# -*- coding: utf-8 -*-
"""万年历 · 公历农历双显 —— 程序入口。

用法：
    python wannianli.py                        # 打开桌面界面
    python wannianli.py --year 2030            # 界面直接定位到 2030 年
    python wannianli.py --export 2026          # 不打开界面，直接导出 2026 年年历 PDF
    python wannianli.py --export 2026 -o d:\\2026.pdf --paper A3

界面需要 tkinter（Python 官方发行版自带）；无界面导出模式不需要。
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def main() -> int:
    parser = argparse.ArgumentParser(description="万年历 · 公历农历双显（含二十四节气与传统节日）")
    parser.add_argument("--export", type=int, metavar="YEAR",
                        help="无界面模式：导出指定年份的年历 PDF")
    parser.add_argument("-o", "--out", help="PDF 输出路径（默认：当前目录下 万年历_年份.pdf）")
    parser.add_argument("--paper", choices=("A4", "A3"), default="A4",
                        help="纸张版式：A4 横向每页 6 个月（2 页），A3 横向整年 1 页，默认 A4")
    parser.add_argument("-y", "--year", type=int, default=date.today().year,
                        help="界面启动后定位到的年份")
    args = parser.parse_args()

    if args.export:
        import pdf_exporter

        out = args.out or os.path.join(os.getcwd(), pdf_exporter.build_default_filename(args.export))
        out = os.path.abspath(out)
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        path = pdf_exporter.export_year_pdf(args.export, out, args.paper)
        print(f"已导出：{path}")
        return 0

    try:
        from calendar_gui import run
    except ModuleNotFoundError as exc:
        if exc.name == "tkinter":
            print("当前 Python 解释器没有 tkinter，请改用 Python 官方发行版（安装时勾选 Tcl/Tk）。",
                  file=sys.stderr)
            return 2
        raise
    return run(args.year)


if __name__ == "__main__":
    raise SystemExit(main())
