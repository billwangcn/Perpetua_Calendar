# -*- coding: utf-8 -*-
"""把某一年的日历导出为 PDF —— 排版规则与界面（wannianli.py）完全一致。

默认：A4 横向，每页 6 个月（3 列 × 2 行），一整年 2 页；
     A3 横向为每页 12 个月（4 列 × 3 行），一整年 1 页。
"""
from __future__ import annotations

import os
from datetime import date
from typing import Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

from lunar_service import (
    DEFAULT_OPTIONS,
    DisplayOptions,
    lunar_year_summary,
    month_grid,
    year_festival_summary,
)
from theme import BORDER, CATEGORY_COLORS, HEADER_BG, TEXT, TEXT_OUT, TEXT_WEEKEND, TODAY_BG, TODAY_BORDER

_FONT_READY = False
FONT_NORMAL = "CNCalendar"
FONT_BOLD = "CNCalendar-Bold"

_CANDIDATES: Tuple[Tuple[str, str], ...] = (
    (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"),
    (r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simhei.ttf"),
    (r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\simsun.ttc"),
    ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/PingFang.ttc"),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc"),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
)


def register_fonts() -> None:
    """注册可用的中文字体（找不到系统字体时退回 Adobe STSong-Light）。"""
    global _FONT_READY
    if _FONT_READY:
        return
    regular = bold = None
    for reg, bld in _CANDIDATES:
        if os.path.exists(reg):
            regular = reg
            bold = bld if os.path.exists(bld) else reg
            break
    if regular:
        try:
            pdfmetrics.registerFont(TTFont(FONT_NORMAL, regular, subfontIndex=0))
            pdfmetrics.registerFont(TTFont(FONT_BOLD, bold, subfontIndex=0))
            pdfmetrics.registerFontFamily(FONT_NORMAL, normal=FONT_NORMAL, bold=FONT_BOLD,
                                          italic=FONT_NORMAL, boldItalic=FONT_BOLD)
            _FONT_READY = True
            return
        except Exception:      # 字体解析失败时继续回退
            pass
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    pdfmetrics.registerFontFamily("STSong-Light", normal="STSong-Light", bold="STSong-Light",
                                  italic="STSong-Light", boldItalic="STSong-Light")
    globals()["FONT_NORMAL"] = "STSong-Light"
    globals()["FONT_BOLD"] = "STSong-Light"
    _FONT_READY = True


def _layout(paper: str) -> dict:
    paper = (paper or "A4").upper()
    if paper == "A3":
        pw, ph = landscape(A3)
        cols, rows = 4, 3
        margin = 10 * mm
    else:
        pw, ph = landscape(A4)
        cols, rows = 3, 2
        margin = 12 * mm
    return {
        "pw": pw, "ph": ph, "cols": cols, "rows": rows,
        "margin": margin, "gap": 6 * mm,
        "pages": (12 + cols * rows - 1) // (cols * rows),
    }


def export_year_pdf(year: int, out_path: str, paper: str = "A4",
                    options: DisplayOptions = DEFAULT_OPTIONS,
                    title: Optional[str] = None) -> str:
    """导出整年年历 PDF，返回生成的文件路径。"""
    register_fonts()
    lay = _layout(paper)
    pw, ph, cols, rows = lay["pw"], lay["ph"], lay["cols"], lay["rows"]
    margin, gap = lay["margin"], lay["gap"]

    c = rl_canvas.Canvas(out_path, pagesize=(pw, ph))
    c.setTitle(f"{year}年万年历")
    c.setAuthor("万年历")

    months = list(range(1, 13))
    per_page = cols * rows
    pages = lay["pages"]
    festivals = year_festival_summary(year, options)
    fest_txt = "   ".join(f"{name}{d.month}月{d.day}日" for name, d in festivals)
    today = date.today()

    title_h = 26 * mm if festivals else 20 * mm
    header_h = 8 * mm                      # 非首页顶部小标题
    footer_h = 8 * mm

    for p in range(pages):
        chunk = months[p * per_page: (p + 1) * per_page]
        top_space = title_h if p == 0 else header_h
        avail_w = pw - margin * 2 - gap * (cols - 1)
        avail_h = ph - margin - footer_h - top_space - gap * (rows - 1)
        block_w = avail_w / cols
        block_h = avail_h / rows

        _draw_page_header(c, year, pw, ph, margin, p, top_space, festivals, options, title)

        for idx, month in enumerate(chunk):
            r, col = divmod(idx, cols)
            x0 = margin + col * (block_w + gap)
            y0 = ph - margin - top_space - r * (block_h + gap)      # 块顶边的 y
            _draw_month(c, x0, y0, block_w, block_h, year, month, options, today)

        _draw_footer(c, year, pw, margin, footer_h, p, pages, paper, fest_txt if p == 0 else None)
        c.showPage()

    c.save()
    return out_path


def _draw_page_header(c, year, pw, ph, margin, page_idx, top_space,
                      festivals, options, title):
    y = ph - margin
    c.setFont(FONT_BOLD if _FONT_READY else "Helvetica", 9)
    if page_idx == 0:
        c.setFont(FONT_BOLD, 22)
        c.setFillColor(colors.HexColor("#1f2933"))
        c.drawString(margin, y - 17 * mm, title or f"{year} 年 · 年历")

        c.setFont(FONT_NORMAL, 10)
        c.setFillColor(colors.HexColor("#52616f"))
        c.drawString(margin, y - 22 * mm, f"{lunar_year_summary(year)}    公历 / 农历对照 · 二十四节气 · 传统节日")

        if festivals:
            line = "传统节日：" + "   ".join(f"{n}{d.month}月{d.day}日" for n, d in festivals)
            c.setFont(FONT_NORMAL, 8.5)
            c.setFillColor(colors.HexColor("#c62828"))
            # 过长时自动缩排
            max_w = pw - margin * 2
            c.drawString(margin, y - 26 * mm, _ellipsize(c, line, max_w, FONT_NORMAL, 8.5))
    else:
        c.setFont(FONT_BOLD, 12)
        c.setFillColor(colors.HexColor("#1f2933"))
        c.drawString(margin, y - 5.5 * mm, f"{year} 年 · 年历（续）")
        c.setFont(FONT_NORMAL, 8.5)
        c.setFillColor(colors.HexColor("#798291"))
        c.drawRightString(pw - margin, y - 5.5 * mm, "万年历")


def _ellipsize(c, text: str, max_w: float, font: str, size: float) -> str:
    if pdfmetrics.stringWidth(text, font, size) <= max_w:
        return text
    cut = text
    while cut and pdfmetrics.stringWidth(cut + "…", font, size) > max_w:
        cut = cut[:-1]
    return cut + "…"


def _draw_month(c, x0, y0, w, h, year, month, options, today):
    """绘制一个月份方块。"""
    rows_count = 6
    title_h = min(7.5 * mm, h * 0.13)
    week_h = min(7 * mm, h * 0.12)
    row_h = (h - title_h - week_h) / rows_count
    cell_w = w / 7

    grid = month_grid(year, month, options)

    # 月份标题
    c.setFillColor(colors.HexColor("#ffffff"))
    c.rect(x0, y0 - title_h, w, title_h, stroke=0, fill=1)
    c.setFont(FONT_BOLD, min(13, title_h / 2.2))
    c.setFillColor(colors.HexColor("#1f2933"))
    c.drawString(x0 + 1.5 * mm, y0 - title_h * 0.72, f"{month} 月")

    # 星期行
    wy = y0 - title_h
    c.setFillColor(colors.HexColor(HEADER_BG))
    c.rect(x0, wy - week_h, w, week_h, stroke=0, fill=1)
    c.setFont(FONT_NORMAL, min(8.5, week_h / 2.4))
    for i, name in enumerate(("日", "一", "二", "三", "四", "五", "六")):
        cx = x0 + cell_w * (i + 0.5)
        c.setFillColor(colors.HexColor(TEXT_WEEKEND if i in (0, 6) else "#4a5568"))
        c.drawCentredString(cx, wy - week_h * 0.68, name)

    number_size = min(cell_w * 0.5, row_h * 0.5, 11)
    lunar_size = min(cell_w / 3.5, row_h * 0.34, 8.5)

    top_wait = wy - week_h
    for r in range(rows_count):
        for i in range(7):
            info = grid[r][i]
            cx = x0 + cell_w * i
            cy = top_wait - row_h * r
            x_start = cx
            y_top_cell = cy

            # 背景
            if info.is_today:
                c.setFillColor(colors.HexColor(TODAY_BG))
                c.rect(x_start, y_top_cell - row_h, cell_w, row_h, stroke=0, fill=1)
            elif i in (0, 6):
                c.setFillColor(colors.HexColor("#fbf6f5"))
                c.rect(x_start, y_top_cell - row_h, cell_w, row_h, stroke=0, fill=1)

            # 网格线
            c.setStrokeColor(colors.HexColor(BORDER))
            c.setLineWidth(0.4)
            c.rect(x_start, y_top_cell - row_h, cell_w, row_h, stroke=1, fill=0)
            if info.is_today:
                c.setStrokeColor(colors.HexColor(TODAY_BORDER))
                c.setLineWidth(1.0)
                c.rect(x_start, y_top_cell - row_h, cell_w, row_h, stroke=1, fill=0)

            faded = info.is_out or info.day.month != month
            num_color = colors.HexColor(TEXT_OUT if faded else
                                        (TEXT_WEEKEND if info.is_weekend or i in (0, 6) else TEXT))
            if info.is_today:
                num_color = colors.HexColor("#1565d8")

            c.setFont(FONT_BOLD if not faded else FONT_NORMAL, number_size)
            c.setFillColor(num_color)
            c.drawCentredString(x_start + cell_w / 2, y_top_cell - row_h * 0.33 - number_size * 0.32,
                                info.solar_text)

            if faded:
                lunar_color = colors.HexColor(TEXT_OUT)
            else:
                lunar_color = colors.HexColor(CATEGORY_COLORS.get(info.category, "#5f6b7a"))
            c.setFont(FONT_NORMAL, lunar_size)
            c.setFillColor(lunar_color)
            txt = info.lunar_text
            max_to = max(3, int(cell_w / (lunar_size * 0.95)))
            if len(txt) > max_to:
                txt = txt[:max_to]
            c.drawCentredString(x_start + cell_w / 2, y_top_cell - row_h * 0.72 - lunar_size * 0.3, txt)


def _draw_footer(c, year, pw, margin, footer_h, page_idx, pages, paper, legend_festivals: Optional[str]):
    c.setFont(FONT_NORMAL, 7.5)
    c.setFillColor(colors.HexColor("#7b8794"))
    legend = ("说明：每格上行为公历日期，下行为农历；遇二十四节气显示节气名（绿色）；"
              "春节、元宵、端午、七夕、中秋等传统节日（红色）；元旦、劳动节、国庆等公历节日（蓝色）。")
    c.drawString(margin, footer_h * 0.42 + 4, _ellipsize(c, legend, pw - margin * 2 - 60, FONT_NORMAL, 7.5))
    c.drawRightString(pw - margin, footer_h * 0.42 + 4, f"第 {page_idx + 1} / {pages} 页")


def build_default_filename(year: int) -> str:
    return f"万年历_{year}年.pdf"
