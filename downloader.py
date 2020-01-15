from io import BytesIO
from queue import Queue
from threading import Thread
import json
import logging
import os
import subprocess
import time

from youtube_dl import YoutubeDL, utils
import mutagen
import requests

logging.basicConfig(
    style="{",
    level=logging.INFO,
    format="[{levelname}] {asctime} {module} {message}",
    datefmt='%H:%M:%S'
)

os.makedirs("Downloads", exist_ok=True)

class BaseThread(Queue, Thread):
    def __init__(self, callback):
        Queue.__init__(self)
        Thread.__init__(self, daemon=True)

        self.callback = callback
        self.start()

    def run(self):
        while True:
            self.process(self.get())

class Preview(BaseThread):
    def __init__(self, callback):
        self.ytd = YoutubeDL({
            "logger": logging,
            "progress_hooks": [callback]
        })
        super().__init__(callback)

    def process(self, url):
        if "youtube" in url:
            url = url.split("&")[0]
        elif "youtu.be" in url:
            yt_id = url.split("?")[0].split("/")[-1]
            url = f"https://www.youtube.com/watch?v={yt_id}"

        self.callback({
            "status": "Extracting",
            "url": url,
            "thumbnail": None,
            "title": "Extracting",
            "uploader": "Extracting info"
        })

        try:
            result = self.ytd.extract_info(url, process=False)
        except utils.DownloadError as e:
            if "is not valid URL." in e.args[0]:
                self.callback({
                    "status": "Error",
                    "url": url,
                    "thumbnail": None,
                    "title": "Error",
                    "uploader": "Invalid url"
                })
        else:
            # TODO: Add playlist functionality
            # if result.get("_type") == "playlist":
            #     base = "https://www.youtube.com/watch?v="
            #     self.check(base + next(result["entries"])["id"])
            # else:

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
                "thumbnail": BytesIO(requests.get(result["thumbnail"]).content),
                "best_video": max_video,
                "best_audio": max_audio or max_video
            })

class Downloader(BaseThread):
    def process(self, info):
        filetype = f"best_{info['filetype'].lower()}"
        filename = f"Downloads/{info['title']}.{info[filetype]['ext']}"

        if not os.path.isfile(filename):
            info["status"] = "Downloading"

            info["progress"] = 0
            previous_time = time.time()
            start, end = 0, 2**20 - 1

            while True:
                response = requests.get(info[filetype]["url"], headers={"range":f"bytes={start}-{end}"})

                if response.ok:
                    with open(filename, "ab") as fp:
                        fp.write(response.content)
                    info["progress"] += len(response.content)
                else:
                    break

                content_end, info["length"] = map(int, response.headers["Content-Range"].split("-")[1].split("/"))

                info["speed"] = len(response.content) / (time.time() - previous_time)
                if self.callback(info):
                    return

                if content_end + 1 == info["length"]:
                    break

                previous_time = time.time()
                start += 2**20
                end += 2**20

        info["status"] = "Finished"
        self.callback(info)

class Converter(BaseThread):
    def process(self, info):
        ext = info[f"best_{info['filetype'].lower()}"]['ext']
        old_filename = f"Downloads/{info['title']}.{ext}"
        new_filename = f"Downloads/{info['title']}.mp3"

        if not os.path.isfile(new_filename):
            info["status"] = "Converting"
            self.callback(info)

            subprocess.run([
                "ffmpeg.exe",
                "-i", old_filename,
                new_filename,
                "-y"
            ])

            os.remove(old_filename)

            muta = mutagen.File(new_filename, easy=True)
            muta["artist"] = info["uploader"]
            muta.save()

        info["status"] = "Converted"
        self.callback(info)
