from tkinter import *
from tkinter import ttk
import json
from io import BytesIO

import requests
from PIL import Image, ImageTk

from downloader import Preview, Downloader

class Popup_menu(Menu):
    def __init__(self, parent):
        super().__init__(parent, tearoff=0)

        self.add_command(label="\tCut", command=self.cut)
        self.add_command(label="\tCopy", command=self.copy)
        self.add_command(label="\tPaste", command=self.paste)

    def cut(self):
        self.entry.cut()

    def copy(self):
        self.entry.copy()

    def paste(self):
        self.entry.paste()

    def set_entry(self, entry):
        self.entry = entry

class MyEntry(Entry):
    def __init__(self, parent, **kwargs):
        self.var = StringVar()
        self.default = ""

        super().__init__(parent, textvariable=self.var, bg="SystemButtonFace", relief="flat", **kwargs)

        self.bind("<Escape>", self.reset)
        self.bind("<Button-3>", self.popup)

    def cut(self):
        if self.selection_present():
            self.copy()
            self.delete(*sorted((self.index("anchor"), self.index("insert"))))

    def copy(self):
        self.clipboard_append(self.selection_get())

    def paste(self):
        if self.selection_present():
            self.delete(*sorted((self.index("anchor"), self.index("insert"))))
        self.insert("insert", self.clipboard_get())

    def set(self, text):
        self.var.set(text)
        self.default = text

    def reset(self, args):
        self.var.set(self.default)

    def popup(self, args):
        self.master.menu.set_entry(self)
        self.master.menu.post(args.x_root, args.y_root)

class Previewer_frame(Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.columnconfigure(2, weight=1)

        self.image = self._blank_image = ImageTk.PhotoImage(Image.new("RGB", (128, 72), (240, 240, 240)))

        self.thumbnail_frame = Label(self, image=self.image)
        self.thumbnail_frame.grid(padx=5, pady=5, rowspan=5)

        Label(self, text="URL: ").grid(column=1, row=0, sticky="ne")
        self.url_entry = MyEntry(self, state="readonly")
        self.url_entry.grid(column=2, row=0, sticky="nwe")

        Label(self, text="Title: ").grid(column=1, row=1, sticky="ne")
        self.title_entry = MyEntry(self)
        self.title_entry.grid(column=2, row=1, sticky="nwe")

        Label(self, text="Uploader: ").grid(column=1, row=2, sticky="ne")
        self.uploader_entry = MyEntry(self)
        self.uploader_entry.grid(column=2, row=2, sticky="nwe")

        self.menu = Popup_menu(self)

    def __setattr__(self, key, value):
        if key == "thumbnail":
            if value is None:
                self.image = self._blank_image
            else:
                data = BytesIO(requests.get(value).content)
                img = Image.open(data).resize((128, 72), Image.ANTIALIAS)
                self.image = ImageTk.PhotoImage(img)
            self.thumbnail_frame["image"] = self.image
        elif key in ("title", "uploader", "url"):
            getattr(self, f"{key}_entry").set(value)
        else:
            super().__setattr__(key, value)

class Tree(ttk.Treeview):
    def __init__(self, parent):
        self.frame = Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)

        xscroll = lambda first, last: self.scroll(xs, first, last)
        yscroll = lambda first, last: self.scroll(ys, first, last)
        super().__init__(self.frame, xscroll=xscroll, yscroll=yscroll)
        super().grid(sticky="nsew")

        xs = ttk.Scrollbar(self.frame, orient="horizontal", command=self.xview)
        xs.grid(column=0, row=1, sticky="we")

        ys = ttk.Scrollbar(self.frame, orient="vertical", command=self.yview)
        ys.grid(column=1, row=0, sticky="ns")

        ttk.Style().layout("Treeview", [("treeview.treearea", {"sticky": "nswe"})])

        self["columns"] = ["Title", "Progress", "ETA", "Speed"]
        self.heading("#0", text="Uploader", anchor="w")
        self.column("#0", stretch=0, anchor="w", minwidth=100, width=100)

        for i, w in zip(self["columns"][:-1], (190, 70, 50)):
            self.heading(i, text=i, anchor="w")
            self.column(i, stretch=0, anchor="w", minwidth=w, width=w)

        i = self["columns"][-1]
        self.heading(i, text=i, anchor="w")
        self.column(i, stretch=1, anchor="w", minwidth=70, width=70)

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)

    def scroll(self, sbar, first, last):
        """Hide and show scrollbar as needed."""
        first, last = float(first), float(last)
        if first <= 0 and last >= 1:
            sbar.grid_remove()
        else:
            sbar.grid()
        sbar.set(first, last)

class Bottom(Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.cb = ttk.Combobox(self, values=["Audio", "Video"])
        self.cb.set("Audio")
        self.cb.grid(padx=5, pady=5, sticky="nw")

        self.download_btn = ttk.Button(self, text="Download", command=self.download)
        self.download_btn.grid(column=1, row=0, padx=5, pady=5, sticky="nw")

    def download(self):
        self.master.add(self.cb.get())

class main(Tk):
    def __init__(self):
        super().__init__()

        self.settings = {}
        self.pv = Preview(self.populate_previewer)
        self.dc = Downloader(self.handle_download)
        self.current_info = {"status": None}

        try:
            self.current_url = self.clipboard_get()
        except TclError:
            self.current_url = None

        try:
            with open("settings.json") as fp:
                self.settings = json.load(fp)
        except FileNotFoundError:
            with open("settings.json", "w") as fp:
                json.dump(self.settings, fp)

        self.title("Youtube Downloader")
        self.attributes("-topmost", True)
        self.geometry(self.settings.get("geometry", "600x250+400+300"))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.minsize(600, 250)

        self.previewer_frame = Previewer_frame(self)
        self.previewer_frame.grid(padx=5, pady=5, sticky="nwe")

        self.tv = Tree(self)
        self.tv.grid(column=0, row=1, padx=5, pady=5, sticky="nswe")

        self.bottom = Bottom(self)
        self.bottom.grid(column=0, row=2, sticky="w")

        try:
            self.pv.add(self.clipboard_get())
        except TclError:
            pass
            
        self.after(100, self.check_clipboard)

        self.protocol("WM_DELETE_WINDOW", self.end)
        self.mainloop()

    def check_clipboard(self):
        try:
            url = self.clipboard_get()
        except TclError:
            pass
        else:
            if self.current_url != url:
                self.current_url = url

                if self.focus_get() is None:
                    self.pv.add(self.current_url)

            self.after(100, self.check_clipboard)

    def add(self, download_type):
        if self.current_info["status"] == "Ok":
            self.current_info["type"] = download_type
            self.dc.add(self.current_info)

    def handle_download(self, info):
        print(info)

    def populate_previewer(self, info):
        self.previewer_frame.url = info["url"]
        self.previewer_frame.thumbnail = info["thumbnail"]
        self.previewer_frame.title = info["title"]
        self.previewer_frame.uploader = info["uploader"]

        self.current_info = info

    def end(self):
        self.settings["geometry"] = self.geometry()

        with open("settings.json", "w") as fp:
            json.dump(self.settings, fp)

        self.destroy()

if __name__ == "__main__":
    main()