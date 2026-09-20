# -*- coding: utf-8 -*-
"""交付文档隐私与内容校验（针对审计中"报告 DOCX 未能取得内容"的盲区）。

检查项：
  1. docProps/core.xml  —— 作者、最后修改者、标题等元数据是否残留个人信息
  2. docProps/app.xml   —— 应用名、公司等
  3. docProps/custom.xml / 其它自定义属性
  4. word/document.xml  —— 正文是否含本机绝对路径、用户名、邮箱、密钥样式串
  5. 页眉/页脚/批注（word/header*.xml、footer*.xml、comments.xml）
  6. 全包搜索可疑模式：Windows 用户目录、邮箱、api key / token / password 等

用法：python tools/verify_docx_privacy.py <docx 路径> [更多 docx ...]
"""
import os
import re
import sys
import zipfile

SUSPECT_PATTERNS = [
    ("Windows 用户目录", r"[A-Za-z]:\\Users\\[^\\\s\"'<>]+"),
    ("本机盘符路径", r"[A-Za-z]:\\(?:dev|Courses|Projects|Windows|Program)[\\/][^\s\"'<>]*"),
    ("邮箱地址", r"[\w.+-]+@[\w-]+\.[\w.]+"),
    ("疑似密钥/令牌", r"(?i)(api[_-]?key|secret|token|passwd|password|bearer)\s*[:=]\s*\S+"),
    ("手机号", r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    ("身份证号", r"(?<!\d)\d{17}[\dXx](?!\d)"),
]

# 姓名/学号是本人主动署名，属预期内容，不算泄露
ALLOWED = ["<成员一姓名>", "<成员一学号>"]


def scan(name, text, findings):
    for label, pat in SUSPECT_PATTERNS:
        for m in re.finditer(pat, text):
            s = m.group(0)
            if any(a in s for a in ALLOWED):
                continue
            findings.append((name, label, s[:120]))


def check(path):
    print("=" * 74)
    print("检查文档:", os.path.basename(path))
    print("=" * 74)
    findings = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        print(f"包内条目数: {len(names)}")
        meta_files = [n for n in names
                      if n.startswith("docProps/") or n.startswith("word/header")
                      or n.startswith("word/footer") or "comments" in n]
        print("元数据/页眉页脚/批注文件:", meta_files or "（无）")

        for n in meta_files:
            raw = z.read(n).decode("utf-8", errors="replace")
            print(f"\n--- {n} ---")
            print("   " + raw[:700].replace("\n", "\n   "))
            scan(n, raw, findings)

        # 正文与全包扫描
        for n in names:
            if not n.endswith(".xml") and not n.endswith(".rels"):
                continue
            try:
                raw = z.read(n).decode("utf-8", errors="replace")
            except Exception:
                continue
            scan(n, raw, findings)

    print("\n--- 可疑项 ---")
    if not findings:
        print("  ✅ 未发现用户目录路径 / 邮箱 / 密钥样式串 / 手机号 / 身份证号")
    else:
        seen = set()
        for name, label, s in findings:
            k = (label, s)
            if k in seen:
                continue
            seen.add(k)
            print(f"  ⚠ [{label}] {name}: {s}")
    return len(findings)


def main(argv):
    paths = argv[1:] or []
    if not paths:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        paths = [os.path.join(base, "out", "<成员一姓名>+<成员一学号>+第1次实验报告.docx")]
    total = 0
    for p in paths:
        if not os.path.exists(p):
            print("缺失:", p)
            continue
        total += check(p)
    print("\n可疑项合计:", total)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
