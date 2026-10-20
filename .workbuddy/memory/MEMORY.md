# 项目长期记忆

## 万年历项目（2026-10-14 起）
- 目录：工作区根目录（`C:\Users\wangb\WorkBuddy\2026-10-14-08-57-34`）
- 结构约定：入口 `wannianli.py`；界面 `calendar_gui.py`；历法规则集中在 `lunar_service.py`；PDF 绘制在 `pdf_exporter.py`；配色在 `theme.py`
- 规则约定（用户需求）：公历农历双显；遇节气显示节气、不显示农历；必须显示春节/元宵/端午/中秋/七夕；导出 PDF 年历须与界面同规则
- 修改显示规则时只改 `lunar_service.get_day_info`，界面与 PDF 会自动一致
- 环境注意：托管 Python 无 tkinter，GUI 用 `C:\Users\wangb\.workbuddy\binaries\python\envs\tk\Scripts\python.exe`；纯导出可用 `envs\default`
