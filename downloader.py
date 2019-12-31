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

class Preview(Thread):
    def __init__(self, callback):
        super().__init__(daemon=True)

        self.queue = Queue()
        self.callback = callback
        self.ytd = YoutubeDL({
            "logger": logging,
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
        if "youtube" in url:
            url = url.split("&")[0]
        elif "youtu.be" in url:
            yt_id = url.split("?")[0].split("/")[-1]
            url = f"https://www.youtube.com/watch?v={yt_id}"

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
            # if result.get("_type") == "playlist":
            #     base = "https://www.youtube.com/watch?v="
            #     self.check(base + next(result["entries"])["id"])
            # else:
            # TODO: Add playlist functionality

            max_video = max_audio = {}

            for _format in result["formats"]:
                if _format["acodec"] != "none":
                    if _format["vcodec"] != "none":
                        if (_format["filesize"] or 0) > max_video.get("filesize", 0):
                            max_video = _format
                    else:
                        if (_format["filesize"] or 0) > max_audio.get("filesize", 0):
                            max_audio = _format

            self.callback({
                "status": "Ok",
                "url": url,
                "id": result["id"],
                "title": result["title"],
                "uploader": result["uploader"],
                "thumbnail": result["thumbnail"],
                "best_video": max_video,
                "best_audio": max_audio or max_video
            })

class Downloader(Thread):
    def __init__(self, callback):
        super().__init__(daemon=True)

        self.queue = Queue()
        self.callback = callback
        self.pending_removal = set()

        self.start()

    def add(self, info):
        self.queue.put(info)

    def run(self):
        while True:
            self.download(self.queue.get())

    def remove(self, tv_id):
        self.pending_removal.add(tv_id)

    def download(self, info):
        if info["id"] in self.pending_removal:
            self.pending_removal.remove(info["id"])
            return
                
        filetype = f"best_{info['filetype'].lower()}"

        info["status"] = "Downloading"

        data = bytearray()
        previous_time = time.time()
        start, end = 0, 1024 * 1024 - 1
        
        while True:
            session.headers["range"] = f"bytes={start}-{end}"

            response = session.get(info[filetype]["url"])

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

            if info["id"] in self.pending_removal:
                self.pending_removal.remove(info["id"])
                return

            self.callback(info)

            previous_time = time.time()
            start += 1024 * 1024
            end += 1024 * 1024

        with open(f"{info['title']}.{info[filetype]['ext']}", "wb") as fp:
            fp.write(data)

        info["status"] = "Finished"
        self.callback(info)
