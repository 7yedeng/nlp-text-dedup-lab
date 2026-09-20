# -*- coding: utf-8 -*-
"""生成《数据来源清单》（Markdown）

从 data/ 目录**实际读取**每条语料的 source= 字段，结构化输出为 Markdown 表格，
保证清单与语料一一对应、可复核（而不是手工维护的列表）。

- data/{sports,tech,ent}/*.txt 与 data/news20/*.txt 均含 source=URL，直接抽取
- data/titles.txt 与 data/short_texts.txt 本身不含逐条 URL，
  因此只列出抓取入口（接口地址）与说明，避免虚构链接

用法：python tools/make_source_list.py
输出：提交材料/<成员一姓名>+<成员一学号>+第1次实验-数据来源清单.md
"""
import os
import re
import json
import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUTDIR = os.path.join(BASE, "提交材料")
os.makedirs(OUTDIR, exist_ok=True)

NAME = "<成员一姓名>+<成员一学号>+<成员二姓名>+<成员二学号>"
CATS = [("sports", "体育"), ("tech", "科技"), ("ent", "娱乐")]

# 抓取入口（与 tools/scraper.py、tools/fetch_titles.py 中的实现一致）
SINA_LIDS = [2509, 2510, 2511, 2512, 2513, 2514, 2515, 2516, 2669, 2050]
NETEASE_CHANNELS = ["lady", "game", "digital", "fund", "house", "taiwan",
                    "reg", "fashion", "woman", "feng", "qt", "rare", "data"]
NETEASE_ARTICLE_CHANNELS = ["whole", "society", "ent", "sports", "tech", "auto",
                            "money", "health", "mil", "edu", "travel"]


def parse_doc(raw):
    """按首个空行切分元信息与正文，返回 (meta_dict, body)。"""
    head, _, body = raw.partition("\n\n")
    meta = {}
    for ln in head.split("\n"):
        if "=" in ln:
            k, _, v = ln.partition("=")
            meta[k.strip()] = v.strip()
    return meta, body.strip()


def read_folder(sub):
    folder = os.path.join(DATA, sub)
    rows = []
    if not os.path.isdir(folder):
        return rows
    for fn in sorted(os.listdir(folder)):
        if not fn.endswith(".txt"):
            continue
        with open(os.path.join(folder, fn), encoding="utf-8") as f:
            meta, body = parse_doc(f.read())
        rows.append({
            "file": f"{sub}/{fn}",
            "title": meta.get("title", ""),
            "source": meta.get("source", ""),
            "category": meta.get("category", sub),
            "group": meta.get("group", ""),
            "rewrite": meta.get("rewrite", ""),
            "chars": len(body),
        })
    return rows


def count_lines(path):
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for ln in f if ln.strip())


def main():
    md = []
    md.append("# 数据来源清单（抓取结果与来源链接）\n")
    md.append(f"> 附件：中文文本特征表示与内容重复理解实验（第 1 次实验）　姓名：<成员一姓名>　学号：<成员一学号>\n")
    md.append(f"> 生成时间：{datetime.datetime.now():%Y-%m-%d %H:%M:%S}　"
              f"生成脚本：`tools/make_source_list.py`\n")
    md.append("> 语料全部为公开新闻页面真实抓取，仅用于课程实验，版权归原媒体所有。\n")
    md.append("> 本清单由脚本从 `data/` 逐条读取 `source=` 字段生成，与语料文件一一对应。\n")

    # ---------- 一、抓取入口 ----------
    md.append("\n## 一、语料抓取入口（列表页 / 接口）\n")
    md.append("| 来源 | 接口地址 | 用途 |")
    md.append("| --- | --- | --- |")
    for lid in SINA_LIDS:
        md.append(f"| 新浪滚动新闻 API | `https://feed.mix.sina.com.cn/api/roll/get?"
                  f"pageid=153&lid={lid}&num=50&page=1..5` | 标题语料 `data/titles.txt`（lid={lid} 频道） |")
    md.append(f"| 网易滚动新闻接口 | `https://temp.163.com/special/00804KVA/cm_{{channel}}.js`"
              f"<br>（channel = {'/'.join(NETEASE_CHANNELS)}） | 补充标题语料 `data/titles.txt` |")
    md.append(f"| 网易新闻频道页 | `https://news.163.com/` 各频道列表页"
              f"<br>（{'/'.join(NETEASE_ARTICLE_CHANNELS)}） | 正文语料 `data/{{sports,tech,ent}}/` 的候选链接 |")
    md.append("| 中国新闻网 RSS | `https://www.chinanews.com.cn/rss/{channel}.xml` | 备用标题语料入口 |")

    # ---------- 二、正文语料 ----------
    themed_total = 0
    for sub, label in CATS:
        rows = read_folder(sub)
        themed_total += len(rows)
        md.append(f"\n## 二、{label}正文语料（`data/{sub}/`，共 {len(rows)} 篇）\n")
        md.append("| # | 标题 | 原文链接 | 正文字数 |")
        md.append("| --- | --- | --- | --- |")
        for i, r in enumerate(rows, 1):
            link = f"[{r['source']}]({r['source']})" if r["source"] else "（未记录）"
            title = r["title"].replace("|", "\\|")
            md.append(f"| {i} | {title} | {link} | {r['chars']} |")

    # ---------- 三、news20 ----------
    news = read_folder("news20")
    md.append(f"\n## 三、网页新闻语料（`data/news20/`，共 {len(news)} 篇）\n")
    md.append("分组含义：`R1/R2` = 转载改写簇（近似重复，用于正样本）；"
              "`D1/D2` = 同一事件不同报道；`D3` = 原标注为同事件、"
              "经复核实为不同事件（15 号女子现代五项团体夺金 vs 16/17 号男子铁人三项摘银），"
              "故不计入近似重复正样本；`U1~U3` = 完全不同主题。\n")
    md.append("| # | 文件 | 标题 | 分组 | 改写类型 | 原文链接 | 正文字数 |")
    md.append("| --- | --- | --- | --- | --- | --- | --- |")
    for r in news:
        link = f"[链接]({r['source']})" if r["source"] else "（未记录）"
        title = r["title"].replace("|", "\\|")
        md.append(f"| {r['file'].split('/')[-1][:3]} | `{r['file']}` | {title} | {r['group']} | "
                  f"{r['rewrite'] or '—'} | {link} | {r['chars']} |")

    # ---------- 四、标题语料 ----------
    n_titles = count_lines(os.path.join(DATA, "titles.txt"))
    md.append(f"\n## 四、标题语料（`data/titles.txt`，共 {n_titles} 条）\n")
    md.append(f"- 规模：{n_titles} 条中文新闻标题，每行一条\n")
    md.append("- 来源：上表「一、语料抓取入口」中的新浪滚动新闻 API（多 lid 频道分页）"
              "与网易滚动新闻接口（多频道）聚合去重而成\n")
    md.append("- 说明：该文件按「每行一条文本」的格式保存，**本身不逐条记录 URL**；"
              "如需逐条溯源，可按上述接口地址重新抓取（脚本：`tools/fetch_titles.py`）\n")
    md.append("\n### 前 20 条示例\n")
    md.append("| # | 标题 |")
    md.append("| --- | --- |")
    with open(os.path.join(DATA, "titles.txt"), encoding="utf-8") as f:
        for i, ln in enumerate(f, 1):
            if i > 20:
                break
            md.append(f"| {i} | {ln.strip().replace('|', chr(92) + '|')} |")

    # ---------- 五、测试用例 ----------
    md.append("\n## 五、去重测试用例（`data/short_texts.txt`，6 条）\n")
    md.append("- 性质：**人工设计**的测试用例，非网络抓取，故无来源链接\n")
    md.append("- 设计覆盖四类关系：完全重复 / 轻度修改 / 中度改写 / 完全不相关\n")
    md.append("- 分层金标准：`T1-T2` 为近重复；`T1~T4` 其余对为同事件改写；`T5/T6` 为不相关\n")
    md.append("\n| 编号 | 文本 | 类别 |")
    md.append("| --- | --- | --- |")
    labels = ["原始文本", "完全重复（与 T1 逐字相同）", "轻度修改（删词/换词）",
              "中度改写（换句序/同义替换）", "完全不相关（同领域不同事件）", "完全不相关（不同领域）"]
    with open(os.path.join(DATA, "short_texts.txt"), encoding="utf-8") as f:
        for i, ln in enumerate([x.strip() for x in f if x.strip()]):
            md.append(f"| T{i+1} | {ln.replace('|', chr(92) + '|')} | {labels[i] if i < len(labels) else '—'} |")

    # ---------- 六、词向量模型 ----------
    md.append("\n## 六、预训练词向量模型\n")
    md.append("| 项目 | 说明 |")
    md.append("| --- | --- |")
    md.append("| 模型 | 腾讯 AI Lab 中文词向量（轻量版，Light 版） |")
    md.append("| 规模 | 143613 词 × 200 维（文件约 116 MB，首行 `143613 200`） |")
    md.append("| 本地路径 | `model/light_Tencent_AILab_ChineseEmbedding.bin`（word2vec 二进制格式） |")
    md.append("| 加载方式 | `gensim.models.KeyedVectors.load_word2vec_format(path, binary=True)` |")
    md.append("| 是否随包提交 | **否**（体积过大，且作业要求不提交大型预训练模型文件），需自行下载后放入 `model/` |")

    # ---------- 七、汇总 ----------
    md.append("\n## 七、语料规模汇总\n")
    md.append("| 数据文件 | 规模 | 获取方式 | 用途 |")
    md.append("| --- | --- | --- | --- |")
    md.append(f"| `data/titles.txt` | {n_titles} 条标题 | 新浪滚动 API + 网易滚动接口多频道聚合 | 实验一(1) TF-IDF 语料 |")
    md.append(f"| `data/sports/` | {len(read_folder('sports'))} 篇正文 | 网易新闻详情页解析 | 实验二(1) 主题文档向量 |")
    md.append(f"| `data/tech/` | {len(read_folder('tech'))} 篇正文 | 网易新闻详情页解析 | 实验二(1) 主题文档向量 |")
    md.append(f"| `data/ent/` | {len(read_folder('ent'))} 篇正文 | 网易新闻详情页解析 | 实验二(1) 主题文档向量 |")
    md.append(f"| `data/news20/` | {len(news)} 篇正文 + 分组真值 | 真实源文 + 规则化改写 + 同事件多源报道 | 实验二(2) 加权 SimHash |")
    md.append("| `data/short_texts.txt` | 6 条 | 人工设计 | 实验一(2) MinHash+LSH |")
    md.append(f"\n> 正文合计：主题语料 {themed_total} 篇 + news20 语料 {len(news)} 篇 = "
              f"**{themed_total + len(news)} 篇全文**\n")

    path = os.path.join(OUTDIR, f"{NAME}+第1次实验-数据来源清单.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("数据来源清单已生成:", path)
    print(f"  标题语料 {n_titles} 条 | 正文 主题 {themed_total} 篇 + news20 {len(news)} 篇")
    return path


if __name__ == "__main__":
    main()
