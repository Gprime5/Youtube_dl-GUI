from threading import Thread
from queue import Queue
from youtube_dl import YoutubeDL, utils
import logging

import json
from time import sleep

logging.basicConfig(
    style="{",
    level=logging.INFO,
    format="[{levelname}] {asctime} {module} {message}",
    datefmt='%H:%M:%S'
)
logger = logging.getLogger()

class Preview(Thread):
    def __init__(self, callback):
        super().__init__(daemon=True)

        self.queue = Queue()
        self.callback = callback
        self.ytd = YoutubeDL({
            "logger": logger,
            "progress_hooks": [self.callback],
            "format": "mp4"
        })

        self.start()

    def add(self, item):
        self.queue.put(item)

    def run(self):
        while True:
            self.check(self.queue.get())

    def check(self, url):
        try:
            self.callback({
                "status": "Extracting",
                "url": url,
                "thumbnail": None,
                "title": "Extracting",
                "uploader": "Extracting info"
            })
            result = self.ytd.extract_info(url, process=False)
        except utils.DownloadError as e:
            if "is not a valid URL." in e.args[0]:
                self.callback({
                    "status": "Error",
                    "url": url,
                    "thumbnail": None,
                    "title": "Error",
                    "uploader": "Invalid url"
                })
        else:
            if result.get("_type") == "playlist":
                base = "https://www.youtube.com/watch?v="
                self.check(base + result.get("webpage_url_basename"))
            else:
                max_video = {"filesize": 0}
                max_audio = {"filesize": 0}

                for _format in result["formats"]:
                    if _format["acodec"] != "none":
                        if _format["vcodec"] != "none":
                            if (_format["filesize"] or 0) > max_video["filesize"]:
                                max_video = _format
                        else:
                            if (_format["filesize"] or 0) > max_audio["filesize"]:
                                max_audio = _format

                self.callback({
                    "status": "Ok",
                    "url": url,
                    "title": result["title"],
                    "uploader": result["uploader"],
                    "thumbnail": result["thumbnail"],
                    "best_video": max_video["url"],
                    "best_audio": max_audio["url"]
                })

class Downloader(Thread):
    def __init__(self, callback):
        super().__init__(daemon=True)

        self.queue = Queue()
        self.callback = callback
        self.current_downloads = {}

        self.start()

    def add(self, info):
        self.queue.put(info)

    def run(self):
        while True:
            self.download(self.queue.get())

    def download(self, info):
        print(info)