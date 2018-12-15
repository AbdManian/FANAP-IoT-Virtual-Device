import time
import threading


class StreamRunner(threading.Thread):
    def __init__(self, q, gen_function, device_type):

        threading.Thread.__init__(self)
        self.q = q
        self.gen_function = gen_function
        self.continue_run = True
        self.device_type = device_type
    
    def run(self):
        user_data = {}
        while self.continue_run:
            for x in self.gen_function(self.device_type, user_data):
                data, delay = x

                if not data or not self.continue_run:
                    return
                
                if delay>=0:
                    time.sleep(delay)

                self.q.put(data)
    
    def end(self):
        self.continue_run = False


