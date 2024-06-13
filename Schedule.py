from enum import Enum
import threading
import os
import time
import sys
from croniter import croniter
import importlib

class WorkerModes(Enum):
    COMMAND = 0,
    FILE = 1,
    INTERNAL = 2

class WorkerThread(threading.Thread):
    def __init__(self, parent, name, cron_schedule, mode, exec, func_name = None, *args, **kwargs):
        super().__init__()
        if cron_schedule != None and not croniter.is_valid(cron_schedule):
            print("Cron Schedule is not valid !")
            return None
        self.parent = parent
        self.name = name
        self.mode = mode
        self.exec = exec
        self.func_name = func_name
        self.cron_schedule = cron_schedule
        self.cron_iter = croniter(cron_schedule, start_time=time.time())
        self.exit_code = 0
        self.shutdown_flag = threading.Event()
        self.args = args
        self.kwargs = kwargs
        self.currently_running = False
        

    def run(self):
        print(f"Thread '{self.name}' started ")
        while True:
            if self.cron_schedule != None:
                next_run = self.cron_iter.get_next(float)
                delay = max(0, next_run - time.time())

                for i in range(0,int(delay)):
                    if self.should_stop():
                        break
                    time.sleep(1)

                if self.should_stop():
                    self.__do_stop(0)
                    break
                else:
                    self.worker_task()
            else:
                ret = self.worker_task()
                self.__do_stop(ret, True)
              
    def worker_task(self):
        self.currently_running = True
        try:
            if self.mode == WorkerModes.COMMAND:
                return os.system(self.exec)
            elif self.mode == WorkerModes.FILE:
                module = importlib.import_module(self.exec)
                method = getattr(module, self.func_name)
                return method()
            elif self.mode == WorkerModes.INTERNAL:
                return self.exec(*self.args, **self.kwargs)
        except Exception as e:
            with open(self.name + "_errors.txt", 'w') as err_writer:
                err_writer.write(time.ctime(time.time())," : ", e)
        self.currently_running = False
        
    def should_stop(self):
        if self.shutdown_flag.is_set():
            return True
        return False
    
    def __do_stop(self, ret = 0, one_shot = False):
        if not one_shot:
            print(f"Thread '{self.name}' received signal, closing...")
        self.exit_code = ret
        print(f"Thread '{self.name}' finished with exit code {self.exit_code}")
        self.parent.thread_exit_codes[self.name] = self.exit_code
        sys.exit(ret)


class ThreadManager():
    # Dictionary to store threads and their exit codes
    threads = {}
    thread_exit_codes = {}
    clean_threads = []
    thread = None
    close_main_thread = False

    def start_thread(self, name, cron_schedule, mode, exec, func_name = None, *args, **kwargs):
        thread = WorkerThread(self, name, cron_schedule, mode, exec, func_name, *args, **kwargs)
        if thread != None:
            self.threads[name] = thread
            thread.start()
        else:
            return None

    def stop_thread(self, name):
        if name in self.threads:
            self.threads[name].shutdown_flag.set()
            print(f"Signal sent to thread '{name}'")
        else:
            print(f"Thread '{name}' not found")

    def get_exit_code(self, name):
        return self.thread_exit_codes.get(name, None)
    
    def begin_manage(self):
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self.__begin)
            self.thread.start()
        else:
            print("Thread is already running")
    
    def stop_manage(self):
        if self.thread != None:
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
    
    def have_tasks_exited(self):
        if len(self.clean_threads) > 0:
            return True
        return False
    
    def get_task_exit_info(self):
        if self.have_tasks_exited():
            thread_found = self.clean_threads.pop(0)
            name = thread_found["name"]
            ret_code = thread_found["exit_code"]
            data = {"name": name, "exit_code": ret_code}
            return data
    
    def get_existing_threads(self):
        ret = []
        for thread_name in self.threads:
            ret.append(thread_name)
        return ret
    
    def get_running_threads(self):
        ret = []
        for thread_name in self.threads:
            if self.threads[thread_name].currently_running == True:
                ret.append(thread_name)
        return ret

    def kill_all_threads(self):
        for thread_name in self.threads.keys():
            self.stop_thread(thread_name)
        
def internal(group):
    print(group)
        
manager = ThreadManager()
#manager.begin_manage()
# Example usage
#manager.start_thread("thread1", "* * * * *",WorkerModes.COMMAND,"dir")
#manager.start_thread("thread2", "* * * * *",WorkerModes.FILE,"lol","run")
manager.start_thread("thread3", "* * * * *",WorkerModes.INTERNAL,internal,None, group = "123")

