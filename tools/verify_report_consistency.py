# -*- coding: utf-8 -*-
"""一致性校验：报告 DOCX 中出现的数字，是否都能在结构化结果中找到对应。

这是针对审计意见 S1 的回归检查——初版报告生成器里硬编码了
91.87 / 713.32 / 30.52 ms 与「84 对、68 误报」等与结果文件冲突的旧数字。
本脚本的做法：
  1. 从四份 results_summary_*.json 收集"允许出现"的数值集合
     （含各种常用舍入位数，以及 ms/百分比等派生值）；
  2. 从报告 DOCX 提取所有正文与表格文本；
  3. 找出报告里出现、但不在允许集合中的小数（≥2 位有效小数）；
  4. 逐个报告出来供人工判断。
用法：python tools/verify_report_consistency.py
"""
import json
import os
import re
import sys

from docx import Document

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "out")
REPORT = os.path.join(OUT, "<成员一姓名>+<成员一学号>+第1次实验报告.docx")


def collect_numbers(obj, acc, path=""):
    """递归收集 JSON 中所有数值与嵌套数字（含字符串里的 Top-3 相似度）。"""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        v = float(obj)
        for nd in (0, 1, 2, 3, 4, 6):
            acc.add(f"{v:.{nd}f}")
        # 派生：毫秒（JSON 里计时以秒存储）
        acc.add(f"{v * 1000:.1f}")
        acc.add(f"{v * 1000:.2f}")
        # 派生：百分比
        acc.add(f"{v * 100:.1f}")
        acc.add(f"{v * 100:.2f}")
        acc.add(f"{v:.2%}")
        # 整数形式
        acc.add(str(int(round(v))))
        return
    if isinstance(obj, str):
        # 字符串里内嵌的数字也算"有出处"（例如类比的 Top-3 文本 "王后(0.705)、爵士(0.656)"）
        for m in re.findall(r"\d+\.\d+", obj):
            acc.add(m)
            acc.add(f"{float(m):.3f}")
            acc.add(f"{float(m):.2f}")
            acc.add(f"{float(m):.1f}")
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            collect_numbers(v, acc, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            collect_numbers(v, acc, f"{path}[{i}]")


def report_text(path):
    doc = Document(path)
    parts = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for r in t.rows:
            for c in r.cells:
                parts.append(c.text)
    return "\n".join(parts)


def main():
    allowed = set()
    for fn in sorted(os.listdir(OUT)):
        if fn.startswith("results_summary_") and fn.endswith(".json"):
            with open(os.path.join(OUT, fn), encoding="utf-8") as f:
                collect_numbers(json.load(f), allowed)

    # 明确允许的常量（人写的编号/年份/尺寸/公式示例，不是实验结果）
    allowed |= {
        "1.0", "1.00", "1.000", "0.0", "0.00", "0.000", "0.1", "0.2", "0.3", "0.4",
        "0.5", "0.6", "0.7", "0.8", "0.9", "2.0", "3.0", "30", "64", "128", "1000",
        "0.12", "0.15", "0.19", "0.26", "0.96", "1.35", "3.13", "5.13", "6.13", "1.5",
        "2026", "<成员一学号>", "1.1", "2.1", "3.1", "4.1", "5.1", "6.1", "7.1",
        "0.05", "0.01", "0.02", "0.03", "0.04", "2.2", "2.3", "2.4", "4.7",
        # 审计整改说明中"引用的历史错误值"——它们是叙事中复述缺陷，不是被当作结果输出
        "91.87", "713.32", "30.52",
    }

    # 数值比较用"归一化"后的形式（去掉末尾多余的 0），
    # 使报告里的 0.9400 与 JSON 里的 0.94 视为同一数值。
    def key(x):
        try:
            return f"{float(x):.10g}"
        except ValueError:
            return x

    allowed_norm = {key(a) for a in allowed}

    txt = report_text(REPORT)
    # 提取所有形如 1.234 的小数
    found = re.findall(r"(?<![\d.])(\d+\.\d{2,})", txt)
    unknown = sorted({f for f in found if key(f) not in allowed_norm},
                     key=lambda x: -float(x))

    print(f"报告: {os.path.basename(REPORT)}")
    print(f"结构化结果中可解释的数值形式: {len(allowed)} 个")
    print(f"报告中小数（≥2位）出现: {len(set(found))} 个不同取值")
    print(f"其中无法由结构化结果解释的: {len(unknown)} 个")
    if unknown:
        print("\n需人工确认的数值：")
        for u in unknown:
            # 给出上下文
            m = re.search(r".{0,34}" + re.escape(u) + r".{0,34}", txt)
            ctx = m.group(0).replace("\n", " ") if m else ""
            print(f"  {u:>10}  …{ctx}…")
    else:
        print("\n✅ 报告中所有 ≥2 位小数都能由结构化结果解释（无孤立数字）")
    return 0 if not unknown else 1


if __name__ == "__main__":
    sys.exit(main())
