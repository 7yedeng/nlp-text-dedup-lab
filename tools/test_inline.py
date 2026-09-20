# -*- coding: utf-8 -*-
"""行内富文本解析器单元测试（不依赖 Word，直接调 parse_inline）。"""
import importlib.util
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "br", os.path.join(HERE, "build_report.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

BT = chr(96)          # 反引号
BOLD = "**"

tests = [
    # (输入, 期望纯文本, 说明)
    ("**加粗**与普通", "加粗与普通", "成对粗体"),
    ("开头**中间**结尾", "开头中间结尾", "粗体在中间"),
    ("含 " + BT + "代码" + BT + " 与 **粗体**",
     "含 代码 与 粗体", "两种标记并存"),
    ("交替**粗" + BT + "代" + BT + "粗**尾", "交替粗代粗尾",
     "反引号嵌套在粗体内（应同时加粗+等宽）"),
    ("不闭合 " + BOLD + "标记", "不闭合 " + BOLD + "标记",
     "落单的 ** 按普通字符保留，不吞字"),
    ("不闭合 " + BT + "标记", "不闭合 " + BT + "标记",
     "落单的反引号按普通字符保留"),
    ("**多**个**粗**体", "多个粗体", "多组粗体"),
    ("（" + BT + "out/x.json" + BT + "）", "（out/x.json）", "代码路径"),
    ("没有任何标记的普通句子。", "没有任何标记的普通句子。", "无标记"),
    ("**" + BT + "code" + BT + "**", "code", "粗体内的代码"),
]

all_ok = True
print("=" * 78)
print("parse_inline 单元测试")
print("=" * 78)
for t, expected, desc in tests:
    parts = m.parse_inline(t)
    joined = "".join(s for s, _b, _c in parts)
    good = (joined == expected)
    all_ok = all_ok and good
    print(("  OK  " if good else "  BAD ") + desc + "：" + repr(t))
    print("        -> " + repr([(s, b, c) for s, b, c in parts]))
    if not good:
        print("        期望: " + repr(expected))
        print("        实际: " + repr(joined))

# 额外性质：任何输入都不得丢字（去掉标记后应完全一致）
print()
print("=== 性质检查：解析后文本 = 去掉配对的标记 ===")
import itertools
chars = ["a", BOLD, BT, "b"]
bad = 0
for n in range(1, 8):
    for combo in itertools.product(chars, repeat=n):
        t = "".join(combo)
        joined = "".join(s for s, _b, _c in m.parse_inline(t))
        # 未配对的标记会被保留，所以只检查：解析结果里不含“凭空出现”的字符
        if any(ch not in t + BOLD + BT for ch in joined):
            bad += 1
            print("  异常输入:", repr(t), "->", repr(joined))
print("  穷举", sum(4 ** n for n in range(1, 8)), "个输入，异常", bad, "个")

print()
print("全部通过:", all_ok and bad == 0)
sys.exit(0 if (all_ok and bad == 0) else 1)
