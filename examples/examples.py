from cron_threads import ThreadManager, WorkerModes # pylint: disable=import-error,no-name-in-module

def internal(group):
    """example function to just print whatever is given as argument"""
    print(group)

manager = ThreadManager()
manager.begin_manage()
# Example usage
manager.start_thread("thread1", "* * * * *",WorkerModes.COMMAND,"dir")
manager.start_thread("thread2", "* * * * *",WorkerModes.FILE,"file_name",func_name="run")
manager.start_thread("thread3", None, WorkerModes.INTERNAL, internal, "123")
