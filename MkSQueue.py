#!/usr/bin/python
import os
import sys
import json
import threading
import queue

if sys.version_info[0] < 3:
	import _thread
else:
	import _thread

class Manager():
    def __init__(self, handler):
        self.ClassName		    = "MkSQueue"
        self.WorkerStart        = False
        self.Locker			    = threading.Lock()
        self.LocalQueue		    = queue.queue()
        self.HandlerCallback    = handler

    def Start(self):
        self.WorkerStart = True
        _thread.start_new_thread(self.Worker, ())
    
    def Stop(self):
        self.WorkerStart = False
        self.QueueItem(None)
    
    def QueueItem(self, item):
        if self.WorkerStart is True:
            self.Locker.acquire()
            try:
                self.LocalQueue.put(item)
            except Exception as e:
                print("({classname})# ERROR [QueueItem] {0} {error}".format(item,classname=self.ClassName,error=str(e)))
            self.Locker.release()

    def Worker(self):
        while self.WorkerStart is True:
            try:
                item = self.LocalQueue.get(block=True,timeout=None)
                if self.HandlerCallback is not None and item is not None:
                    self.HandlerCallback(item)
            except Exception as e:
                print("({classname})# ERROR - [Worker] {0} {error}".format(item,classname=self.ClassName,error=str(e)))