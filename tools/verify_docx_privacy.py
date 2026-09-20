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

# 姓名/学号是本人主动署名，属预期内容，不算泄露。
# 从环境变量读取，避免把个人信息写进仓库：
#   REPORT_MEMBER1_NAME / REPORT_MEMBER1_ID / REPORT_MEMBER2_NAME / REPORT_MEMBER2_ID
ALLOWED = [v.strip() for k, v in os.environ.items()
           if k.startswith("REPORT_MEMBER") and v.strip()]


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
        # 报告可能在：本项目 out/、本项目 提交材料/，或整理成包后的 01_提交材料/
        dirs = [os.path.join(base, "out"), os.path.join(base, "提交材料")]
        up = base
        for _ in range(4):
            up = os.path.dirname(up)
            if not up or up == os.path.dirname(up):
                break
            dirs.append(os.path.join(up, "01_提交材料"))
            dirs.append(os.path.join(up, "提交材料"))
        # 只检查**报告**（不含老师的作业文档等）
        cand = []
        for d in dirs:
            if not os.path.isdir(d):
                continue
            for f in sorted(os.listdir(d)):
                if f.endswith(".docx") and not f.startswith("~$") \
                        and "实验报告" in f:
                    p = os.path.join(d, f)
                    if p not in cand:
                        cand.append(p)
        paths = cand
        if not paths:
            print("未找到任何报告 docx（检查过：%s）" % ", ".join(dirs))
            return 1
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
