# -*- coding: utf-8 -*-
"""万年历桌面界面（Tkinter）。

由 wannianli.py 负责入口调用；这里只放界面实现，显示规则统一取自 lunar_service。
需要 tkinter（Python 官方发行版自带）。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from datetime import date
from tkinter import filedialog, font as tkfont, messagebox, ttk

from lunar_service import (
    DisplayOptions,
    get_day_info,
    lunar_year_summary,
    month_grid,
    year_festival_summary,
)
from theme import (
    BG,
    BORDER,
    CARD,
    CATEGORY_COLORS,
    CATEGORY_LABELS,
    HEADER_BG,
    HEADER_TEXT,
    HOVER_BG,
    TEXT,
    TEXT_OUT,
    TEXT_SECOND,
    TEXT_WEEKEND,
    TODAY_BG,
    TODAY_BORDER,
)
import pdf_exporter

MIN_YEAR, MAX_YEAR = 1900, 2100
WEEK_HEADERS = ("日", "一", "二", "三", "四", "五", "六")


_FONT_CANDIDATES = ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
                    "Noto Sans CJK SC", "Microsoft JhengHei", "SimHei", "SimSun")
_FONT_FAMILY: str | None = None


def _font_family() -> str:
    """首次调用时探测系统中文字体（必须在创建 Tk 根窗口之后）。"""
    global _FONT_FAMILY
    if _FONT_FAMILY is None:
        try:
            families = set(tkfont.families())
        except tk.TclError:
            families = set()
        _FONT_FAMILY = next((n for n in _FONT_CANDIDATES if n in families), "TkDefaultFont")
    return _FONT_FAMILY


def f(size: int, weight: str = "normal") -> tuple:
    return (_font_family(), size, weight)


def line_px(font_spec: tuple) -> int:
    """按实际字体度量返回行高像素（自动适配系统 DPI 缩放）。"""
    return tkfont.Font(font=font_spec).metrics("linespace")


def weeks_in_month(year: int, month: int) -> int:
    """该月在「周日起始」网格中实际占用的行数（4~6）。"""
    import calendar as _calendar

    first_weekday = (date(year, month, 1).weekday() + 1) % 7      # 0=周日
    days = _calendar.monthrange(year, month)[1]
    return (first_weekday + days + 6) // 7


class CalendarApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("万年历 · 公历 / 农历双显")
        self.configure(bg=BG)
        self.minsize(880, 620)
        self.update_idletasks()
        width = min(1240, max(900, self.winfo_screenwidth() - 60))
        height = min(1000, max(660, self.winfo_screenheight() - 80))
        self.geometry(f"{width}x{height}")

        today = date.today()
        self.year = today.year
        self.month = today.month
        self.view = tk.StringVar(value="month")
        self.show_public = tk.BooleanVar(value=True)
        self.festival_first = tk.BooleanVar(value=True)
        self.selected: date | None = today
        self.status_var = tk.StringVar()

        self._configure_styles()
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()
        self._bind_keys()
        self._render()
        self._update_status(self._info(today))

    # ------------------------------------------------------------------ 构建
    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        if "vista" in (style.theme_use() or "") or sys.platform == "win32":
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass
        style.configure("Tool.TButton", font=f(10), padding=(10, 5))
        style.configure("Nav.TButton", font=f(11, "bold"), padding=(8, 4))
        style.configure("Go.TButton", font=f(10, "bold"), padding=(12, 5))

    def _build_toolbar(self) -> None:
        bar = tk.Frame(self, bg=BG, highlightthickness=0)
        bar.pack(fill="x", padx=12, pady=(10, 4))

        ttk.Button(bar, text="◀", width=3, style="Nav.TButton",
                   command=self.prev_period).pack(side="left")
        ttk.Button(bar, text="▶", width=3, style="Nav.TButton",
                   command=self.next_period).pack(side="left", padx=(4, 10))

        tk.Label(bar, text="年", bg=BG, font=f(10)).pack(side="left")
        self.year_var = tk.StringVar(value=str(self.year))
        self.year_spin = ttk.Spinbox(bar, from_=MIN_YEAR, to=MAX_YEAR, width=6,
                                     font=f(11, "bold"), justify="center",
                                     textvariable=self.year_var,
                                     command=self._on_year_spin)
        self.year_spin.pack(side="left", padx=(6, 10))
        self.year_spin.bind("<Return>", lambda e: self._on_year_spin())

        tk.Label(bar, text="月", bg=BG, font=f(10)).pack(side="left")
        self.month_var = tk.StringVar(value=str(self.month))
        self.month_combo = ttk.Combobox(bar, width=4, state="readonly",
                                        font=f(11, "bold"), justify="center",
                                        textvariable=self.month_var,
                                        values=[str(i) for i in range(1, 13)])
        self.month_combo.pack(side="left", padx=(6, 12))
        self.month_combo.bind("<<ComboboxSelected>>", lambda e: self._on_month_combo())

        ttk.Button(bar, text="今天", style="Tool.TButton",
                   command=self.go_today).pack(side="left")

        tk.Frame(bar, width=1, height=22, bg="#ccd2da").pack(side="left", padx=12)

        self._seg_buttons = {}
        seg = tk.Frame(bar, bg=BG)
        seg.pack(side="left")
        for text, mode in (("月视图", "month"), ("年视图", "year")):
            btn = tk.Button(seg, text=text, font=f(10), bd=0, padx=14, pady=5,
                            cursor="hand2", command=lambda m=mode: self.set_view(m))
            btn.pack(side="left", padx=(0, 6))
            self._seg_buttons[mode] = btn

        tk.Frame(bar, width=1, height=22, bg="#ccd2da").pack(side="left", padx=12)

        tk.Checkbutton(bar, text="显示公历节日", variable=self.show_public,
                       bg=BG, font=f(10), activebackground=BG,
                       command=self._render).pack(side="left")
        tk.Checkbutton(bar, text="节日优先于节气", variable=self.festival_first,
                       bg=BG, font=f(10), activebackground=BG,
                       command=self._render).pack(side="left", padx=(10, 0))

        self.export_btn = ttk.Button(bar, text="导出 PDF 年历", style="Go.TButton",
                                     command=self.open_export_dialog)
        self.export_btn.pack(side="right")
        self._paint_seg()

    def _build_body(self) -> None:
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=12, pady=(2, 6))

        self.canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.vsb.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.content = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda e: self._sync_size())
        self.canvas.bind("<Configure>", lambda e: self._sync_size())
        self._bind_mousewheel(self.canvas)

    def _sync_size(self) -> None:
        """内容比窗口矮时撑满窗口（月视图随之铺满），更高时保留滚动。"""
        width = self.canvas.winfo_width()
        height = max(self.canvas.winfo_height(), self.content.winfo_reqheight())
        if getattr(self, "_last_size", None) == (width, height):
            return
        self._last_size = (width, height)
        self.canvas.itemconfig(self._win, width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))

    def _build_statusbar(self) -> None:
        bottom = tk.Frame(self, bg="#ffffff", highlightthickness=1,
                          highlightbackground=BORDER)
        bottom.pack(fill="x", padx=12, pady=(0, 10))

        legend = tk.Frame(bottom, bg="#ffffff")
        legend.pack(fill="x", padx=10, pady=(4, 2))
        tk.Label(legend, text="■", fg=CATEGORY_COLORS["traditional"], bg="#ffffff",
                 font=f(9)).pack(side="left")
        tk.Label(legend, text="传统节日  ", fg=TEXT_SECOND, bg="#ffffff",
                 font=f(9)).pack(side="left")
        tk.Label(legend, text="■", fg=CATEGORY_COLORS["jieqi"], bg="#ffffff",
                 font=f(9)).pack(side="left")
        tk.Label(legend, text="节气  ", fg=TEXT_SECOND, bg="#ffffff",
                 font=f(9)).pack(side="left")
        tk.Label(legend, text="■", fg=CATEGORY_COLORS["public"], bg="#ffffff",
                 font=f(9)).pack(side="left")
        tk.Label(legend, text="公历节日  ", fg=TEXT_SECOND, bg="#ffffff",
                 font=f(9)).pack(side="left")
        tk.Label(legend, text="■", fg=TEXT_WEEKEND, bg="#ffffff",
                 font=f(9)).pack(side="left")
        tk.Label(legend, text="周末 / 农历", fg=TEXT_SECOND, bg="#ffffff",
                 font=f(9)).pack(side="left")

        tk.Frame(bottom, height=1, bg=BORDER).pack(fill="x", padx=10)
        tk.Label(bottom, textvariable=self.status_var, bg="#ffffff", fg=TEXT,
                 font=f(9), anchor="w", justify="left").pack(fill="x", padx=10, pady=(4, 6))

    def _bind_keys(self) -> None:
        self.bind("<Left>", lambda e: self.prev_period())
        self.bind("<Right>", lambda e: self.next_period())
        self.bind("<Home>", lambda e: self.go_today())
        self.bind("<F5>", lambda e: self._render())
        for key in ("Up", "Down", "Prior", "Next"):
            self.bind(f"<{key}>", self._on_special_key)

    def _on_special_key(self, event) -> None:
        if event.keysym in ("Up", "Prior"):
            self.next_period()
        else:
            self.prev_period()

    def _bind_mousewheel(self, _widget) -> None:
        """整窗口滚轮均作用于日历画布。"""
        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event) -> None:
        try:
            first, last = self.canvas.yview()
        except tk.TclError:
            return
        if first <= 0 and last >= 1:          # 内容不足一屏时不滚动
            return
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ------------------------------------------------------------------ 数据
    @property
    def options(self) -> DisplayOptions:
        return DisplayOptions(show_public=self.show_public.get(),
                              festival_first=self.festival_first.get())

    def _info(self, d: date):
        return get_day_info(d, self.options)

    # ------------------------------------------------------------------ 交互
    def set_view(self, mode: str) -> None:
        if self.view.get() == mode:
            return
        self.view.set(mode)
        self._paint_seg()
        self._render()

    def _paint_seg(self) -> None:
        active = self.view.get()
        for mode, btn in self._seg_buttons.items():
            if mode == active:
                btn.configure(bg="#1a73e8", fg="#ffffff", activebackground="#1a73e8")
            else:
                btn.configure(bg="#e8ecf1", fg="#3c4653", activebackground="#dfe4ea")

    def _set_year(self, year: int) -> None:
        self.year = max(MIN_YEAR, min(MAX_YEAR, year))
        self.year_var.set(str(self.year))
        self._render()

    def _on_year_spin(self) -> None:
        value = self.year_spin.get().strip()
        try:
            year = int(value)
        except ValueError:
            self.year_spin.set(str(self.year))
            return
        self._set_year(year)

    def _on_month_combo(self) -> None:
        try:
            self.month = int(self.month_var.get())
        except ValueError:
            return
        self.view.set("month")
        self._paint_seg()
        self._render()

    def prev_period(self) -> None:
        if self.view.get() == "year":
            self._set_year(self.year - 1)
        else:
            self._shift_month(-1)

    def next_period(self) -> None:
        if self.view.get() == "year":
            self._set_year(self.year + 1)
        else:
            self._shift_month(1)

    def _shift_month(self, delta: int) -> None:
        m = self.month - 1 + delta
        y = self.year + m // 12
        m = m % 12
        self.year = max(MIN_YEAR, min(MAX_YEAR, y))
        self.month = m + 1
        self.year_var.set(str(self.year))
        self.month_var.set(str(self.month))
        self._render()

    def go_today(self) -> None:
        today = date.today()
        self.year, self.month = today.year, today.month
        self.year_var.set(str(self.year))
        self.month_var.set(str(self.month))
        self.selected = today
        self._render()
        self._update_status(self._info(today))

    def jump_to(self, d: date) -> None:
        if d.month != self.month or d.year != self.year:
            self.year, self.month = d.year, d.month
            self.year_var.set(str(self.year))
            self.month_var.set(str(self.month))
        self.selected = d
        self._render()
        self._update_status(self._info(d))

    def _update_status(self, info) -> None:
        label = CATEGORY_LABELS.get(info.category, "")
        detail = info.tooltip.replace("\n", "　·　")
        self.status_var.set(f"{detail}　·　第二行显示：{label}「{info.lunar_text}」")

    # ------------------------------------------------------------------ 渲染
    def _render(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()
        try:
            self.year_spin.set(str(self.year))
        except tk.TclError:
            pass
        self.month_var.set(str(self.month))

        summary = tk.Frame(self.content, bg=BG)
        summary.pack(fill="x", pady=(0, 8))
        title = f"{self.year} 年" + (f" {self.month} 月" if self.view.get() == "month" else "")
        tk.Label(summary, text=title, font=f(18, "bold"), bg=BG,
                 fg="#1f2933").pack(side="left")
        tk.Label(summary, text=f"   {lunar_year_summary(self.year)}", font=f(11),
                 bg=BG, fg=TEXT_SECOND).pack(side="left")
        fest = "   ".join(f"{n}{d.month}/{d.day}" for n, d in year_festival_summary(self.year, self.options))
        if fest:
            tk.Label(summary, text=fest, font=f(10), bg=BG,
                     fg=CATEGORY_COLORS["traditional"]).pack(side="right")

        if self.view.get() == "month":
            self._render_month_view()
        else:
            self._render_year_view()
        self.content.update_idletasks()
        self._last_size = None
        self._sync_size()
        self.canvas.yview_moveto(0)

    def _render_month_view(self) -> None:
        header_h = line_px(f(11, "bold")) + 10
        row_h = max(76, line_px(f(17, "bold")) + line_px(f(10)) + 26)

        board = tk.Frame(self.content, bg=BORDER)
        board.pack(fill="both", expand=True)
        board.columnconfigure(tuple(range(7)), weight=1, uniform="col")
        board.grid_rowconfigure(0, weight=0, minsize=header_h)
        for r in range(1, 7):
            board.grid_rowconfigure(r, weight=1, minsize=row_h, uniform="row")

        for i, name in enumerate(WEEK_HEADERS):
            fg = TEXT_WEEKEND if i in (0, 6) else HEADER_TEXT
            tk.Label(board, text=name, bg=HEADER_BG, fg=fg, font=f(11, "bold"),
                     pady=8).grid(row=0, column=i, sticky="nsew", padx=(1 if i else 0, 1),
                                  pady=(0, 1))

        grid = month_grid(self.year, self.month, self.options)
        for r in range(6):
            for col in range(7):
                info = grid[r][col]
                cell = self._make_cell(board, info, "large")
                cell.grid_propagate(False)
                cell.grid(row=r + 1, column=col, sticky="nsew",
                          padx=(1 if col == 0 else 0, 1), pady=(1, 1 if r == 5 else 0))

    def _render_year_view(self) -> None:
        wrap = tk.Frame(self.content, bg=BG)
        wrap.pack(fill="both", expand=True)
        wrap.grid_columnconfigure(tuple(range(4)), weight=1, uniform="ycol")
        for m in range(1, 13):
            r, c = divmod(m - 1, 4)
            block = self._make_small_month(wrap, m)
            block.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)

    def _make_small_month(self, parent, month: int) -> tk.Frame:
        num_ls = line_px(f(9, "bold"))
        lun_ls = line_px(f(7))
        cell_h = num_ls + lun_ls + 4
        cell_w = max(22, int(lun_ls * 2.0))       # 仅作下限，列宽由权重自适应
        head_h = line_px(f(10, "bold")) + 8
        week_h = line_px(f(7, "bold")) + 3

        block = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        head = tk.Frame(block, bg="#f7f9fc", height=head_h)
        head.pack(fill="x")
        head.pack_propagate(False)
        label = tk.Label(head, text=f"{month} 月", bg="#f7f9fc", fg="#1f2933",
                         font=f(10, "bold"), padx=8, cursor="hand2")
        label.pack(side="left")
        for w in (head, label):
            w.bind("<Button-1>", lambda e, mm=month: self._enter_month(mm))

        body = tk.Frame(block, bg=BORDER)
        body.pack(fill="both", expand=True)
        for i, name in enumerate(WEEK_HEADERS):
            tk.Label(body, text=name, bg=HEADER_BG,
                     fg=(TEXT_WEEKEND if i in (0, 6) else HEADER_TEXT),
                     font=f(7, "bold")).grid(row=0, column=i, sticky="nsew")
        grid = month_grid(self.year, month, self.options)
        rows = weeks_in_month(self.year, month)
        grid = grid[:rows]
        for r in range(rows):
            for c in range(7):
                cell = self._make_cell(body, grid[r][c], "small")
                cell.grid(row=r + 1, column=c, sticky="nsew", padx=(0, 1), pady=(0, 1))
        body.grid_rowconfigure(0, weight=0, minsize=week_h)
        for c in range(7):
            body.grid_columnconfigure(c, weight=1, minsize=cell_w)
        for r in range(rows):
            body.grid_rowconfigure(r + 1, weight=1, minsize=cell_h)
        return block

    def _enter_month(self, month: int) -> None:
        self.month = month
        self.month_var.set(str(month))
        self.view.set("month")
        self._paint_seg()
        self._render()

    def _make_cell(self, parent, info, mode: str) -> tk.Frame:
        large = mode == "large"
        num_font = f(17, "bold") if large else f(9, "bold")
        lunar_font = f(10) if large else f(7)
        num_pady = (8, 0) if large else 0
        lunar_pady = (0, 8) if large else 0

        today = info.is_today
        selected = self.selected == info.day and not info.is_out
        base_bg = TODAY_BG if today else CARD

        num_fg = TEXT_OUT if info.is_out else (TEXT_WEEKEND if info.is_weekend else TEXT)
        if today and not info.is_out:
            num_fg = "#1660d0"
        lunar_fg = TEXT_OUT if info.is_out else CATEGORY_COLORS.get(info.category, TEXT_SECOND)

        cell = tk.Frame(parent, bg=base_bg, cursor="hand2")
        if selected:
            cell.configure(highlightthickness=2, highlightbackground="#f0a02a",
                           highlightcolor="#f0a02a")
        elif today:
            cell.configure(highlightthickness=2, highlightbackground=TODAY_BORDER,
                           highlightcolor=TODAY_BORDER)
        else:
            cell.configure(highlightthickness=1, highlightbackground=BORDER)

        lbl_num = tk.Label(cell, text=info.solar_text, bg=base_bg, fg=num_fg, font=num_font)
        lbl_num.grid(row=0, column=0, sticky="nsew", pady=num_pady)
        lbl_lunar = tk.Label(cell, text=info.lunar_text, bg=base_bg, fg=lunar_fg,
                             font=lunar_font)
        lbl_lunar.grid(row=1, column=0, sticky="nsew", pady=lunar_pady)
        cell.grid_rowconfigure(0, weight=3)
        cell.grid_rowconfigure(1, weight=2)
        cell.grid_columnconfigure(0, weight=1)

        widgets = (cell, lbl_num, lbl_lunar)

        def enter(_e=None):
            if today or selected:
                return
            bg = HOVER_BG
            for w in widgets:
                w.configure(bg=bg)

        def leave(_e=None):
            bg = TODAY_BG if today else CARD
            for w in widgets:
                w.configure(bg=bg)

        def click(_e=None):
            if self.view.get() == "year":
                self.jump_to(info.day)
            elif info.is_out:
                self.selected = info.day
                self.jump_to(info.day)
            else:
                self.selected = info.day
                self._render()
                self._update_status(info)
                return
            self._update_status(info)

        for w in widgets:
            w.bind("<Button-1>", click)
            w.bind("<Enter>", enter)
            w.bind("<Leave>", leave)
            if not info.is_out:
                w.bind("<Motion>", lambda _e, i=info: self._update_status(i))
        return cell

    # ------------------------------------------------------------------ 导出
    def open_export_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("导出 PDF 年历")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        body = tk.Frame(dialog, bg=BG, padx=18, pady=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        tk.Label(body, text="导出年份", bg=BG, font=f(10)).grid(row=0, column=0, sticky="w", pady=6)
        year_var = tk.IntVar(value=self.year)
        tk.Spinbox(body, from_=MIN_YEAR, to=MAX_YEAR, width=8, font=f(11),
                   textvariable=year_var, justify="center").grid(row=0, column=1, sticky="w", pady=6)

        tk.Label(body, text="纸张版式", bg=BG, font=f(10)).grid(row=1, column=0, sticky="w", pady=6)
        paper_var = tk.StringVar(value="A4")
        papers = tk.Frame(body, bg=BG)
        papers.grid(row=1, column=1, sticky="w", pady=6)
        tk.Radiobutton(papers, text="A4 横向（每页 6 个月，共 2 页）",
                       variable=paper_var, value="A4", bg=BG, font=f(10),
                       activebackground=BG).pack(anchor="w")
        tk.Radiobutton(papers, text="A3 横向（每页 12 个月，整年 1 页）",
                       variable=paper_var, value="A3", bg=BG, font=f(10),
                       activebackground=BG).pack(anchor="w")

        opt_frame = tk.Frame(body, bg=BG)
        opt_frame.grid(row=2, column=1, sticky="w", pady=6)
        pub_var = tk.BooleanVar(value=self.show_public.get())
        ff_var = tk.BooleanVar(value=self.festival_first.get())
        tk.Checkbutton(opt_frame, text="显示元旦 / 劳动节 / 国庆等公历节日",
                       variable=pub_var, bg=BG, font=f(10), activebackground=BG).pack(anchor="w")
        tk.Checkbutton(opt_frame, text="传统节日优先于节气显示",
                       variable=ff_var, bg=BG, font=f(10), activebackground=BG).pack(anchor="w")

        tk.Label(body, text="保存位置", bg=BG, font=f(10)).grid(row=3, column=0, sticky="w", pady=6)
        path_frame = tk.Frame(body, bg=BG)
        path_frame.grid(row=3, column=1, sticky="ew", pady=6)
        path_var = tk.StringVar(value=os.path.join(os.getcwd(), f"万年历_{self.year}年.pdf"))
        tk.Entry(path_frame, textvariable=path_var, font=f(10), relief="solid",
                 bd=1).pack(side="left", fill="x", expand=True)
        ttk.Button(path_frame, text="浏览…", style="Tool.TButton",
                   command=lambda: path_var.set(
                       filedialog.asksaveasfilename(
                           parent=dialog, defaultextension=".pdf",
                           initialfile=os.path.basename(path_var.get()),
                           filetypes=[("PDF 文档", "*.pdf")]) or path_var.get())
                   ).pack(side="left", padx=(6, 0))

        def do_export() -> None:
            year = int(year_var.get())
            path = path_var.get().strip() or pdf_exporter.build_default_filename(year)
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            try:
                opts = DisplayOptions(show_public=pub_var.get(), festival_first=ff_var.get())
                pdf_exporter.export_year_pdf(year, path, paper_var.get(), opts)
            except Exception as exc:                       # noqa: BLE001
                messagebox.showerror("导出失败", f"{exc}", parent=dialog)
                return
            self.status_var.set(f"已导出 {year} 年年历 PDF：{path}")
            dialog.destroy()
            if messagebox.askyesno("导出完成", f"已生成：\n{path}\n\n是否立即打开？", parent=self):
                self._open_file(path)

        btns = tk.Frame(body, bg=BG)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="取消", style="Tool.TButton",
                   command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text="导出 PDF", style="Go.TButton",
                   command=do_export).pack(side="right")

        dialog.update_idletasks()
        dialog.geometry(f"+{self.winfo_rootx() + 160}+{self.winfo_rooty() + 160}")

    @staticmethod
    def _open_file(path: str) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(path)          # noqa: S606
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except Exception:                    # noqa: BLE001
            pass


def run(year: int | None = None) -> int:
    """启动界面。year 不为 None 时跳转到该年份。"""
    app = CalendarApp()
    if year and year != date.today().year:
        app.jump_to(date(year, date.today().month, 1))
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
