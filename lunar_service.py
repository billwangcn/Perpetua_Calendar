# -*- coding: utf-8 -*-
"""万年历核心数据服务。

基于 lunar-python 计算每一天需要展示的信息，并对界面（Tkinter）与 PDF 导出提供
完全一致的展示规则：

优先级（默认）：传统节日 > 二十四节气 > 公历节日 > 农历日名
  · 传统节日：春节、除夕、元宵节、端午节、七夕节、中秋节、重阳节、腊八节……
  · 二十四节气：立春、雨水……清明（清明既是节气也是节日，按节日着色）
  · 公历节日：元旦、劳动节、国庆节等（可开关）
  · 其余日期显示农历日名，农历初一显示农历月名（如「正月」「腊月」「闰六月」）
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

from lunar_python import Solar

# ---------------------------------------------------------------- 常量表
WEEKDAY_CN = ("一", "二", "三", "四", "五", "六", "日")  # 索引 = date.weekday()

JIEQI_NAMES = (
    "立春", "雨水", "惊蛰", "春分", "清明", "谷雨", "立夏", "小满", "芒种", "夏至",
    "小暑", "大暑", "立秋", "处暑", "白露", "秋分", "寒露", "霜降", "立冬", "小雪",
    "大雪", "冬至", "小寒", "大寒",
)

# 农历节日已是传统节日；下面先列出「重要节日」，它们永远排在节气之前
MAJOR_FESTIVALS = ("春节", "除夕", "元宵节", "端午节", "七夕节", "中秋节")

TRADITIONAL_ORDER = (
    "春节", "除夕", "元宵节", "端午节", "七夕节", "中秋节", "重阳节",
    "中元节", "腊八节", "龙头节", "上巳节", "寒食节", "下元节", "寒衣节",
)

# 公历节日白名单（只保留法定/大众节日，避免 2626 个洋节刷屏）
PUBLIC_FESTIVALS = {
    "元旦节": "元旦",
    "劳动节": "劳动节",
    "国庆节": "国庆",
    "妇女节": "妇女节",
    "植树节": "植树节",
    "青年节": "青年节",
    "儿童节": "儿童节",
    "建军节": "建军节",
    "教师节": "教师节",
}

# 既是节气又是节日 -> 单独分类，按节日着色
QINGMING = "清明"

CATEGORY_TRADITIONAL = "traditional"
CATEGORY_JIEQI = "jieqi"
CATEGORY_PUBLIC = "public"
CATEGORY_LUNAR = "lunar"
CATEGORY_MONTH = "month"          # 农历初一：显示农历月名


@dataclass(frozen=True)
class DisplayOptions:
    """界面与 PDF 共用的展示开关。"""
    show_public: bool = True          # 是否显示元旦/劳动节/国庆等公历节日
    festival_first: bool = True       # True：节日优先于节气；False：节气优先于节日
    show_leap_marker: bool = True     # 闰月是否显示「闰」字


DEFAULT_OPTIONS = DisplayOptions()


@dataclass(frozen=True)
class DayInfo:
    """某一天用于展示的完整信息。"""
    day: date
    solar_text: str                   # 第一行：公历日号
    lunar_text: str                   # 第二行：节日/节气/农历
    category: str                     # 见上面 CATEGORY_*
    weekday: int                      # 0=周一 ... 6=周日
    is_weekend: bool
    is_today: bool
    is_out: bool                      # 非当前月（补齐格）
    tooltip: str


@lru_cache(maxsize=4096)
def _raw(y: int, m: int, d: int):
    solar = Solar.fromYmd(y, m, d)
    lunar = solar.getLunar()
    return {
        "lunar_year": lunar.getYearInChinese(),
        "ganzhi_year": lunar.getYearInGanZhi(),
        "ganzhi_month": lunar.getMonthInGanZhi(),
        "ganzhi_day": lunar.getDayInGanZhi(),
        "shengxiao": lunar.getYearShengXiao(),
        "lunar_month": lunar.getMonth(),           # 负数代表闰月
        "lunar_month_cn": lunar.getMonthInChinese(),
        "lunar_day": lunar.getDay(),
        "lunar_day_cn": lunar.getDayInChinese(),
        "jieqi": lunar.getJieQi() or "",
        "festivals": tuple(lunar.getFestivals()),
        "solar_festivals": tuple(solar.getFestivals()),
    }


def _pick_traditional(festivals: Sequence[str]) -> Optional[str]:
    if not festivals:
        return None
    for name in TRADITIONAL_ORDER:
        if name in festivals:
            return name
    return festivals[0]


def _pick_public(solar_festivals: Sequence[str]) -> Optional[str]:
    for name, short in PUBLIC_FESTIVALS.items():
        if name in solar_festivals:
            return short
    return None


def lunar_month_label(lunar_month_cn: str, show_leap: bool = True) -> str:
    """「六」->「六月」，「闰六」->「闰六月」。"""
    if not show_leap:
        lunar_month_cn = lunar_month_cn.lstrip("闰")
    return f"{lunar_month_cn}月"


@lru_cache(maxsize=8192)
def get_day_info(d: date, options: DisplayOptions = DEFAULT_OPTIONS,
                 base_month: Optional[int] = None) -> DayInfo:
    """返回某天的展示信息。base_month 用于判断是否为当月之外的补位格。"""
    raw = _raw(d.year, d.month, d.day)

    traditional = _pick_traditional(raw["festivals"])
    jieqi = raw["jieqi"]
    public = _pick_public(raw["solar_festivals"]) if options.show_public else None

    # 重要传统节日 vs 其它传统节日
    major = minor = None
    if traditional in MAJOR_FESTIVALS:
        major = traditional
    elif traditional:
        minor = traditional
    if jieqi == QINGMING:                      # 清明既是节气也是节日
        major = major or QINGMING
    jieqi_item = jieqi or None

    if options.festival_first:
        order = ((major, CATEGORY_TRADITIONAL), (jieqi_item, CATEGORY_JIEQI),
                 (minor, CATEGORY_TRADITIONAL), (public, CATEGORY_PUBLIC))
    else:
        order = ((jieqi_item, CATEGORY_JIEQI), (major, CATEGORY_TRADITIONAL),
                 (minor, CATEGORY_TRADITIONAL), (public, CATEGORY_PUBLIC))

    text, cat = None, CATEGORY_LUNAR
    for value, c in order:
        if value:
            text, cat = value, c
            break

    if text is None:
        if raw["lunar_day"] == 1:
            text = lunar_month_label(raw["lunar_month_cn"], options.show_leap_marker)
            cat = CATEGORY_MONTH
        else:
            text = raw["lunar_day_cn"]
            cat = CATEGORY_LUNAR

    today = date.today()
    weekday = d.weekday()
    is_out = base_month is not None and d.month != base_month

    tooltip = (
        f"{d.year}年{d.month}月{d.day}日  星期{WEEKDAY_CN[weekday]}\n"
        f"农历：{raw['lunar_year']}年（{raw['shengxiao']}年）"
        f"{lunar_month_label(raw['lunar_month_cn'])}{raw['lunar_day_cn']}\n"
        f"干支：{raw['ganzhi_year']}年 {raw['ganzhi_month']}月 {raw['ganzhi_day']}日"
    )
    extra = ""
    if traditional:
        extra += f"\n传统节日：{traditional}"
    if jieqi:
        extra += f"\n节气：{jieqi}" + ("（清明节）" if jieqi == QINGMING else "")
    if public:
        extra += f"\n公历节日：{public}"
    tooltip += extra

    return DayInfo(
        day=d,
        solar_text=str(d.day),
        lunar_text=text,
        category=cat,
        weekday=weekday,
        is_weekend=weekday >= 5,
        is_today=(d == today),
        is_out=is_out,
        tooltip=tooltip,
    )


def month_grid(year: int, month: int,
               options: DisplayOptions = DEFAULT_OPTIONS) -> List[List[DayInfo]]:
    """返回 6 行 × 7 列（周日起始）的月视图矩阵，含前后月补位格。"""
    first = date(year, month, 1)
    start = first - timedelta(days=(first.weekday() + 1) % 7)   # 回溯到周日
    return [
        [get_day_info(start + timedelta(days=w * 7 + i), options, month)
         for i in range(7)]
        for w in range(6)
    ]


def year_grid(year: int, options: DisplayOptions = DEFAULT_OPTIONS) -> Dict[int, List[List[DayInfo]]]:
    return {m: month_grid(year, m, options) for m in range(1, 13)}


def lunar_year_summary(year: int) -> str:
    """xx年对应的农历年信息，跨农历年时给出两个年份。"""
    head = _raw(year, 1, 1)
    tail = _raw(year, 12, 31)
    if head["ganzhi_year"] == tail["ganzhi_year"]:
        return f"农历{head['ganzhi_year']}年 · {head['shengxiao']}年"
    return f"农历{head['ganzhi_year']}年 · {tail['ganzhi_year']}年（{head['shengxiao']}转{tail['shengxiao']}）"


def year_festival_summary(year: int, options: DisplayOptions = DEFAULT_OPTIONS) -> List[Tuple[str, date]]:
    """全年传统节日（含清明）一览，按日期排序。"""
    result: List[Tuple[str, date]] = []
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        info = get_day_info(d, options)
        if info.category == CATEGORY_TRADITIONAL and not info.is_out:
            result.append((info.lunar_text, d))
        d += timedelta(days=1)
    seen, unique = set(), []
    for name, day in result:
        if name in seen:
            continue
        seen.add(name)
        unique.append((name, day))
    return unique
