# -*- coding: utf-8 -*-
"""批量复制文件名工具 - Windows 桌面版"""
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

CONFIG_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "FilenameCopier", "config.json")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("批量复制文件名工具")
        self.geometry("780x620")
        self.minsize(640, 480)
        self.configure(bg="#1e1f24")

        self.files = []        # 完整路径列表
        self.names = []        # 文件名列表（与 files 一一对应）
        self.folder = ""
        self.checked = set()   # 已勾选文件名集合
        self._build_ui()
        last = self._load_config().get("last_folder")
        if last and os.path.isdir(last):
            self.load_folder(last, silent=True)

    # ---------- 配置 ----------
    def _load_config(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save_config(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"last_folder": self.folder}, f, ensure_ascii=False)
        except OSError:
            pass

    # ---------- UI ----------
    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background="#26272e", foreground="#e4e5ea",
                        fieldbackground="#2d2e36", bordercolor="#3a3b44")
        style.configure("TFrame", background="#26272e")
        style.configure("TLabel", background="#26272e", foreground="#e4e5ea")
        style.configure("TButton", background="#2d2e36", foreground="#e4e5ea",
                        bordercolor="#3a3b44", padding=6)
        style.map("TButton", background=[("active", "#383945")])
        style.configure("Primary.TButton", background="#4f8cff", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#3a78f0")])
        style.configure("TEntry", fieldbackground="#2d2e36", foreground="#e4e5ea")
        style.configure("TCheckbutton", background="#26272e", foreground="#9a9ba6")
        style.map("TCheckbutton",
                  background=[("active", "#26272e")],
                  foreground=[("selected", "#e4e5ea")])
        style.configure("TRadiobutton", background="#26272e", foreground="#9a9ba6")
        style.map("TRadiobutton",
                  background=[("active", "#26272e")],
                  foreground=[("selected", "#e4e5ea")])

        # 工具栏
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=12, pady=(12, 6))
        ttk.Button(bar, text="📂 选择文件夹", command=self.pick_folder).pack(side="left")
        ttk.Button(bar, text="全选", command=self.select_all).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="反选", command=self.invert).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="清空", command=self.clear).pack(side="left", padx=(6, 0))
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self.render_list())
        ttk.Entry(bar, textvariable=self.filter_var, width=28).pack(side="left", padx=(10, 0), fill="x", expand=True)
        self.folder_label = ttk.Label(bar, text="", foreground="#9a9ba6")
        self.folder_label.pack(side="left", padx=(10, 0))

        # 格式选择
        fmt_bar = ttk.Frame(self)
        fmt_bar.pack(fill="x", padx=12, pady=4)
        ttk.Label(fmt_bar, text="复制格式：").pack(side="left")
        self.fmt_var = tk.StringVar(value="name")
        for text, val in [("完整文件名", "name"), ("不含扩展名", "stem"), ("完整路径", "path")]:
            ttk.Radiobutton(fmt_bar, text=text, value=val, variable=self.fmt_var,
                            command=self.update_preview).pack(side="left", padx=(4, 8))
        ttk.Label(fmt_bar, text="分隔符：").pack(side="left", padx=(10, 0))
        self.sep_var = tk.StringVar(value="nl")
        for text, val in [("换行", "nl"), ("空格", "space"), ("逗号", "comma"), ("分号", "semicolon")]:
            ttk.Radiobutton(fmt_bar, text=text, value=val, variable=self.sep_var,
                            command=self.update_preview).pack(side="left", padx=(4, 8))

        # 状态栏 + 复制按钮
        stat_bar = ttk.Frame(self)
        stat_bar.pack(fill="x", padx=12, pady=4)
        self.stat_var = tk.StringVar(value="共 0 个文件，已选 0 个")
        ttk.Label(stat_bar, textvariable=self.stat_var).pack(side="left")
        ttk.Button(stat_bar, text="⧉ 复制所选文件名", style="Primary.TButton",
                   command=self.copy_selected).pack(side="right")

        # 文件列表
        list_wrap = ttk.Frame(self)
        list_wrap.pack(fill="both", expand=True, padx=12, pady=6)
        self.canvas = tk.Canvas(list_wrap, bg="#26272e", highlightthickness=0)
        scroll = ttk.Scrollbar(list_wrap, orient="vertical", command=self.canvas.yview)
        self.list_frame = ttk.Frame(self.canvas)
        self.list_frame.bind("<Configure>",
                             lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw",
                                  tags="inner")
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        self.canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # 复选状态
        self.check_vars = {}   # name -> tk.BooleanVar

        # 预览
        self.preview = tk.Text(self, height=6, bg="#2d2e36", fg="#9a9ba6",
                               relief="flat", font=("Consolas", 9),
                               insertbackground="#e4e5ea")
        self.preview.pack(fill="x", padx=12, pady=(6, 12))
        self.preview.insert("1.0", "复制预览：—")
        self.preview.configure(state="disabled")

    def _on_canvas_resize(self, e):
        self.canvas.itemconfigure("inner", width=e.width)

    # ---------- 数据 ----------
    def pick_folder(self):
        d = filedialog.askdirectory(title="选择文件夹")
        if d:
            self.load_folder(d)

    def load_folder(self, folder, silent=False):
        try:
            entries = sorted(os.listdir(folder))
        except OSError as e:
            if not silent:
                messagebox.showerror("错误", f"无法读取文件夹：\n{e}")
            return
        self.folder = folder
        self.names = []
        self.files = []
        self.checked = set()
        for n in entries:
            p = os.path.join(folder, n)
            if os.path.isfile(p):
                self.names.append(n)
                self.files.append(p)
        self.folder_label.config(text=folder)
        self.render_list()
        self._save_config()

    def visible(self):
        kw = self.filter_var.get().strip().lower()
        if not kw:
            return list(range(len(self.names)))
        return [i for i, n in enumerate(self.names) if kw in n.lower()]

    def render_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.check_vars = {}
        for i in self.visible():
            name = self.names[i]
            var = tk.BooleanVar(value=name in self.checked)
            self.check_vars[name] = var
            row = ttk.Frame(self.list_frame)
            row.pack(fill="x")
            cb = ttk.Checkbutton(row, text=name, variable=var, command=self.on_check)
            cb.pack(anchor="w", padx=8, pady=1)
        self._sync_stats()
        self.update_preview()

    def _checked_set(self):
        return {n for n, v in self.check_vars.items() if v.get()}

    def on_check(self):
        self.checked = self._checked_set()
        self._sync_stats()
        self.update_preview()

    def select_all(self):
        for i in self.visible():
            self.checked.add(self.names[i])
        self.render_list()

    def clear(self):
        self.checked.clear()
        self.render_list()

    def invert(self):
        for i in self.visible():
            name = self.names[i]
            if name in self.checked:
                self.checked.discard(name)
            else:
                self.checked.add(name)
        self.render_list()

    def selected_names(self):
        """按文件列表原始顺序返回已勾选文件名"""
        return [n for n in self.names if n in self.check_vars and self.check_vars[n].get()]

    def _sync_stats(self):
        vis = len(self.visible())
        sel = len(self.selected_names())
        total = len(self.names)
        txt = f"共 {total} 个文件"
        if vis != total:
            txt += f"，筛选出 {vis} 个"
        txt += f"，已选 {sel} 个"
        self.stat_var.set(txt)

    # ---------- 复制 ----------
    def build_output(self):
        sep = {"nl": "\n", "space": " ", "comma": ", ", "semicolon": ";"}[self.sep_var.get()]
        out = []
        for name in self.selected_names():
            if self.fmt_var.get() == "stem":
                out.append(os.path.splitext(name)[0])
            elif self.fmt_var.get() == "path":
                out.append(os.path.join(self.folder, name))
            else:
                out.append(name)
        return sep.join(out)

    def update_preview(self):
        text = self.build_output() or "—"
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", "复制预览：\n" + text)
        self.preview.configure(state="disabled")

    def copy_selected(self):
        out = self.build_output()
        if not out:
            return
        self.clipboard_clear()
        self.clipboard_append(out)
        self.update()  # 确保关闭前剪贴板内容保留
        self.stat_var.set(f"✓ 已复制 {len(self.selected_names())} 个文件名到剪贴板")
        self.after(2000, self._sync_stats)


if __name__ == "__main__":
    App().mainloop()
