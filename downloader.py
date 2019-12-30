from queue import Queue
from threading import Thread
import time
import json
import logging

import requests
from youtube_dl import YoutubeDL, utils

session = requests.Session()

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
                    "id": result["id"],
                    "title": result["title"],
                    "uploader": result["uploader"],
                    "thumbnail": result["thumbnail"],
                    "best_video": max_video["url"],
                    "best_audio": max_audio.get("url", max_video["url"])
                })

class Downloader(Thread):
    def __init__(self, callback):
        super().__init__(daemon=True)

        self.queue = Queue()
        self.callback = callback

        self.start()

    def add(self, info):
        self.queue.put(info)

    def run(self):
        while True:
            self.download(self.queue.get())

    def download(self, info):
        filetype = f"best_{info['filetype'].lower()}"

        info["status"] = "Downloading"

        data = bytearray()
        previous_time = time.time()
        start, end = 0, 1024 * 1024 - 1
        
        while True:
            session.headers["range"] = f"bytes={start}-{end}"

            response = session.get(info[filetype])

            if response.ok:
                data += response.content
            else:
                break

            content_range = response.headers["Content-Range"].split("/")

            info["speed"] = len(response.content) / (time.time() - previous_time)
            info["progress"] = len(data)
            info["length"] = int(content_range[1])

            if int(content_range[0].split("-")[1]) + 1 == info["length"]:
                break

            self.callback(info)

            previous_time = time.time()
            start += 1024 * 1024
            end += 1024 * 1024

        info["status"] = "Saving"
        self.callback(info)

        with open(f"{info['title']}.mp4", "wb") as fp:
            fp.write(data)

        info["status"] = "Finished"
        self.callback(info)
