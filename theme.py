# -*- coding: utf-8 -*-
"""界面与 PDF 共用的配色 / 字体常量（浅色主题）。"""
from __future__ import annotations

# ---------------- 背景与结构 ----------------
BG = "#f3f5f8"            # 窗口底色
CARD = "#ffffff"          # 日历格底色
HEADER_BG = "#eef1f6"     # 星期表头底色
BORDER = "#d7dce4"        # 网格线
TITLE_BG = "#ffffff"

# ---------------- 文字 ----------------
TEXT = "#202124"          # 工作日 / 正文
TEXT_MUTED = "#ffffff"     # 占位（勿用，见下）
TEXT_SECOND = "#5f6b7a"   # 农历日名等次要文字
TEXT_OUT = "#b9bfc8"      # 非本月补位格
TEXT_WEEKEND = "#c0392b"  # 周末
HEADER_TEXT = "#4a5568"

# ---------------- 分类着色 ----------------
CATEGORY_COLORS = {
    "traditional": "#c62828",   # 传统节日：红
    "jieqi": "#0a7d4f",         # 二十四节气：绿
    "public": "#1565c0",        # 公历节日：蓝
    "lunar": "#5f6b7a",         # 普通农历日：灰
    "month": "#8a5a00",         # 农历初一（月名）：棕黄
}

# ---------------- 今天高亮 ----------------
TODAY_BG = "#e4efff"
TODAY_BORDER = "#1a73e8"
HOVER_BG = "#eef2f8"

CATEGORY_LABELS = {
    "traditional": "传统节日",
    "jieqi": "二十四节气",
    "public": "公历节日",
    "lunar": "农历日期",
    "month": "农历月初一",
}
