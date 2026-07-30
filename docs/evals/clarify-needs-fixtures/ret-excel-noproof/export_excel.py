"""把合并后的成绩数据导出成 Excel 文件。"""
from pathlib import Path

try:
    import openpyxl
except ImportError:
    openpyxl = None


def export(rows, out_path="年级总表.xlsx"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "年级总表"
    ws.append(["班级", "姓名", "总分"])
    for r in rows:
        ws.append(r)
    wb.save(out_path)
    return Path(out_path)
