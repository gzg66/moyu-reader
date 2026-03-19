"""
小说阅读器 - 摸鱼神器
支持：网页小说抓取、TXT导入、背景透明、字体/行距调节、老板键
右键菜单调出所有设置，界面极简
"""

import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import chardet
import requests
import ttkbootstrap as ttk
from ttkbootstrap.constants import (
    PRIMARY, INFO,
    LEFT, RIGHT, BOTH, X, Y, W,
    CENTER, BOTTOM,
)
from bs4 import BeautifulSoup
from urllib.parse import urljoin



# ═══════════════════════════════════════════════════════
#                     网页抓取器
# ═══════════════════════════════════════════════════════
class WebFetcher:
    """抓取网页小说内容"""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    @staticmethod
    def fetch(url: str) -> dict:
        resp = requests.get(url, headers=WebFetcher.HEADERS, timeout=15)
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        title = WebFetcher._extract_title(soup)
        content = WebFetcher._extract_content(soup)
        next_url = WebFetcher._find_next_link(soup)
        if next_url:
            next_url = urljoin(url, next_url)

        return {"title": title, "content": content, "next_url": next_url}

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:
        for tag in ("h1", "h2", "h3"):
            el = soup.find(tag)
            if el:
                return el.get_text(strip=True)
        t = soup.find("title")
        return t.get_text(strip=True) if t else "未知标题"

    @staticmethod
    def _extract_content(soup: BeautifulSoup) -> str:
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        ids = [
            "content", "chaptercontent", "booktxt", "book_text",
            "htmlContent", "chapter-content", "articlecontent",
            "TextContent", "text_content", "nr_title", "nr1",
        ]
        classes = [
            "content", "chapter_content", "book_text", "readcontent",
            "read-content", "article-content", "novelcontent",
            "txtnav", "contentbox", "RBGBookDetailcontent",
        ]

        best, best_len = None, 0

        for cid in ids:
            el = soup.find(id=cid)
            if el:
                txt = el.get_text("\n", strip=True)
                if len(txt) > best_len:
                    best, best_len = txt, len(txt)

        for cls in classes:
            for el in soup.find_all(class_=cls):
                txt = el.get_text("\n", strip=True)
                if len(txt) > best_len:
                    best, best_len = txt, len(txt)

        if best_len < 200:
            p_text = "\n".join(
                p.get_text(strip=True)
                for p in soup.find_all("p")
                if len(p.get_text(strip=True)) > 10
            )
            if len(p_text) > best_len:
                best, best_len = p_text, len(p_text)

        if best_len < 100:
            body = soup.find("body")
            if body:
                best = body.get_text("\n", strip=True)

        return best or "未能提取到正文内容，请检查 URL 是否正确。"

    @staticmethod
    def _find_next_link(soup: BeautifulSoup) -> str | None:
        patterns = [
            re.compile(r"下一[页章节篇]"),
            re.compile(r"next\s*(page|chapter)", re.IGNORECASE),
        ]
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            for pat in patterns:
                if pat.search(text):
                    return a["href"]
        for a in soup.find_all("a", href=True, id=re.compile(r"next", re.IGNORECASE)):
            return a["href"]
        return None


# ═══════════════════════════════════════════════════════
#                    TXT 分章管理
# ═══════════════════════════════════════════════════════
class TxtBook:
    """管理 TXT 文件的加载和分章/分页"""

    def __init__(self, filepath: str, chars_per_page: int = 3000):
        self.filepath = filepath
        self.chars_per_page = chars_per_page
        self.chapters: list[tuple[str, str]] = []
        self.current_index = 0
        self._load()

    def _load(self):
        with open(self.filepath, "rb") as f:
            raw = f.read()
        enc = chardet.detect(raw).get("encoding", "utf-8") or "utf-8"
        text = raw.decode(enc, errors="replace")

        pattern = re.compile(
            r"^[ \t]*(第[零一二三四五六七八九十百千万\d]+[章节回卷集部篇].*)",
            re.MULTILINE,
        )
        splits = list(pattern.finditer(text))

        if len(splits) >= 2:
            for i, m in enumerate(splits):
                title = m.group(1).strip()
                start = m.end()
                end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
                content = text[start:end].strip()
                if content:
                    self.chapters.append((title, content))
        else:
            for i in range(0, len(text), self.chars_per_page):
                page = i // self.chars_per_page + 1
                self.chapters.append((f"第 {page} 页", text[i : i + self.chars_per_page]))

    @property
    def total(self) -> int:
        return len(self.chapters)

    def current(self) -> tuple[str, str]:
        if 0 <= self.current_index < self.total:
            return self.chapters[self.current_index]
        return ("", "")

    def has_next(self) -> bool:
        return self.current_index < self.total - 1

    def has_prev(self) -> bool:
        return self.current_index > 0

    def go_next(self):
        if self.has_next():
            self.current_index += 1

    def go_prev(self):
        if self.has_prev():
            self.current_index -= 1

    def go_to(self, idx: int):
        if 0 <= idx < self.total:
            self.current_index = idx


# ═══════════════════════════════════════════════════════
#                     阅读器主窗口
# ═══════════════════════════════════════════════════════
class ReaderApp:
    # 默认配置
    DEFAULT_FONT_FAMILY = "Microsoft YaHei"
    DEFAULT_FONT_SIZE = 10
    DEFAULT_LINE_SPACING = 2
    FONT_CHOICES = [
        "Microsoft YaHei", "SimSun", "KaiTi", "SimHei",
        "FangSong", "Consolas", "Courier New", "Arial",
    ]

    def __init__(self):
        self.root = ttk.Window(
            title="小说阅读器",
            themename="litera",
            size=(860, 680),
            minsize=(400, 300),
        )
        self.root.place_window_center()

        # ── 状态变量 ──
        self.current_url = ""
        self.next_url: str | None = None
        self.history: list[str] = []
        self.txt_book: TxtBook | None = None
        self.is_web_mode = True
        self._fetching = False
        self._transparent_bg = False      # 是否开启背景透明
        self._toolbar_visible = True      # 顶栏是否可见
        self._opacity = 100
        self._drag_x = 0                 # 拖动窗口用
        self._drag_y = 0

        # ── tkinter 变量 ──
        self.var_font_family = tk.StringVar(value=self.DEFAULT_FONT_FAMILY)
        self.var_font_size = tk.IntVar(value=self.DEFAULT_FONT_SIZE)
        self.var_line_spacing = tk.IntVar(value=self.DEFAULT_LINE_SPACING)
        self.var_topmost = tk.BooleanVar(value=False)
        self.var_status = tk.StringVar(value="就绪 — 右键打开菜单 | 输入网址或打开TXT")
        self.var_url = tk.StringVar()
        self.var_page_info = tk.StringVar()

        self._build_ui()
        self._build_context_menu()
        self._bind_keys()

    # ────────────────────────────────────
    #              界面构建
    # ────────────────────────────────────
    def _build_ui(self):
        # 用原生 tk.Frame 作容器（ttk.Frame 不支持直接改 bg，透明会失效）
        self._default_bg = self.root.cget("bg")

        # ═══ 顶部工具栏（可隐藏） ═══
        self.toolbar = tk.Frame(self.root, bg=self._default_bg, padx=5, pady=3)
        self.toolbar.pack(fill=X)

        tk.Label(self.toolbar, text="网址:", bg=self._default_bg,
                 font=("Microsoft YaHei", 10)).pack(side=LEFT, padx=(0, 4))
        self.entry_url = ttk.Entry(self.toolbar, textvariable=self.var_url, width=55)
        self.entry_url.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        self.entry_url.bind("<Return>", lambda e: self._on_fetch())

        self.btn_fetch = ttk.Button(
            self.toolbar, text="抓取", bootstyle=PRIMARY, width=6, command=self._on_fetch,
        )
        self.btn_fetch.pack(side=LEFT, padx=2)

        self.btn_open = ttk.Button(
            self.toolbar, text="打开TXT", bootstyle=INFO, width=8, command=self._on_open_txt,
        )
        self.btn_open.pack(side=LEFT, padx=2)

        # ═══ 标题 ═══
        self.lbl_title = tk.Label(
            self.root, text="", font=("Microsoft YaHei", 14, "bold"),
            anchor=CENTER, bg=self._default_bg, fg="#333333", pady=4,
        )
        self.lbl_title.pack(fill=X)

        # ═══ 正文阅读区 ═══
        self.text_frame = tk.Frame(self.root, bg=self._default_bg)
        self.text_frame.pack(fill=BOTH, expand=True, padx=4, pady=2)

        self.scrollbar = ttk.Scrollbar(self.text_frame, bootstyle="round")
        self.scrollbar.pack(side=RIGHT, fill=Y)

        self.text = tk.Text(
            self.text_frame,
            wrap=tk.WORD,
            font=(self.DEFAULT_FONT_FAMILY, self.DEFAULT_FONT_SIZE),
            spacing1=0,
            spacing2=self.DEFAULT_LINE_SPACING,
            spacing3=0,
            padx=16,
            pady=10,
            relief=tk.FLAT,
            bd=0,
            bg="#FFFFFF",
            fg="#333333",
            selectbackground="#B3D9FF",
            insertwidth=0,
            cursor="arrow",
            yscrollcommand=self.scrollbar.set,
        )
        self.text.pack(side=LEFT, fill=BOTH, expand=True)
        self.scrollbar.config(command=self.text.yview)
        self.text.config(state=tk.DISABLED)

        # ═══ 底部翻页栏 ═══
        self.nav_bar = tk.Frame(self.root, bg=self._default_bg, padx=5, pady=2)
        self.nav_bar.pack(fill=X)

        self.btn_prev = ttk.Button(
            self.nav_bar, text="← 上一页", width=10, command=self._on_prev,
        )
        self.btn_prev.pack(side=LEFT)
        self.btn_prev.config(state=tk.DISABLED)

        self.lbl_page_info = tk.Label(
            self.nav_bar, textvariable=self.var_page_info,
            anchor=CENTER, bg=self._default_bg, font=("Microsoft YaHei", 10),
        )
        self.lbl_page_info.pack(side=LEFT, fill=X, expand=True)

        self.btn_next = ttk.Button(
            self.nav_bar, text="下一页 →", width=10, command=self._on_next,
        )
        self.btn_next.pack(side=RIGHT)
        self.btn_next.config(state=tk.DISABLED)

        # ═══ 状态栏 ═══
        self.status_bar = tk.Label(
            self.root, textvariable=self.var_status,
            relief=tk.SUNKEN, anchor=W, padx=6, pady=2,
            font=("Microsoft YaHei", 9), bg=self._default_bg, fg="#777777",
        )
        self.status_bar.pack(fill=X, side=BOTTOM)

    # ────────────────────────────────────
    #           右键菜单（替代设置面板）
    # ────────────────────────────────────
    def _build_context_menu(self):
        self.ctx_menu = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei", 10))

        # ── 字体子菜单 ──
        font_menu = tk.Menu(self.ctx_menu, tearoff=0, font=("Microsoft YaHei", 10))
        for f in self.FONT_CHOICES:
            font_menu.add_radiobutton(
                label=f, variable=self.var_font_family, value=f,
                command=self._apply_font,
            )
        self.ctx_menu.add_cascade(label="字体", menu=font_menu)

        # ── 字号子菜单 ──
        size_menu = tk.Menu(self.ctx_menu, tearoff=0, font=("Microsoft YaHei", 10))
        for s in (4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20, 24, 28):
            size_menu.add_radiobutton(
                label=f"{s} px", variable=self.var_font_size, value=s,
                command=self._apply_font,
            )
        self.ctx_menu.add_cascade(label="字号", menu=size_menu)

        # ── 行距子菜单 ──
        spacing_menu = tk.Menu(self.ctx_menu, tearoff=0, font=("Microsoft YaHei", 10))
        for sp in (0, 1, 2, 3, 4, 6, 8, 10, 14, 18):
            spacing_menu.add_radiobutton(
                label=f"{sp} px", variable=self.var_line_spacing, value=sp,
                command=self._apply_font,
            )
        self.ctx_menu.add_cascade(label="行距", menu=spacing_menu)

        self.ctx_menu.add_separator()

        # ── 透明度子菜单 ──
        opacity_menu = tk.Menu(self.ctx_menu, tearoff=0, font=("Microsoft YaHei", 10))
        for pct in (100, 90, 80, 70, 60, 50, 40, 30, 20, 10):
            opacity_menu.add_command(
                label=f"{pct}%",
                command=lambda p=pct: self._set_opacity(p),
            )
        self.ctx_menu.add_cascade(label="窗口透明度", menu=opacity_menu)

        # ── 摸鱼模式 ──
        self.ctx_menu.add_command(label="⬜ 摸鱼模式（半透明+极简）", command=self._toggle_transparent_bg)

        # ── 窗口置顶 ──
        self.ctx_menu.add_checkbutton(
            label="窗口置顶", variable=self.var_topmost,
            command=self._on_topmost_changed,
        )

        self.ctx_menu.add_separator()

        # ── 显示/隐藏工具栏 ──
        self.ctx_menu.add_command(label="显示/隐藏工具栏", command=self._toggle_toolbar)

        # ── 老板键 ──
        self.ctx_menu.add_command(label="老板键 (Esc)", command=self._on_boss_key)

    def _show_context_menu(self, event):
        """弹出右键菜单前，更新摸鱼模式的标签"""
        label = "✅ 摸鱼模式（半透明+极简）" if self._transparent_bg else "⬜ 摸鱼模式（半透明+极简）"
        self.ctx_menu.entryconfig(5, label=label)
        self.ctx_menu.post(event.x_root, event.y_root)

    def _show_context_menu_center(self, _event=None):
        """键盘 F2 在窗口中央弹出菜单"""
        label = "✅ 摸鱼模式（半透明+极简）" if self._transparent_bg else "⬜ 摸鱼模式（半透明+极简）"
        self.ctx_menu.entryconfig(5, label=label)
        x = self.root.winfo_rootx() + self.root.winfo_width() // 2
        y = self.root.winfo_rooty() + self.root.winfo_height() // 2
        self.ctx_menu.post(x, y)

    # ────────────────────────────────────
    #              快捷键
    # ────────────────────────────────────
    def _bind_keys(self):
        self.root.bind("<Escape>", lambda e: self._on_boss_key())
        self.root.bind("<Left>", lambda e: self._on_prev())
        self.root.bind("<Right>", lambda e: self._on_next())
        self.root.bind("<Control-o>", lambda e: self._on_open_txt())
        self.root.bind("<MouseWheel>", self._on_mousewheel)
        self.text.bind("<MouseWheel>", self._on_mousewheel)
        # 上/下方向键滚动正文
        self.root.bind("<Up>", lambda e: self.text.yview_scroll(-3, "units"))
        self.root.bind("<Down>", lambda e: self.text.yview_scroll(3, "units"))

        # 右键菜单（鼠标 + 键盘 F2）
        self.root.bind("<Button-3>", self._show_context_menu)
        self.text.bind("<Button-3>", self._show_context_menu)
        self.root.bind("<F2>", self._show_context_menu_center)

    def _on_mousewheel(self, event):
        self.text.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ────────────────────────────────────
    #            背景透明 & 外观
    # ────────────────────────────────────
    def _toggle_transparent_bg(self):
        """切换摸鱼模式：去标题栏 + 半透明 + 极简布局"""
        self._transparent_bg = not self._transparent_bg
        if self._transparent_bg:
            # ── 开启摸鱼 ──
            self.root.overrideredirect(True)           # 去标题栏
            self.root.attributes("-alpha", 0.35)       # 半透明
            self.root.attributes("-topmost", True)     # 置顶
            # 暗色背景 + 浅色文字，降低存在感
            self.root.configure(bg="#1E1E1E")
            self.text.config(bg="#1E1E1E", fg="#CCCCCC",
                             selectbackground="#444444")
            self.text_frame.config(bg="#1E1E1E")
            # 隐藏多余控件
            self.scrollbar.pack_forget()
            self.toolbar.pack_forget()
            self.lbl_title.pack_forget()
            self.nav_bar.pack_forget()
            self.status_bar.pack_forget()
            self._toolbar_visible = False
            # 拖动窗口
            self.text.bind("<ButtonPress-1>", self._on_drag_start)
            self.text.bind("<B1-Motion>", self._on_drag_motion)
        else:
            # ── 关闭摸鱼 ──
            self.text.unbind("<ButtonPress-1>")
            self.text.unbind("<B1-Motion>")
            self.root.overrideredirect(False)
            self.root.attributes("-alpha", self._opacity / 100.0)
            self.root.attributes("-topmost", self.var_topmost.get())
            # 恢复配色
            self.root.configure(bg=self._default_bg)
            self.text.config(bg="#FFFFFF", fg="#333333",
                             selectbackground="#B3D9FF")
            self.text_frame.config(bg=self._default_bg)
            self.lbl_title.config(fg="#333333")
            self.status_bar.config(fg="#777777")
            self._rebuild_layout()
            self._toolbar_visible = True

    # ── 拖动窗口（无标题栏时） ──
    def _on_drag_start(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag_motion(self, event):
        x = self.root.winfo_x() + (event.x - self._drag_x)
        y = self.root.winfo_y() + (event.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")

    def _rebuild_layout(self):
        """将所有控件按正确顺序重新 pack"""
        for w in (self.toolbar, self.lbl_title, self.text_frame,
                  self.nav_bar, self.status_bar):
            w.pack_forget()
        self.status_bar.pack(fill=X, side=BOTTOM)
        self.toolbar.pack(fill=X)
        self.lbl_title.pack(fill=X)
        self.text_frame.pack(fill=BOTH, expand=True, padx=4, pady=2)
        self.nav_bar.pack(fill=X)
        self.scrollbar.pack(side=RIGHT, fill=Y, before=self.text)

    def _set_opacity(self, pct: int):
        self._opacity = pct
        self.root.attributes("-alpha", pct / 100.0)
        self.var_status.set(f"窗口透明度: {pct}%")

    def _on_topmost_changed(self):
        self.root.attributes("-topmost", self.var_topmost.get())

    def _toggle_toolbar(self):
        """显示/隐藏顶部工具栏"""
        if self._toolbar_visible:
            self.toolbar.pack_forget()
            self._toolbar_visible = False
            self.var_status.set("工具栏已隐藏 — 右键菜单可恢复")
        else:
            # 重新 pack 到最顶部
            self.toolbar.pack(fill=X, before=self.lbl_title)
            self._toolbar_visible = True
            self.var_status.set("工具栏已显示")

    def _on_boss_key(self):
        if self._transparent_bg:
            # 摸鱼模式下 overrideredirect(True) 导致 iconify() 在 Windows 上无效
            # 先临时关闭 overrideredirect 再最小化，恢复时重新启用
            self.root.overrideredirect(False)
            self.root.iconify()
            self.root.bind("<Map>", self._on_restore_from_boss)
        else:
            self.root.iconify()

    def _on_restore_from_boss(self, event=None):
        """从老板键最小化恢复后，重新启用摸鱼模式的无边框 + 半透明"""
        if event and event.widget != self.root:
            return
        self.root.unbind("<Map>")
        if self._transparent_bg:
            self.root.overrideredirect(True)
            self.root.attributes("-alpha", 0.35)
            self.root.attributes("-topmost", True)

    # ────────────────────────────────────
    #              字体应用
    # ────────────────────────────────────
    def _apply_font(self, *_args):
        family = self.var_font_family.get()
        size = self.var_font_size.get()
        spacing = self.var_line_spacing.get()
        self.text.config(font=(family, size), spacing2=spacing)

    # ────────────────────────────────────
    #             内容展示
    # ────────────────────────────────────
    def _display(self, title: str, content: str):
        self.lbl_title.config(text=title)

        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        for line in content.split("\n"):
            line = line.strip()
            if line:
                self.text.insert(tk.END, "　　" + line + "\n")

        self.text.config(state=tk.DISABLED)
        self.text.yview_moveto(0)

    # ────────────────────────────────────
    #             网页抓取
    # ────────────────────────────────────
    def _on_fetch(self):
        url = self.var_url.get().strip()
        if not url:
            self.var_status.set("请输入网址")
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self.var_url.set(url)
        if self._fetching:
            return

        self.is_web_mode = True
        self.txt_book = None
        self._fetching = True
        self.btn_fetch.config(state=tk.DISABLED)
        self.var_status.set(f"正在抓取: {url} ...")

        def _do():
            try:
                result = WebFetcher.fetch(url)
                self.root.after(0, lambda: self._on_fetch_done(url, result))
            except Exception as err:
                msg = str(err)
                self.root.after(0, lambda: self._on_fetch_error(msg))

        threading.Thread(target=_do, daemon=True).start()

    def _on_fetch_done(self, url: str, result: dict):
        self._fetching = False
        self.btn_fetch.config(state=tk.NORMAL)

        self.current_url = url
        self.next_url = result.get("next_url")

        self._display(result["title"], result["content"])

        self.btn_prev.config(state=tk.NORMAL if self.history else tk.DISABLED)
        self.btn_next.config(state=tk.NORMAL if self.next_url else tk.DISABLED)
        self.var_page_info.set("")
        self.var_status.set(f"已加载: {result['title']}")

    def _on_fetch_error(self, msg: str):
        self._fetching = False
        self.btn_fetch.config(state=tk.NORMAL)
        self.var_status.set(f"抓取失败: {msg}")
        messagebox.showerror("抓取失败", f"无法获取页面内容：\n{msg}")

    # ────────────────────────────────────
    #             TXT 文件
    # ────────────────────────────────────
    def _on_open_txt(self):
        filepath = filedialog.askopenfilename(
            title="打开小说文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
        )
        if not filepath:
            return
        try:
            self.txt_book = TxtBook(filepath)
            self.is_web_mode = False
            self.next_url = None
            self.history.clear()
            self._show_txt_page()
            self.var_status.set(
                f"已加载: {os.path.basename(filepath)} ({self.txt_book.total} 章/页)"
            )
        except Exception as e:
            messagebox.showerror("打开失败", f"无法读取文件：\n{e}")

    def _show_txt_page(self):
        if not self.txt_book:
            return
        title, content = self.txt_book.current()
        self._display(title, content)
        self.btn_prev.config(state=tk.NORMAL if self.txt_book.has_prev() else tk.DISABLED)
        self.btn_next.config(state=tk.NORMAL if self.txt_book.has_next() else tk.DISABLED)
        self.var_page_info.set(f"{self.txt_book.current_index + 1} / {self.txt_book.total}")

    # ────────────────────────────────────
    #               翻页
    # ────────────────────────────────────
    def _on_prev(self):
        if not self.is_web_mode and self.txt_book:
            self.txt_book.go_prev()
            self._show_txt_page()
        elif self.is_web_mode and self.history:
            url = self.history.pop()
            self.var_url.set(url)
            self._on_fetch()

    def _on_next(self):
        if not self.is_web_mode and self.txt_book:
            self.txt_book.go_next()
            self._show_txt_page()
        elif self.is_web_mode and self.next_url:
            self.history.append(self.current_url)
            self.var_url.set(self.next_url)
            self._on_fetch()

    # ────────────────────────────────────
    #               启动
    # ────────────────────────────────────
    def run(self):
        self.root.mainloop()


# ═══════════════════════════════════════════════════════
#                        入口
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    app = ReaderApp()
    app.run()
