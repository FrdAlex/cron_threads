import threading
import time
import sys
import json
import importlib
from enum import Enum
from subprocess import Popen, PIPE
from functools import wraps
from typing import Tuple, Dict, List
from croniter import croniter

def enforce_return_count(expected_count:int = 3):
    """Forces function to return a specific number of arguments.

    Args:
    expected_count(int = 3): The number of arguments to return
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if not isinstance(result, tuple):
                result = (result,)

            actual_count = len(result)

            if actual_count < expected_count:
                result = result + (None,) * (expected_count - actual_count)
            elif actual_count > expected_count:
                raise ValueError(f"Expected {expected_count} return values, but got {actual_count}")

            return result
        return wrapper
    return decorator

# custom system command
def system_cmd(command:str) -> Tuple[int, str, str]:
    """Run a system command in a separate shell and return the exit code, output and error mesages.

    Args:
        command(str): The command to run

    Returns:
        Tuple[int, str, str] : the exit code, output and error messages, decoded as utf-8
    """
    with Popen(args=command, stdout=PIPE, stderr=PIPE, shell=True) as process:
        out, err = process.communicate()
        retcode = process.poll()
        return retcode, out.decode("utf-8"), err.decode("utf-8")

class WorkerModes(Enum):
    """Represents an enum with the Working Modes.

    COMMAND: a command to run on the OS using a shell
    FILE: run a function from an external python file which needs to be imported first
    INTERNAL: an internal function to the script calling to start the thread
    """
    COMMAND = 0
    FILE = 1
    INTERNAL = 2

class ThreadManager():
    """Class that manages the threads"""

    # Dictionary to store threads and their exit codes
    threads = {}
    thread_exit_codes = {}
    task_exit_info = []
    clean_threads = []
    thread = None
    close_main_thread = False

    def start_thread(self, name:str, cron_schedule:str, mode:int, to_exec, *args, func_name = None, **kwargs):
        """Start a Thread. If a cron schedule is provided it will run the task inside at the specified time.
           If no cron schedule is provided, it will execute once then the thread will close.

        Args:
            name(str): Identifier for the thread
            cron_schedule(str): The schedule on which to run the task inside the thread
            mode(int): Supply a WorkedMode here.
            to_exec(function | str): The function or command to run
            func_name(function): Applies to FILE mode only, the function inside another python script to run
            *args,**kwargs: any needed additional arguments here which should be passed further along

        Returns:
            None : if the cron_schedule provided is not valid
        """

        thread = WorkerThread(self, name, cron_schedule, mode, to_exec, func_name, *args, **kwargs)
        if thread is not None:
            self.threads[name] = thread
            thread.start()
        else:
            return None

    def stop_thread(self, name):
        """Sends a signal to stop a thread. If the task is currently running it will stop only after 
        the task has finished

        Args:
            name(str): Identifier for the thread

        """

        if name in self.threads:
            self.threads[name].shutdown_flag.set()
            print(f"Signal sent to thread '{name}'")
        else:
            print(f"Thread '{name}' not found")

    def get_exit_code(self, name):
        """Returns the exit code of a thread that has exited

        Args:
            name(str): Identifier for the thread

        """

        return self.thread_exit_codes.get(name, None)

    def begin_manage(self):
        """Starts a separate thread that manages all user started threads
        and checks if any of them has exited at any time. Also deletes the thread
        from the dict of running threads to maintain cleanliness
        """

        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self.__begin)
            self.thread.start()
        else:
            print("Thread is already running")

    def stop_manage(self):
        """Stops the thread manager and kills any active threads remaining."""

        if self.thread is not None:
            self.kill_all_threads()
            self.close_main_thread = True

    def __begin(self):
        while True:
            if self.close_main_thread:
                print("Closing Thread Manager task")
                sys.exit()

            # Retrieve exit codes
            for name in self.thread_exit_codes.keys():
                print(f"Thread '{name}' exit code: {self.get_exit_code(name)}")
                data = {
                    "name" : name,
                    "exit_code": self.get_exit_code(name)
                }
                self.clean_threads.append(data)
                del self.threads[name]

            print("Thread Manager task active !")
            self.thread_exit_codes = {}
            time.sleep(5)

    def have_threads_exited(self):
        """Check to see if any threads have exited for any reason"""

        if len(self.clean_threads) > 0:
            return True
        return False

    def have_tasks_exited(self):
        """Check to see if any tasks inside threads have finished"""

        if len(self.task_exit_info) > 0:
            return True
        return False

    def get_task_exit_info(self) -> Dict:
        """Retrieve the details around an exited task"""

        if self.have_tasks_exited():
            task_found = self.task_exit_info.pop(0)
            name = task_found["name"]
            ret_code = task_found["exit_code"]
            data = {"name": name, "exit_code": ret_code}
            return data

    def get_thread_exit_info(self) -> Dict:
        """Retrieve the details around an exited thread"""

        if self.have_threads_exited():
            thread_found = self.clean_threads.pop(0)
            name = thread_found["name"]
            ret_code = thread_found["exit_code"]
            data = {"name": name, "exit_code": ret_code}
            return data

    def get_existing_threads(self) -> List:
        """Retrieve a list of all currently existing threads"""

        ret = []
        for thread_name in self.threads:
            ret.append(thread_name)
        return ret

    def get_running_threads(self):
        """Retrieve a list of all threads in which tasks are currently running"""

        ret = []
        for thread_name in self.threads.keys():
            if self.threads[thread_name].currently_running:
                ret.append(thread_name)
        return ret

    def kill_all_threads(self):
        """Stop all threads"""

        for thread_name in self.threads.keys():
            self.stop_thread(thread_name)

    def save_to_disk_status(self):
        """Save to disk in the cwd information related to all existing threads and all running threads"""
        data = {}
        with open("thread_manager_status.json", encoding="utf-8") as status:
            data["threads"] = self.get_existing_threads()
            data["currently_running"] = self.get_running_threads()
            json.dump(data, indent=4, sort_keys=True, fp=status)

class WorkerThread(threading.Thread):
    """Class that represents the actual thread being run"""

    def __init__(self, parent: ThreadManager, name, cron_schedule, mode, to_exec, *args, func_name = None, **kwargs):
        super().__init__()
        if cron_schedule is not None and not croniter.is_valid(cron_schedule):
            print("Cron Schedule is not valid !")
            return None
        if cron_schedule is None or cron_schedule == "":
            self.oneshot = True
            self.cron_iter = None
        else:
            self.oneshot = False
            self.cron_iter = croniter(cron_schedule, start_time=time.time())
        self.parent = parent
        self.name = name
        self.mode = mode
        self.to_exec = to_exec
        self.func_name = func_name
        self.cron_schedule = cron_schedule
        self.exit_code = 0
        self.shutdown_flag = threading.Event()
        self.args = args
        self.kwargs = kwargs
        self.currently_running = False
        self.seconds_until_next_run = 0

    def run(self):
        print(f"Thread '{self.name}' started ")
        while True:

            start_time = time.time()

            if self.cron_schedule is not None:
                next_run = self.cron_iter.get_next(float)
                delay = max(0, next_run - time.time())

                for i in range(0,int(delay)):
                    if self.should_stop():
                        break
                    self.seconds_until_next_run = delay - i
                    time.sleep(1)

                if self.should_stop():
                    self.__do_stop(0)
                    break
                ret, out, err = self.worker_task()
                self.parent.task_exit_info.append(self.__prepare_task_info(start_time, ret, out, err))
            else:
                ret, out, err = self.worker_task()
                self.parent.task_exit_info.append(self.__prepare_task_info(start_time, ret, out, err))
                self.__do_stop(ret, True)

    def __prepare_task_info(self, start_time, ret, output=None, error=None):
        data = {
            "name": self.name,
            "exit_code": ret,
            "start_time": start_time,
            "finish_time": time.time(),
            "output": output,
            "error": error,
            "oneshot" : self.oneshot
        }
        return data

    @enforce_return_count(3)
    def worker_task(self):
        """This methods contains the actual logic on how to run a task"""
        self.currently_running = True
        try:
            if self.mode == WorkerModes.COMMAND:
                return system_cmd(self.to_exec)
            if self.mode == WorkerModes.FILE:
                module = importlib.import_module(self.to_exec)
                method = getattr(module, self.func_name)
                return method() # should return exit_code, output, error in that order
            if self.mode == WorkerModes.INTERNAL:
                return self.to_exec(*self.args, **self.kwargs) # should return exit_code, output, error in that order
        except Exception as e:
            print(e)
        self.currently_running = False

    def should_stop(self):
        """Check if the thread should stop"""
        if self.shutdown_flag.is_set():
            return True
        return False

    def __do_stop(self, ret = 0, one_shot = False):
        if not one_shot:
            print(f"Thread '{self.name}' received signal, closing...")
        self.exit_code = ret
        print(f"Thread '{self.name}' finished with exit code {self.exit_code}")
        self.parent.thread_exit_codes[self.name] = self.exit_code
        if one_shot:
            del self.parent.threads[self.name]
        sys.exit(ret)
