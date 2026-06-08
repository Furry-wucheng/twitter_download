import os
import pickle
import threading
import time


class cache_gen():

    def __init__(self, save_path, is_share=False) -> None:
        if is_share:
            self.cache_path = os.path.dirname(save_path) + os.sep + "cache_data.log"
        else:
            self.cache_path = save_path + os.sep + "cache_data.log"

        if os.path.exists(self.cache_path):
            with open(self.cache_path, 'rb') as f:
                self.cache_data = pickle.load(f)
        else:
            self.cache_data = set()

        # 开启自动保存线程
        thread = threading.Thread(target=self.save_cache)
        thread.daemon = True
        thread.start()

    def __del__(self):
        with open(self.cache_path, 'wb') as f:
            pickle.dump(self.cache_data, f)

    def add(self, element):
        self.cache_data.add(element)

    def save_cache(self):
        while True:
            time.sleep(10)
            with open(self.cache_path, 'wb') as f:
                pickle.dump(self.cache_data, f)

    def is_present(self, element):
        if element in self.cache_data:
            return False
        else:
            return True
