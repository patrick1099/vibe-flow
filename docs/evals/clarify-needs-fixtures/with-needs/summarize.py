"""汇总当月所有发票金额出一张 CSV 总表。

文件名格式假设是 rename_invoices.py 改好的 日期_金额.pdf。
"""
import csv
import sys
from pathlib import Path


def summarize(folder):
    folder = Path(folder)
    rows = []
    total = 0.0
    for pdf in sorted(folder.glob("*_*.pdf")):
        stem = pdf.stem  # 20260603_128.00
        date_str, amount_str = stem.split("_", 1)
        amount = float(amount_str)
        rows.append((date_str, amount))
        total += amount

    out = folder / "汇总.csv"
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["日期", "金额"])
        w.writerows(rows)
        w.writerow(["合计", f"{total:.2f}"])
    print(f"汇总完成，共 {len(rows)} 张，合计 {total:.2f}，写入 {out}")


if __name__ == "__main__":
    summarize(sys.argv[1] if len(sys.argv) > 1 else ".")
