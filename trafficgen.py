# Load external 
import imp
import queue
import streamrunner

class TrafficGen:
    def __init__(self, stream_file_name, device_type):
        self.queue = queue.Queue()
        self.device_type = device_type
        self._load_stream_modules(stream_file_name)
    
    def _load_stream_modules(self, stream_file_name):
        module = imp.load_source('genmodules', stream_file_name)

        gen_functions = []
        for name in dir(module):
            func = getattr(module, name)
            if name.find('gen_')==0 and callable(func):
                gen_functions.append(func)
        
        
        stream_runners = []
        for func in gen_functions:
            stream_runners.append(
                streamrunner.StreamRunner(self.queue, func, self.device_type)
            )
        self.stream_runners = stream_runners

    def get_queue(self):
        return self.queue

    def start(self):
        for sr in self.stream_runners:
            sr.start()
    
    def end(self):
        for sr in self.stream_runners:
            sr.end()

        for sr in self.stream_runners:
            sr.join()




