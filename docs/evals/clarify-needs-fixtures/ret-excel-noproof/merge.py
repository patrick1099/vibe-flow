"""把多张班级成绩 CSV 合并成一份行列表，喂给 export_excel.export。"""
import csv
from pathlib import Path


def merge(folder):
    rows = []
    for f in sorted(Path(folder).glob("*.csv")):
        cls = f.stem
        with f.open(encoding="utf-8") as fh:
            for name, score in csv.reader(fh):
                rows.append([cls, name, score])
    return rows
