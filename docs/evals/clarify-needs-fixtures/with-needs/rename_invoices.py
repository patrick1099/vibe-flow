"""把一个文件夹里的 PDF 发票批量改名成 日期_金额.pdf。

从旁挂的同名 .txt（OCR 文本）里抠出开票日期和金额。
"""
import re
import sys
from pathlib import Path


def extract_date_amount(text):
    """从发票文本里抠出开票日期和金额。返回 (date_str, amount_str) 或 None。"""
    date_m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", text)
    amount_m = re.search(r"[¥￥]\s*([\d,]+\.\d{2})", text)
    if not date_m or not amount_m:
        return None
    date_str = f"{date_m.group(1)}{int(date_m.group(2)):02d}{int(date_m.group(3)):02d}"
    amount_str = amount_m.group(1).replace(",", "")
    return date_str, amount_str


def rename_folder(folder):
    folder = Path(folder)
    renamed = 0
    for pdf in folder.glob("*.pdf"):
        text = pdf.with_suffix(".txt").read_text(encoding="utf-8")  # OCR 结果旁挂
        hit = extract_date_amount(text)
        if hit is None:
            print(f"[跳过] 认不出日期/金额：{pdf.name}")
            continue
        date_str, amount_str = hit
        new_name = folder / f"{date_str}_{amount_str}.pdf"
        pdf.rename(new_name)
        print(f"[改名] {pdf.name} -> {new_name.name}")
        renamed += 1
    print(f"完成，共改名 {renamed} 张。")


if __name__ == "__main__":
    rename_folder(sys.argv[1] if len(sys.argv) > 1 else ".")
