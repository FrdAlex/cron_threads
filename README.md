
# Cron Threads

A Python module whose goal is to simplify working with threads which need to trigger it`s internal tasks via a cron schedule.




## Working Modes

- Command : used to run os specific commands in a shell in a separate thread
- File : import a specific python script and run a function within it as a separate thread. Very good for running scripts based on template
- Internal : run just an internal function in a separate thread

## Schedules
- If a schedule is provided in cron format, it will execute whatever is specified based on that specific schedule
- If no schedule is provided or is left empty, then it will work as oneshot, were after the work is done, the thread will be deleted.

## Workflow logic
- Rather than start a thread directly which you have to manage manually, a thread manager has been created which holds references to each thread it was created by it.
- The Manager has a function which enables management of threads, specifically monitoring for when threads exit or for when the tasks inside threads finish executing and relay-ing that info to the main thread.
- The thread will always stay online if possible if a cron schedule is provided, an internal timer will just suspend the thread until it is time for whatever needes to be run to be executed again.

## Thread Output
- Ideally the task given to the thread should always return 3 things : exit code(int), output(str) and error(str), in that specific order
- If the task has no return statements, or it returns less that the 3 mentioned items, it will suppliment with None returns
- If more than 3 items are returned, it will throw an error mentioning that only 3 items can be returned.



## Usage/Examples

```python
from cron_threads import ThreadManager, WorkerModes 

def internal(group):
    """example function to just print whatever is given as argument"""
    print(group)

manager = ThreadManager()
manager.begin_manage()
# Example usage
manager.start_thread("thread1", "* * * * *",WorkerModes.COMMAND,"dir") # run the dir command as a separate shell
manager.start_thread("thread2", "* * * * *",WorkerModes.FILE,"file_name",func_name="run") # run a separate function from within another python script
manager.start_thread("thread3", None, WorkerModes.INTERNAL, internal, "123") # use an internal function as the task of the thread

manager.stop_thread("thread1") # will send a signal to the tread to close. If the task of the thread is running, it will wait for the task to finish, then close the thread

# simple while true logic to monitor what is going on with the threads
while True:
    while manager.have_threads_exited() > 0:
        print(manager.get_thread_exit_info())
    while manager.have_tasks_exited() > 0:
        print(manager.get_task_exit_info())    
    if some_test_here_is_true:
        manager.stop_manage() # this will kill all threads as well

```


## Future improvements

- Force kill thread even when task is running
- Resource locking
- Community Requests which make sense
- TBD

