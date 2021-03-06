from tkinter import Tk, ttk, Menu, StringVar, Entry, TclError
import json

from PIL import Image, ImageTk

import downloader

class PopupMenu(Menu):
    def __init__(self, parent, *functions):
        super().__init__(parent, tearoff=0)

        self.widget = None

        for func in functions:
            self.add_command(label=f"\t{func.capitalize().replace('_', ' ')}", command=lambda f=func:getattr(self.widget, f)())

    def post(self, widget, x, y):
        self.widget = widget
        super().post(x, y)

class MyEntry(Entry):
    def __init__(self, parent, **kwargs):
        self.var = StringVar()
        self.default = ""

        super().__init__(parent, textvariable=self.var, **kwargs)

        self.bind("<Escape>", self.reset)

    def cut(self):
        if self.selection_present():
            self.copy()
            self.delete(*sorted((self.index("anchor"), self.index("insert"))))

    def copy(self):
        if self.selection_present():
            self.clipboard_append(self.selection_get())

    def paste(self):
        if self.selection_present():
            self.delete(*sorted((self.index("anchor"), self.index("insert"))))
        self.insert("insert", self.clipboard_get())

    def set(self, text):
        self.var.set(text)
        self.default = text

    def get(self):
        return self.var.get()

    def reset(self, args):
        self.var.set(self.default)

class PreviewFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.columnconfigure(2, weight=1)

        self.image = self._blank_image = ImageTk.PhotoImage(Image.new("RGB", (128, 72), (240, 240, 240)))

        self.thumbnail_frame = ttk.Label(self, image=self.image)
        self.thumbnail_frame.grid(rowspan=3)

        ttk.Label(self, text="URL: ").grid(column=1, row=0, sticky="ne")
        self.url_entry = MyEntry(self, state="readonly")
        self.url_entry.grid(column=2, row=0, sticky="we")

        ttk.Label(self, text="Title: ").grid(column=1, row=1, sticky="ne")
        self.title_entry = MyEntry(self)
        self.title_entry.grid(column=2, row=1, sticky="we")

        ttk.Label(self, text="Uploader: ").grid(column=1, row=2, sticky="ne")
        self.uploader_entry = MyEntry(self)
        self.uploader_entry.grid(column=2, row=2, sticky="we")

    def __setattr__(self, key, value):
        if key == "thumbnail":
            if value is None:
                self.image = self._blank_image
            else:
                img = Image.open(value).resize((128, 72), Image.ANTIALIAS)
                self.image = ImageTk.PhotoImage(img)
            self.thumbnail_frame["image"] = self.image
        elif key in ("url", "title", "uploader"):
            getattr(self, f"{key}_entry").set(value)
        else:
            super().__setattr__(key, value)

class Tree(ttk.Treeview):
    def __init__(self, parent, headers):
        self.frame = ttk.Frame(parent)
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

        self["columns"], widths = zip(*headers[1:])
        self.heading("#0", text=headers[0][0], anchor="w")
        self.column("#0", stretch=0, anchor="w", minwidth=headers[0][1], width=headers[0][1])

        for i, w in headers[1:]:
            self.heading(i, text=i, anchor="w")
            self.column(i, stretch=0, anchor="w", minwidth=w, width=w)

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

class BottomFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.cmb = ttk.Combobox(self, values=["Audio", "Video"])
        self.cmb.set("Audio")
        self.cmb.grid(padx=5, pady=5, sticky="nw")

        self.download_btn = ttk.Button(self, text="Download", command=self.download)
        self.download_btn.grid(column=1, row=0, padx=5, pady=5, sticky="nw")

    def download(self):
        self.master.download(self.cmb.get())

class Main(Tk):
    def __init__(self):
        super().__init__()

        self.current_url = None
        self.current_info = None

        self.settings = {
            "geometry": "600x250+400+300",
            "treeview": [
                ["Uploader", 100],
                ["Title", 190],
                ["Progress", 70],
                ["ETA (s)", 50],
                ["Speed", 70]
            ]
        }

        try:
            with open("settings.json") as fp:
                self.settings.update(json.load(fp))
        except FileNotFoundError:
            with open("settings.json", "w") as fp:
                json.dump(self.settings, fp)

        self.title("Video Downloader")
        self.attributes("-topmost", True)
        self.geometry(self.settings["geometry"])
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.minsize(600, 250)

        self.preview_frame = PreviewFrame(self)
        self.preview_frame.grid(padx=5, pady=5, sticky="nwe")

        self.tv = Tree(self, self.settings["treeview"])
        self.tv.grid(column=0, row=1, padx=5, pady=5, sticky="nswe")

        self.bottom_frame = BottomFrame(self)
        self.bottom_frame.grid(column=0, row=2, sticky="w")

        self.menu = PopupMenu(self, "cut", "copy", "paste")
        self.tv_menu = PopupMenu(self, "cancel", "pause", "download_speed")

        self.pv_thread = downloader.Preview(self.preview_callback)
        self.dl_thread = downloader.Downloader(self.callback)
        self.cv_thread = downloader.Converter(self.callback)

        try:
            self.pv_thread.put(self.clipboard_get())
        except TclError:
            pass

        self.bind("<Button-3>", self.popup)

        self.after(100, self.check_clipboard)

        self.protocol("WM_DELETE_WINDOW", self.end)
        self.mainloop()

    def download(self, filetype):
        info = self.current_info

        if info["status"] not in ("Extracting", "Error") and not self.tv.exists(info["id"]):
            info["filetype"] = filetype
            info["title"] = self.preview_frame.title_entry.get()
            info["uploader"] = self.preview_frame.uploader_entry.get()

            values = info["title"], "Queued", "-", "-"
            self.tv.insert("", "end", info["id"], text=info["uploader"], values=values)
            self.dl_thread.put(info)

    def preview_callback(self, info):
        self.preview_frame.thumbnail = info["thumbnail"]
        self.preview_frame.title = info["title"]
        self.preview_frame.uploader = info["uploader"]

        self.current_info = info

    def callback(self, info):
        remaining = info["length"] - info["progress"]
        eta = f"{remaining / info['speed']:.2f}"

        if info["speed"] < 2e3:
            speed = f"{info['speed']:.0f}bps"
        elif info["speed"] < 2e6:
            speed = f"{info['speed']/1e3:.0f}Kbps"
        elif info["speed"] < 2e9:
            speed = f"{info['speed']/1e6:.0f}Mbps"
        elif info["speed"] < 2e12:
            speed = f"{info['speed']/1e9:.0f}Gbps"

        values = [info["title"], f"{info['progress']*100/info['length']:.2f}%", eta, speed]

        if info["status"] == "Finished":
            if info["filetype"] == "Video":
                if self.tv.exists(info["id"]):
                    self.tv.delete(info["id"])
                return True
            self.cv_thread.put(info)
        elif info["status"] == "Converted":
            if self.tv.exists(info["id"]):
                self.tv.delete(info["id"])
            return True
        elif info["status"] == "Converting":
            values[1] = "Converting"

        if self.tv.exists(info["id"]):
            self.tv.item(info["id"], values=values)
        else:
            return True

    def check_clipboard(self):
        try:
            url = self.clipboard_get()
        except TclError:
            pass
        else:
            if self.current_url != url:
                self.current_url = url
                self.preview_frame.url = url

                if self.focus_get() is None:
                    self.pv_thread.put(self.current_url)

            self.after(100, self.check_clipboard)

    def popup(self, args):
        if args.widget == self.tv:
            tv_id = self.tv.identify_row(args.y)
            if tv_id:
                self.tv.selection_set(tv_id)
                self.tv_menu.post(self, args.x_root, args.y_root)
            else:
                self.tv.selection_set()
        elif args.widget in (self.preview_frame.title_entry, self.preview_frame.uploader_entry):
            self.menu.post(args.widget, args.x_root, args.y_root)

    def cancel(self):
        self.tv.delete(self.tv.selection()[0])

    def pause(self):
        # TODO
        print("main pause")

    def download_speed(self):
        # TODO
        print("main download_speed")

    def end(self):
        self.settings["geometry"] = self.geometry()
        
        for n, header in enumerate(self.settings["treeview"]):
            header[1] = self.tv.column(f"#{n}", "width")

        with open("settings.json", "w") as fp:
            json.dump(self.settings, fp)

        self.destroy()

if __name__ == "__main__":
    Main()
