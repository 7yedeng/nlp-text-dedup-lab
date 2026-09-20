# -*- coding: utf-8 -*-
"""生成「NLP第一次实验」包的完整文件清单。

输出两个文件：
  05_参考资料/文件清单.txt   人类可读的目录树 + 体积统计
  05_参考资料/文件清单.csv   机器可读（路径、字节数、修改时间）
"""
import csv
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))          # …/02_代码/NLP/tools
PROJECT = os.path.dirname(HERE)                            # …/02_代码/NLP
# 包根：优先找含 01_提交材料 的上级目录；找不到就退回项目上级
PKG = None
cur = PROJECT
for _ in range(4):
    cand = os.path.dirname(cur)
    if os.path.isdir(os.path.join(cand, "01_提交材料")):
        PKG = cand
        break
    cur = cand
if PKG is None:
    PKG = os.path.dirname(PROJECT)
OUT = os.path.join(PKG, "05_参考资料")
os.makedirs(OUT, exist_ok=True)
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "_baseline_original"}


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024


def walk(root):
    """返回 (相对路径, 字节数, mtime) 列表，目录优先、名称排序。"""
    items = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn.startswith("~$") or fn.endswith(".pyc"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                st = os.stat(p)
            except OSError:
                continue
            items.append((os.path.relpath(p, root), st.st_size, st.st_mtime))
    return sorted(items)


def main():
    files = walk(PKG)
    total = sum(s for _p, s, _m in files)
    lines = []
    lines.append("NLP 第一次实验 —— 完整包文件清单")
    lines.append("=" * 78)
    lines.append(f"生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}")
    lines.append(f"文件总数：{len(files)}   合计体积：{human(total)}")
    lines.append("")

    # 顶层统计
    lines.append("【按目录统计】")
    lines.append(f"  {'目录':<22}{'文件数':>8}{'体积':>12}")
    lines.append("  " + "-" * 42)
    tops = {}
    for p, s, _m in files:
        top = p.split(os.sep)[0] if os.sep in p else "(顶层文件)"
        tops.setdefault(top, [0, 0])
        tops[top][0] += 1
        tops[top][1] += s
    for top in sorted(tops):
        n, sz = tops[top]
        lines.append(f"  {top:<22}{n:>8}{human(sz):>12}")
    lines.append("")

    # 目录树
    lines.append("【完整文件列表】")
    cur_dir = None
    for p, s, m in files:
        d = os.path.dirname(p) or "."
        if d != cur_dir:
            lines.append("")
            lines.append(f"[{d}]")
            cur_dir = d
        lines.append(f"  {os.path.basename(p):<58}{human(s):>10}  "
                     f"{datetime.fromtimestamp(m):%Y-%m-%d %H:%M}")

    txt = os.path.join(OUT, "文件清单.txt")
    with open(txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    csvp = os.path.join(OUT, "文件清单.csv")
    with open(csvp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["相对路径", "字节数", "修改时间", "目录"])
        for p, s, m in files:
            w.writerow([p, s, datetime.fromtimestamp(m).strftime("%Y-%m-%d %H:%M:%S"),
                        os.path.dirname(p)])

    print(f"清单已生成：{txt}")
    print(f"          {csvp}")
    print(f"文件总数 {len(files)}，合计 {human(total)}")
    print()
    print("按目录统计：")
    for top in sorted(tops):
        n, sz = tops[top]
        print(f"  {top:<22}{n:>6} 个  {human(sz):>10}")


if __name__ == "__main__":
    main()
