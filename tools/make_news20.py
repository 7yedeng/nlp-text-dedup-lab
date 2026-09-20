# -*- coding: utf-8 -*-
"""重新构建 data/news20/ 数据集（20 篇）：
  - R1/R2: 转载改写簇（源自真实抓取文章，程序化规则改写） 各4篇：源文+转载(换标题)+轻度改写+中度改写
  - D1/D2/D3: 同一事件不同报道（真实抓取）各3篇
  - U1/U2/U3: 完全不同主题（真实抓取）各1篇
"""
import os, json, random, re

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUT = os.path.join(BASE, "news20")
os.makedirs(OUT, exist_ok=True)

# 同义词替换规则（保持语义的近义替换，模拟网媒转载/洗稿）
SYN = {
    "成功": "顺利达成", "宣布": "对外公布", "表示": "称", "记者": "媒体人",
    "来自": "源自", "宣传": "推广", "冠军": "冠军", "球队": "队伍",
    "俱乐部": "球会", "球迷": "拥趸", "联赛": "赛事", "公司": "企业",
    "发布": "推出", "网友": "网民", "消息": "消息", "技术": "技术",
    "提升": "提升", "大幅": "明显", "远超": "高于", "关键": "核心",
}
MASKED = {"技术", "冠军", "消息", "提升"}  # 保留原词，避免误差

def read_doc(cat, idx):
    p = os.path.join(BASE, cat, f"{idx:03d}.txt")
    with open(p, encoding="utf-8") as f:
        lines = f.read().split("\n", 3)
    title = lines[0].replace("title=", "", 1).strip()
    src = lines[1].replace("source=", "", 1).strip()
    body = lines[3] if len(lines) > 3 else ""
    return title, src, body

def substitute(text, n=None):
    """在 n 个出现位置上做同义替换；n=None 则全部替换"""
    cnt = 0
    for w, rep in SYN.items():
        if w in MASKED:
            continue
        while w in text:
            if n is not None and cnt >= n:
                return text, cnt
            text = text.replace(w, rep, 1)
            cnt += 1
    return text, cnt

def write(idx, title, src, cat, group, body, r1=None):
    with open(os.path.join(OUT, f"{idx:03d}.txt"), "w", encoding="utf-8") as f:
        f.write(f"title={title}\nsource={src}\ncategory={cat}\ngroup={group}\nrewrite={r1 or ''}\n\n{body}")

MANIFEST = {}
doc_meta = {}

# ---------- R1: 科技 015 扎克伯格专访 ----------
t0, s0, b0 = read_doc("tech", 15)
paras = [p for p in b0.split("\n") if p.strip()]
assert len(paras) >= 4, "source paras too few"

# 1) 源文
write(1, t0, s0, "tech", "R1", b0)
doc_meta[1] = {"title": t0, "group": "R1", "cat": "tech"}

# 2) 转载版：标题改写，正文不变
t1 = "深度｜扎克伯格谈中美AI竞争：'完全错误的叙事'"
write(2, t1, s0, "tech", "R1", b0, "reprint-title")
doc_meta[2] = {"title": t1, "group": "R1", "cat": "tech"}

# 3) 轻度改写：标题改写 + 前 200 字同义替换 + 结尾加来源声明
body3, _ = substitute(b0, n=6)
body3 = body3 + "\n\n（原标题：扎克伯格深度专访：中美AI竞争完全错误，美国别想长期领先中国，转载自网易科技）"
t3 = "独家专访扎克伯格：中美AI竞争的说法完全错误"
write(3, t3, s0, "tech", "R1", body3, "light-rewrite")
doc_meta[3] = {"title": t3, "group": "R1", "cat": "tech"}

# 4) 中度改写：标题改写 + 段序调整 + 更多同义替换 + 删末段
body4 = "\n".join(paras[1:] + [paras[0]])
body4, _ = substitute(body4, n=12)
t4 = "扎克伯格专访实录：AI竞争叙事背后，中美科技产业的真实关系"
write(4, t4, s0, "tech", "R1", body4, "medium-rewrite")
doc_meta[4] = {"title": t4, "group": "R1", "cat": "tech"}

# ---------- R2: 体育 022 国米曼联 ----------
t0, s0, b0 = read_doc("sports", 22)
paras = [p for p in b0.split("\n") if p.strip()]
assert len(paras) >= 3

write(5, t0, s0, "sports", "R2", b0)
doc_meta[5] = {"title": t0, "group": "R2", "cat": "sports"}

t5 = "观察｜国际米兰检验出罗马真身，红狼尚不具备争冠条件"
write(6, t5, s0, "sports", "R2", b0, "reprint-title")
doc_meta[6] = {"title": t5, "group": "R2", "cat": "sports"}

body7, _ = substitute(b0, n=6)
body7 = body7 + "\n\n（原标题：【观察】国米验出罗马真身 红狼还不具备争冠条件，转载自网易体育）"
t7 = "观点：国米一战验出罗马成色，红狼争冠还欠火候"
write(7, t7, s0, "sports", "R2", body7, "light-rewrite")
doc_meta[7] = {"title": t7, "group": "R2", "cat": "sports"}

body8 = "\n".join(paras[1:] + [paras[0]])
body8, _ = substitute(body8, n=10)
t8 = "复盘：罗马在梅阿查暴露的结构性短板"
write(8, t8, s0, "sports", "R2", body8, "medium-rewrite")
doc_meta[8] = {"title": t8, "group": "R2", "cat": "sports"}

# ---------- D1: 佟丽娅·陈思诚（真实不同报道） ----------
d1 = [("ent", 4), ("ent", 35), ("ent", 48)]
for k, (cat, ix) in enumerate(d1):
    ti, src, bd = read_doc(cat, ix)
    write(9 + k, ti, src, cat, "D1", bd)
    doc_meta[9 + k] = {"title": ti, "group": "D1", "cat": cat}

# ---------- D2: 萨拉赫帽子戏法（真实不同报道） ----------
d2 = [("sports", 24), ("sports", 39), ("sports", 41)]
for k, (cat, ix) in enumerate(d2):
    ti, src, bd = read_doc(cat, ix)
    write(12 + k, ti, src, cat, "D2", bd)
    doc_meta[12 + k] = {"title": ti, "group": "D2", "cat": cat}

# ---------- D3: 亚运首金（真实不同报道） ----------
d3 = [("sports", 9), ("sports", 19), ("sports", 45)]
for k, (cat, ix) in enumerate(d3):
    ti, src, bd = read_doc(cat, ix)
    write(15 + k, ti, src, cat, "D3", bd)
    doc_meta[15 + k] = {"title": ti, "group": "D3", "cat": cat}

# ---------- U: 完全不同主题 ----------
u = [("tech", 2), ("tech", 26), ("ent", 29)]
for k, (cat, ix) in enumerate(u):
    ti, src, bd = read_doc(cat, ix)
    write(18 + k, ti, src, cat, f"U{k+1}", bd)
    doc_meta[18 + k] = {"title": ti, "group": f"U{k+1}", "cat": cat}

manifest = {"doc": {}}
for idx in range(1, 21):
    m = doc_meta[idx]
    manifest["doc"][str(idx)] = {"title": m["title"], "group": m["group"], "cat": m["cat"]}
with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)

print("news20 rebuilt:")
for idx in range(1, 21):
    print(f"  {idx:02d} [{doc_meta[idx]['group']}] {doc_meta[idx]['title'][:38]}")