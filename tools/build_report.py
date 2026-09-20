# -*- coding: utf-8 -*-
"""生成《内容重复理解技术综合实验》实验报告 Word 文档

数据来源：out/*.txt（各实验落盘结果）、out/figures/*.png（可视化）、
         out/screenshots/*.png（关键代码白底截图）
"""
import os
import re

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "out")
FIG = os.path.join(OUT, "figures")
SHOT = os.path.join(OUT, "screenshots")
FONT = "微软雅黑"


# ------------------------- 基础排版工具 -------------------------
def set_run(run, size=10.5, bold=False, color=None, name=FONT):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)


def h(doc, text, level=1):
    sizes = {0: 20, 1: 15, 2: 13, 3: 11.5}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10 if level else 0)
    p.paragraph_format.space_after = Pt(6)
    set_run(p.add_run(text), size=sizes.get(level, 11.5), bold=True)
    return p


def para(doc, text, size=10.5, bold=False, indent=True, align=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.35
    if indent:
        p.paragraph_format.first_line_indent = Pt(21)
    if align:
        p.alignment = align
    set_run(p.add_run(text), size=size, bold=bold)
    return p


def caption(doc, text, before=2, after=8):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    set_run(p.add_run(text), size=9, bold=True, color=(0x44, 0x44, 0x44))
    return p


def add_image(doc, path, cap=None, max_w=6.1, max_h=6.6):
    if not os.path.exists(path):
        para(doc, f"[缺失图片: {os.path.basename(path)}]", size=9)
        return
    w, hh = Image.open(path).size
    inch_w = max_w
    inch_h = inch_w * hh / w
    if inch_h > max_h:
        inch_h = max_h
        inch_w = inch_h * w / hh
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(path, width=Inches(inch_w))
    if cap:
        caption(doc, cap)


def add_table(doc, headers, rows, cap=None, widths=None, size=9):
    if cap:
        caption(doc, cap, after=3)
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, hd in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run(p.add_run(str(hd)), size=size, bold=True)
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i else WD_ALIGN_PARAGRAPH.LEFT
            set_run(p.add_run(str(v)), size=size)
    if widths:
        for row in t.rows:
            for i, wd in enumerate(widths):
                row.cells[i].width = Inches(wd)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def read(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as f:
        return f.read()


# ------------------------- 结果解析 -------------------------
def parse_tfidf():
    txt = read("exp1_tfidf_results.txt")
    scale = re.search(r"规范化去重后语料规模: (\d+)", txt).group(1)
    raw_scale = re.search(r"语料规模\(原始\): (\d+)", txt).group(1)
    removed = re.search(r"移除的空白/大小写重复标题数: (\d+)", txt)
    shape = re.search(r"矩阵形状: (\([\d, ]+\))", txt).group(1)
    pairs = re.findall(r"\d+\. 相似度=([\d.]+)\n\s+A\[(\d+)\]: (.*?)\n\s+B\[(\d+)\]: (.*)", txt)
    words = re.findall(r"^(\S+)\t词频=(\d+)\t平均TF-IDF=([\d.]+)\t进入特征集=(\S+)", txt, re.M)

    stats = {}
    m = re.search(r"相似度统计: 文本对总数=(\d+) 均值=([\d.]+) P50=([\d.]+) P99=([\d.]+) 最大=([\d.]+)", txt)
    if m:
        stats.update(dict(zip(["n_pairs", "mean", "p50", "p99", "max"], m.groups())))
    m = re.search(r"相似度>=0\.9 文本对=(\d+)\s+>=0\.5=(\d+)\s+>=0\.3=(\d+)", txt)
    if m:
        stats.update(dict(zip(["ge9", "ge5", "ge3"], m.groups())))
    m = re.search(r"Top-10 中相似度>=0\.3 的文本对数: (\d+)", txt)
    if m:
        stats["top10_ge3"] = m.group(1)
    stats["raw_scale"] = raw_scale
    stats["removed"] = removed.group(1) if removed else "0"
    return scale, shape, pairs, words, stats


def parse_minhash():
    txt = read("exp1_minhash_results.txt")
    sims = re.findall(r"T(\d+)-T(\d+): Jaccard=([\d.]+)\s+MinHash=([\d.]+)\s+LSH候选=(\S*)", txt)
    err = re.search(r"平均绝对误差: ([\d.]+)\s+最大: ([\d.]+)", txt)
    # 两套阈值表：混合口径在前，分层口径在后；用完整表头行定位切分点
    marker = "=== 分层口径（修正后）"
    split = txt.find(marker)
    if split < 0:
        raise ValueError(f"未在 exp1_minhash_results.txt 中定位到分层口径表头 {marker!r}")
    head_txt, tail_txt = txt[:split], txt[split:]
    row_re = r"^ ([\d.]+) \| ([\d.]+)/([\d.]+)/([\d.]+) \| ([\d.]+)/([\d.]+)/([\d.]+)"
    thr_mixed = re.findall(row_re, head_txt, re.M)
    thr = re.findall(row_re, tail_txt, re.M)
    lsh = re.findall(r"^--- LSH\(b=(\d+), r=(\d+)\) 候选 (\d+) 对 ---", txt, re.M)
    lsh_items = re.findall(r"T(\d+)-T(\d+): MinHash 相似度=([\d.]+) -> (\S+)", txt)
    run = re.findall(r"^\s+(\d+) \| *([\d.]+)ms \| *([\d.]+)ms \| *([\d.]+)ms \| *([\d.]+)ms \| "
                     r"(\d+) \| (\d+) \| (\d+) \| ([\d.]+)", txt, re.M)
    return sims, err, thr_mixed, thr, lsh, lsh_items, run


def parse_wordvec():
    txt = read("exp2_wordvec_results.txt")
    model = re.search(r"模型信息: (.*)", txt).group(1)
    analogies = re.findall(r"^  (\S+)-(\S+)\+(\S+) 期望≈(\S+) \| 实际: (.*?)(★命中)?$", txt, re.M)
    pairs = re.findall(r"sim\((\S+), (\S+)\) = ([\d.]+)", txt)
    intra = re.search(r"类内平均相似度: ([\d.]+)\s+类间平均相似度: ([\d.]+)", txt)
    km = re.search(r"聚类纯度 Purity = ([\d.]+)\s+调整兰德指数 ARI = ([\d.]+)", txt)
    conf = re.findall(r"^    (体育|科技|娱乐): \[([\d, ]+)\]", txt, re.M)
    cover = re.search(r"整体词表覆盖率: ([\d.]+)% \(([\d/]+)\)", txt)
    return model, analogies, pairs, intra, km, conf, cover


def parse_simhash():
    txt = read("exp2_simhash_results.txt")
    head = re.search(r"数据集: (\d+) 篇新闻", txt)
    gold = re.search(r"改写簇近似重复对=(\d+)\s+同事件不同报道对=(\d+)\s+初版混合口径\(所有同组对\)=(\d+)", txt)
    # 每个方案两行：修正口径在前，初版口径在后
    res, mixed = {}, {}
    for m in re.finditer(r"^(\S+?) SimHash:\s*\n\s+修正口径[^:]*: P=([\d.]+) R=([\d.]+) F1=([\d.]+) "
                         r"TP=(\d+) FP=(\d+) FN=(\d+)\s*\n\s+初版口径[^:]*: P=([\d.]+) R=([\d.]+) "
                         r"F1=([\d.]+) TP=(\d+) FP=(\d+) FN=(\d+)", txt, re.M):
        name = m.group(1)
        res[name] = (m.group(2), m.group(3), m.group(4), m.group(5), m.group(6), m.group(7))
        mixed[name] = (m.group(8), m.group(9), m.group(10), m.group(11), m.group(12), m.group(13))
    # 阈值扫描（修正口径）：三列并排
    sweep = []
    for m in re.finditer(r"^阈值=\s*(\d+): TF-IDF加权 P=([\d.]+) R=([\d.]+) F1=([\d.]+) \| "
                         r"等权 P=([\d.]+) R=([\d.]+) F1=([\d.]+) \| "
                         r"唯一词 P=([\d.]+) R=([\d.]+) F1=([\d.]+)", txt, re.M):
        g = m.groups()
        sweep.append((g[0], (g[1], g[2], g[3]), (g[4], g[5], g[6]), (g[7], g[8], g[9])))
    return head, gold, res, mixed, sweep


# ------------------------- 报告主体 -------------------------
def build():
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)

    # ===== 封面 =====
    for _ in range(3):
        doc.add_paragraph()
    h(doc, "内容重复理解技术综合实验", 0)
    h(doc, "实 验 报 告", 1)
    doc.add_paragraph()
    for line in ["实验名称：文本特征表示与短文本去重 / 文本相似度计算",
                 "实验课程：自然语言处理",
                 "姓名：<成员一姓名>    学号：<成员一学号>",
                 "日期：2026 年 9 月 20 日"]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run(p.add_run(line), size=12)
    doc.add_page_break()

    # ===== 一、实验环境 =====
    h(doc, "一、实验环境与依赖", 1)
    add_table(doc, ["项目", "说明"], [
        ["操作系统", "Windows"],
        ["开发语言", "Python 3.13.5（已验证可运行；依赖版本见 requirements.txt）"],
        ["中文分词", "jieba 0.42.1"],
        ["机器学习/特征", "scikit-learn 1.8.0（TfidfVectorizer、cosine_similarity、PCA、TSNE、KMeans）"],
        ["词向量", "gensim 4.4.0（KeyedVectors）"],
        ["数值/绘图", "numpy 2.3.5、matplotlib（Microsoft YaHei 中文字体）"],
        ["网页抓取", "requests + BeautifulSoup(lxml)"],
        ["文档与截图", "python-docx、Pillow"],
        ["预训练词向量模型", "腾讯 AI Lab 中文词向量（800 万词轻量版），143613 词 × 200 维"],
    ], cap="表 1-1 实验环境与依赖", widths=[1.6, 4.4])
    para(doc, "说明：预训练模型体积较大（116 MB），按作业要求不随代码压缩包提交；"
              "运行 exp2_wordvec.py 前需将模型文件放到 model/ 目录（见附录复现步骤）。")
    para(doc, "另需说明：本报告的全部指标均由本目录代码现场运行生成，落盘于 out/*_results.txt；"
              "对早期版本结果的逐行对照见 out/_baseline_original/ 与 out/AUDIT_NOTES.md。")

    # ===== 二、实验材料获取 =====
    h(doc, "二、实验材料获取（真实语料抓取）", 1)
    para(doc, "本次实验的全部语料均来自互联网真实新闻站点实时抓取，未使用任何现成的标注数据集，"
              "抓取脚本见 tools/ 目录（scraper.py / fetch.py / fetch_titles.py）。抓取流程与数据规模如下表。")
    add_table(doc, ["数据文件", "规模", "获取方式", "用途"], [
        ["data/titles.txt", "2579 条", "网易滚动新闻接口（GBK JSON）+ 新浪滚动新闻 API，多频道分页聚合",
         "实验一(1) TF-IDF 语料（要求≥500 条）"],
        ["data/sports/*.txt\ndata/tech/*.txt\ndata/ent/*.txt", "各 50 篇\n（共 150 篇）",
         "上述接口取标题/链接后，逐篇抓取正文并用 BeautifulSoup 解析（h1 标题 + 正文容器）",
         "实验二(1) 三类主题文档向量"],
        ["data/news20/*.txt\n+ manifest.json", "20 篇",
         "真实新闻为源文：同一事件的多家媒体报道 + 转载改写 + 完全不同主题；"
         "改写簇由同义词替换、换标题、调段序规则化生成，并写入 group/rewrite 标注",
         "实验二(2) 加权 SimHash 相似度"],
        ["data/short_texts.txt", "6 条", "人工设计：完全重复 / 轻度修改 / 中度改写 / 完全不相关四类",
         "实验一(2) MinHash+LSH 去重"],
    ], cap="表 2-1 实验材料获取一览", widths=[1.5, 0.9, 3.0, 1.3])
    para(doc, "每条新闻全文均保存为统一格式：首行 title=、第二行 source=（原始 URL）、第三行 category=，"
              "空行后为正文，便于溯源与复核（news20 额外含 group= / rewrite= 两行标注）。"
              "解析时统一按“首个空行”切分元信息与正文。")

    # ===== 三、实验题目一 =====
    h(doc, "三、实验题目一：文本特征表示与短文本去重", 1)

    # ---------- 3.1 TF-IDF ----------
    scale, shape, pairs, words, st = parse_tfidf()
    tm_stats = [
        ["原始语料条数", st.get("raw_scale", "-")],
        ["规范化去重后语料条数", scale],
        ["移除的空白/大小写重复条目", f"{st.get('removed', '0')} 条"],
        ["TF-IDF 矩阵形状", shape],
        ["文本对总数", f"{int(st['n_pairs']):,}" if "n_pairs" in st else "-"],
        ["相似度均值 / P50", f"{st.get('mean', '-')} / {st.get('p50', '-')}"],
        ["相似度 P99 / 最大值", f"{st.get('p99', '-')} / {st.get('max', '-')}"],
        ["相似度 ≥0.9 / ≥0.5 / ≥0.3 的文本对",
         f"{st.get('ge9', '-')} / {st.get('ge5', '-')} / {st.get('ge3', '-')}"],
        ["Top-10 中相似度 ≥0.3 的对数", f"{st.get('top10_ge3', '-')} / 10"],
    ]
    h(doc, "3.1 基于 TF-IDF 的文本特征表示与相似度检索", 2)
    h(doc, "3.1.1 实验目的", 3)
    para(doc, "掌握基于 TF-IDF 的文本特征提取方法，理解词袋模型（Bag-of-Words）与词向量的区别；"
              "能够用余弦相似度度量文档相似性，并借助可视化分析词的权重分布。")

    h(doc, "3.1.2 算法原理", 3)
    para(doc, "TF-IDF（Term Frequency–Inverse Document Frequency）由词频 TF 与逆文档频率 IDF 相乘得到，"
              "用于衡量一个词对某篇文档的区分能力：")
    for f in ["TF(t, d) = 词 t 在文档 d 中出现的次数 / 文档 d 的总词数；",
              "IDF(t) = ln((1 + N) / (1 + DF(t))) + 1，其中 N 为文档总数，DF(t) 为包含词 t 的文档数；",
              "TF-IDF(t, d) = TF(t, d) × IDF(t)。"]:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Pt(28)
        p.paragraph_format.space_after = Pt(2)
        set_run(p.add_run("• " + f), size=10.5)
    para(doc, "可见某词在本篇出现越多、而在全局出现越少，其权重越高；反之像“的、了”这类高频停用词的 IDF 很低，"
              "权重被自然抑制。本实验进一步设置 ngram_range=(1,2)，即同时保留单字/单词与相邻二元组，"
              "以捕捉“超级智能体”这类固定搭配。")
    para(doc, "文档相似度采用余弦相似度：将每篇文档的 TF-IDF 向量视作高维空间中的向量，"
              "计算两向量夹角的余弦值 cos(A,B) = (A·B) / (|A||B|)，取值在 [0,1] 之间，越接近 1 越相似。"
              "余弦相似度对文档长度不敏感，适合长短不一的新闻文本。")

    h(doc, "3.1.3 关键代码解读", 3)
    add_image(doc, os.path.join(SHOT, "exp1_tfidf_core.png"),
              "图 3-1 TF-IDF 特征构建与 Top-10 相似对检索（白底代码截图）")
    para(doc, f"代码要点：① jieba 分词后去除停用词与纯标点/数字，用空格连接为 TfidfVectorizer 可识别的输入；"
              f"② 以 max_features=1000、ngram_range=(1,2) 构建 TF-IDF 矩阵，实际得到 {shape}；"
              f"③ 只在**上三角**（i<j）中排序取前 10。这一点很关键：早期实现先 fill_diagonal(-1)、"
              f"再对展平后的整个矩阵 argsort，会把 (i,j) 与 (j,i) 当成两个不同的结果同时取到，"
              f"使“Top-10”实际只包含约 5 个不同的文本对；改用 np.triu_indices 后每一个文本对只出现一次。")
    add_image(doc, os.path.join(SHOT, "exp1_tfidf_dedup.png"),
              "图 3-2 语料规范化与去重（normalize_title / dedup_titles）")
    para(doc, "代码要点：先把标题的空格全部压缩掉并统一小写，再按该键去重并统计移除条数。"
              "这样既消除了“仅排版不同”的伪重复，又不改动原始语料文件，便于复核。")
    add_image(doc, os.path.join(SHOT, "exp1_tfidf_weight_lookup.png"),
              "图 3-3 TF-IDF 权重回查：大小写对齐与“是否进入特征集”标记")
    para(doc, "代码要点：回查权重时用 w.lower() 与 TfidfVectorizer(lowercase=True) 的特征名对齐；"
              "同时记录该词是否命中特征集，输出为独立的“进入特征集”列。"
              "早期实现用原始大小写去查 feature_names，导致含英文的词必然查不到而被误判为权重 0。")

    h(doc, "3.1.4 实验结果", 3)
    para(doc, f"语料规模：{scale} 条中文新闻标题（满足 ≥500 条要求）；TF-IDF 矩阵形状：{shape}。")
    add_table(doc, ["统计项", "数值"], tm_stats,
              cap="表 3-1 语料规范化与相似度分布统计", widths=[3.0, 2.0])
    add_table(doc, ["排名", "余弦相似度", "文本 A", "文本 B"],
              [[i + 1, f"{float(s):.4f}", f"[{a}] {ta[:34]}", f"[{b}] {tb[:34]}"]
               for i, (s, a, ta, b, tb) in enumerate(pairs)],
              cap="表 3-2 相似度最高的 Top-10 文本对", widths=[0.5, 0.9, 2.4, 2.4])
    add_table(doc, ["词", "词频", "平均 TF-IDF 权重", "进入特征集"],
              [[w, fq, wx, ok] for w, fq, wx, ok in words],
              cap="表 3-3 词频最高的 20 个词及其平均 TF-IDF 权重", widths=[1.2, 1.0, 1.8, 1.2])
    add_image(doc, os.path.join(FIG, "exp1_tfidf_top20.png"),
              "图 3-2 词频最高的 20 个词的 TF-IDF 权重柱状图")

    h(doc, "3.1.5 结果分析", 3)
    for s in [
        "语料规范化的重要性：原始 2579 条标题中存在 3 条（0.12%）仅空格/大小写差异的重复条目"
        "（如“腾势 D9 车型 OTA 升级”与“腾势D9车型OTA升级”）。由于 jieba 分词后词序列完全一致，"
        "这类条目对的余弦相似度恒为 1.0000，会在 Top-10 中霸榜，掩盖真正的相似文本。"
        "因此在语料加载阶段按“去空白 + 统一小写”规范化并去重，最终有效语料 2576 条。"
        "这说明数据清洗不是可选项——它会直接决定相似度检索结果的可读性。",
        "Top-10 全部是“模板化近似重复”：修正后 Top-10 中 10 对相似度均为 1.0000，"
        "且全部来自模板化批量内容——9 对是“微博观影团《X》北京首映免费抢票”（仅影片名不同），"
        "1 对是“253期X福彩3D预测奖号：X推荐”（仅人名/玩法不同）。"
        "经统计，2576 条有效标题中模板化标题共 218 条（8.5%）：彩票预测类 101 条、竞彩/指数类 40 条、"
        "影迷评 29 条、公司增持减持 25 条、微博观影团抢票 24 条。"
        "仅占 8.5% 的模板内容却占据了相似度的最顶端，因为模板文本的 TF-IDF 向量几乎完全相同。"
        "这一方面实证了“TF-IDF+余弦对机器批量生成内容极为敏感”，可用于识别低质内容；"
        "另一方面也提醒：若把 Top-10 直接当作“新闻事件重复”来解读，会严重误判。",
        "相似度 1.0 不等于语义相同：以“109期张世奇双色球预测奖号：大小比参考”与"
        "“109期林必立双色球预测奖号：大小比参考”为例，人名（张世奇/林必立）是两篇的关键差异，"
        "但人名经分词后被停用词表与纯数字规则过滤，剩余词完全一致，于是向量相同、相似度为 1。"
        "同理“[小炮APP]专家齐大力竞彩推荐：日职+德甲2串1”与“…意甲西甲2串1”也判为 1.0。"
        "这正是词袋模型“只看词共现、不看词序与关键实体”的固有天花板。",
        "词频与 TF-IDF 权重并非正相关（表 3-3、图 3-2）：高频词“预测（121 次）”“奖号（119 次）”"
        "的平均权重只有 0.2763/0.2749，因为它们在大量文档中共同出现、IDF 很低；"
        "而“电影”词频仅 40 次，平均权重却最高（0.4560），“人（0.4237）”“特朗普（0.4123）”"
        "“俄（0.4067）”同理——它们集中于少数文档，区分度强。这与 TF-IDF 的设计初衷完全吻合。",
        "关于“AI”一词的权重（一个必须澄清的坑）：语料中“AI”词频 82 次，平均 TF-IDF 权重 0.3566，"
        "**一直在特征集内**。需要特别说明的是，早期实现曾在分词阶段保留英文原形（token 为“AI”），"
        "而 TfidfVectorizer 默认 lowercase=True 使特征名变为“ai”，"
        "按特征名回查权重时因大小写不匹配而必然落空，把该词误报成“权重 0.0000、未进入特征集”。"
        "修正方式是分词阶段统一转小写，与 lowercase 参数对齐；同时在结果中增加“进入特征集”一列，"
        "使“真正被 max_features 截断”与“因键名不匹配查不到”这两种情况可以被直接区分。"
        "这个案例说明：特征矩阵算对了，不代表按名字取值就取对了。",
    ]:
        para(doc, s)

    # ---------- 3.2 MinHash + LSH ----------
    sims, err, thr_mixed, thr, lsh, lsh_items, run = parse_minhash()
    h(doc, "3.2 基于 MinHash + LSH 的短文本近似去重", 2)
    h(doc, "3.2.1 实验目的", 3)
    para(doc, "理解并实现基于 Jaccard 系数与 MinHash 的近似文本去重，掌握 LSH 分桶的近似近邻查找思想；"
              "通过对比精确计算与近似计算，量化二者在准确率与运行时间上的差异，并分析阈值的影响。")

    h(doc, "3.2.2 算法原理", 3)
    para(doc, "（1）Jaccard 相似度。把文本表示为 shingle（n-gram）集合，两集合的 Jaccard 相似度为 "
              "J(A,B) = |A∩B| / |A∪B|。本实验采用词级 1+2-gram：既保留单个词，也保留相邻词对（用“|”连接），"
              "在字面重合与语义容忍之间取得平衡（纯字符 5-gram 对中度改写会因词序调整而失效）。")
    para(doc, "（2）MinHash 签名。直接两两求交并集的复杂度为 O(n²·|S|)。MinHash 通过 k 个随机哈希函数 "
              "h_i(x) = (a_i·x + b_i) mod P（P 取梅森素数 2⁶¹−1）为每个集合生成 k 维签名："
              "签名第 i 位取集合中所有元素 h_i 的最小值。理论可证明，两个签名第 i 位相等的概率恰等于两集合的 "
              "Jaccard 相似度，因此可用签名相同位数的比例无偏估计 Jaccard。本实验取 k=128。")
    para(doc, "（3）LSH 分桶。把 128 维签名切成 b 个 band，每个 band 含 r 行（b·r=128）。"
              "只有至少一个 band 完全相同的文档对才进入候选集，从而把 O(n²) 的比较量降到近似 O(n)；"
              "对候选对再用 MinHash 相似度精确回验。band 数越多、r 越小，召回越高但候选越多（精确率下降）。")

    h(doc, "3.2.3 测试用例设计", 3)
    para(doc, "共设计 6 条短文本用例，覆盖完全重复、轻度修改、中度改写、完全不相关四类。"
              "需要强调的是：这 6 条用例内部其实有**三个相似度量级**，因此金标准必须分层，"
              "而不能把 T1~T4 两两全部当作“重复”（实测 T1-T4/T3-T4 的 Jaccard 只有 0.1875/0.1176，"
              "与完全重复的 1.0000 相差一个量级）：")
    add_table(doc, ["编号", "文本", "类别", "层级"], [
        ["T1", "中国代表团在亚运会收获首金，女子现代五项团体成功卫冕", "原始文本", "—"],
        ["T2", "中国代表团在亚运会收获首金，女子现代五项团体成功卫冕", "完全重复（与 T1 逐字相同）", "近重复"],
        ["T3", "中国代表团亚运首金到手，女子现代五项团队成功卫冕", "轻度修改（删词/换词）", "近重复（J=0.31）"],
        ["T4", "卫冕成功！现代五项女子团体为中国队拿下本届亚运会第一枚金牌", "中度改写（换句序/同义替换）", "同事件改写（J=0.12~0.19）"],
        ["T5", "马斯克否认特斯拉向xAI投资五十亿美元参股计划", "完全不相关（同领域不同事件）", "不相关（J=0）"],
        ["T6", "佟丽娅公开回应与陈思诚的离婚传闻，称两人早已分开", "完全不相关（不同领域）", "不相关（J=0）"],
    ], cap="表 3-4 MinHash+LSH 实验的 6 个测试用例与分层", widths=[0.55, 3.9, 1.55, 1.4])
    para(doc, "分层规则：**近重复 = T1-T2**（字面几乎一致）；**同事件改写 = T1/T2/T3 与 T4 的 5 对**"
              "（事件相同但句子结构重写，不计入“近似重复”正样本，另计命中数）；"
              "**不相关 = T5/T6 与其余文本**（相似度全为 0.0000，与 T1~T4 之间存在天然的间隔带）。"
              "报告同时给出“初版混合口径”（T1~T4 两两共 6 对）与“分层口径”两套指标，便于对照。")

    h(doc, "3.2.4 关键代码解读", 3)
    add_image(doc, os.path.join(SHOT, "exp1_minhash_update.png"),
              "图 3-4 MinHash 签名生成（k=128，exp1_minhash.py）")
    para(doc, "代码要点：签名初始化为一维 k 长数组（初值 P）；对集合中每个 shingle 计算其 64 位整数哈希后，"
              "逐个哈希函数取最小值。实现上刻意使用纯 Python 大整数运算而非 numpy 向量化："
              "因为 a_i·x 的量级接近 2¹²²，超出 numpy int64 的范围会造成溢出，属于典型的“数学正确但工程踩坑”问题。")
    add_image(doc, os.path.join(SHOT, "exp1_lsh.png"),
              "图 3-5 LSH 分桶与候选对生成（build_lsh_tables / lsh_candidates）")
    para(doc, "代码要点：把签名按 band 切片并作为 dict 的 key 建立倒排桶；同一桶内文档两两组合即为候选对，"
              "用 set 去重。整个过程只需一次线性扫描，避免了全量两两比较。")
    add_image(doc, os.path.join(SHOT, "exp1_minhash_prf.png"),
              "图 3-6 P/R/F1 计算（prf）——分母为空时返回 0 并同时输出 TP/FP/FN")
    para(doc, "代码要点：早期实现把“没有预测”时的查准率定义为 1.0，于是出现“一对都没检出却 F1 = 1.000”"
              "的荒谬结论。修正为分母为空时取 0，并让函数同时返回 TP/FP/FN，"
              "使“无预测”与“全对”在结果里不可能再被混淆。")

    h(doc, "3.2.5 实验结果", 3)
    rows3 = [[f"T{i}-T{j}", jac, mh, ("是" if mark else "否")] for i, j, jac, mh, mark in sims]
    add_table(doc, ["文本对", "精确 Jaccard", "MinHash 估计", "进入 LSH 候选"], rows3,
              cap="表 3-5 各文本对的精确 Jaccard 与 MinHash 估计对比", widths=[1.4, 1.6, 1.6, 1.6])
    para(doc, f"MinHash 估计的平均绝对误差为 {err.group(1)}，最大误差 {err.group(2)}，"
              f"说明 k=128 的签名已能高精度逼近真实 Jaccard（签名长度越长误差越小，误差量级约为 1/√k）。")

    rows_mixed = [[f"{t}", f"{p1}/{r1}/{f1}", f"{p2}/{r2}/{f2}"] for t, p1, r1, f1, p2, r2, f2 in thr_mixed]
    add_table(doc, ["相似度阈值", "精确 Jaccard（P/R/F1）", "MinHash（P/R/F1）"], rows_mixed,
              cap="表 3-6 阈值影响（初版混合口径：ground truth = T1~T4 两两，共 6 对）",
              widths=[1.4, 2.3, 2.3])
    rows_thr = [[f"{t}", f"{p1}/{r1}/{f1}", f"{p2}/{r2}/{f2}"] for t, p1, r1, f1, p2, r2, f2 in thr]
    add_table(doc, ["相似度阈值", "精确 Jaccard（P/R/F1）", "MinHash（P/R/F1）"], rows_thr,
              cap="表 3-7 阈值影响（分层口径：ground truth = 近重复对 T1-T2）", widths=[1.4, 2.3, 2.3])

    lsh_rows = []
    for bi, ri, cnt in lsh:
        lsh_rows.append([f"b={bi}, r={ri}", cnt, "—"])
    add_table(doc, ["LSH 配置", "候选对数", "说明"], lsh_rows,
              cap="表 3-8 两种 LSH 分桶参数下的候选对数量", widths=[1.6, 1.4, 3.0])
    rows5 = [[f"T{i}-T{j}", mh, st] for i, j, mh, st in lsh_items]
    add_table(doc, ["候选文本对（b=64, r=2）", "MinHash 相似度", "回验结论"], rows5,
              cap="表 3-9 LSH 候选对的相似度回验", widths=[1.6, 1.6, 1.6])

    rows6 = [[m, ej, mj, f"{lj} / {lj2}", f"{tj} 对", f"{cj} / {cj2}", f"{float(pr):.2%}"]
             for m, ej, mj, lj, lj2, tj, cj, cj2, pr in run]
    add_table(doc, ["文档数", "精确 Jaccard", "MinHash 签名+全量", "LSH 建桶耗时\n(b16r8 / b64r2)",
                    "全量对数", "LSH 候选数\n(b16r8 / b64r2)", "剪枝率(b16r8)"], rows6,
              cap="表 3-10 批量规模对运行时间的影响（真实标题语料，单位毫秒）",
              widths=[0.8, 1.15, 1.3, 1.35, 0.95, 1.25, 0.9], size=8)
    add_image(doc, os.path.join(FIG, "exp1_minhash_sim.png"),
              "图 3-7 MinHash 估计 vs 精确 Jaccard（左）与两种金标准口径下的 F1（右）")
    add_image(doc, os.path.join(FIG, "exp1_minhash_scaling.png"),
              "图 3-8 批量规模对计算耗时的影响（对数纵轴）")

    h(doc, "3.2.6 结果分析", 3)
    for s in [
        "MinHash 估计精度：T1-T2（完全重复）估计值 1.0000 与精确值一致；"
        "T1-T3（轻度修改）精确 0.3077 vs 估计 0.3203，T1-T4（中度改写）精确 0.1875 vs 估计 0.1641；"
        "完全不相关的 T5、T6 与其余文本精确值与估计值均为 0.0000。"
        f"整体平均绝对误差仅 {err.group(1)}（最大 {err.group(2)}），"
        "验证了 MinHash 作为 Jaccard 无偏估计的有效性。",
        "金标准分层如何改变结论（表 3-6 vs 表 3-7）：这是本次实验最有价值的一处修正。"
        "在**混合口径**下（把 T1~T4 两两都当重复），阈值 0.1 处精确与近似方法的 F1 都是 0.909~1.000，"
        "看起来“阈值取 0.1 就是最优”；但这个结论是脆弱的——它完全建立在"
        "“把 0.12 相似度的中度改写也算作重复”这一设定上。"
        "改用**分层口径**（正样本只有真正字面重复的 T1-T2）后，同一批数据的曲线形状完全变了："
        "阈值 0.2~0.3 时 F1 只有 0.500，阈值 ≥0.4 时才升到 1.000。"
        "也就是说：**“最优阈值”不是一个算法常数，而是由业务对“什么算重复”的定义决定的**。"
        "去重要求“只删真重复”，阈值取 0.4；内容收敛要求“把改写稿也一并合并”，阈值取 0.1~0.2"
        "（此区间能召回 5/6 对改写稿且零误报）。",
        "近似 vs 精确：在分层口径下 MinHash 与精确 Jaccard 的 P/R/F1 在全部阈值上完全一致"
        "（0.4 及以上均为 1.000/1.000/1.000）。这说明 k=128 的签名精度已足以支撑本次判定任务；"
        "在混合口径下 MinHash 于阈值 0.1 处的 F1 为 0.909，略低于精确方法的 1.000，"
        "差异来自 T3-T4 的估计值 0.0938 被压到阈值以下（精确值 0.1176 高于阈值）。"
        "这正是近似算法“用少量精度换取大量效率”的本质——误差可控且可解释。",
        "LSH 分桶参数的取舍（表 3-8、3-9）：(b=16, r=8) 只产生 1 对候选，"
        "把 5 对同事件改写全部漏掉；(b=64, r=2) 产生 6 对候选，覆盖全部 T1~T4 之间的相似对，"
        "但其中 3 对（T1-T4/T2-T4/T3-T4）经相似度回验后相似度 <0.2 被剔除。"
        "这恰好演示了工业界的三段式做法：**LSH 粗筛候选 → MinHash 相似度回验 → 阈值判定**。",
        "运行时间与规模（表 3-10、图 3-8）：精确 Jaccard 随文档数呈平方增长（O(n²·|S|)），"
        "500 篇耗时约 134 ms；MinHash 全量对比虽把集合运算换成签名比较，但比较次数仍是 O(n²)，"
        "且 128 个哈希函数的签名生成本身开销不小，500 篇合计约 635 ms"
        "（其中签名生成约 12 ms/篇的量级，是纯 Python 大整数运算的代价）。"
        "而 LSH 建桶只需一次线性扫描：500 篇时 (b=16,r=8) 仅约 8 ms、(b=64,r=2) 约 28 ms。"
        "关键是**签名与索引都是一次性成本**，建成后每次查询只与同桶文档比较，"
        "规模越大优势越明显——这正是搜索引擎与去重系统采用 LSH 的原因。",
        "关于剪枝率的一个反直觉现象：在真实标题语料上，(b=16, r=8) 的候选对在 200 篇时为 **0** 对，"
        "500 篇也只有 3 对。原因是该配置要求“某个 8 行的 band 完全相同”，"
        "碰撞概率约为 s⁸ 量级以上的命中，只对相似度 ≥0.9 的文档有效；"
        "而真实新闻标题两两的 Jaccard 普遍低于 0.3（全语料相似度 P99 仅 0.208），因此几乎全被剪掉。"
        "这说明 **LSH 参数必须按目标相似度区间标定**：要高召回就必须用 (b=64, r=2) 这类小 r 配置，"
        "不能照搬“band 越多越好”或“rows 越大越省”的经验。"
        "（相比之下，早期版本用“6 条用例重复拼接”造出的规模实验，文档几乎相同、相似度极高，"
        "候选对高达 27640 对，反而掩盖了这个真实问题。）",
    ]:
        para(doc, s)

    # ===== 四、实验题目二 =====
    h(doc, "四、实验题目二：文本相似度计算", 1)

    # ---------- 4.1 词向量 ----------
    model, anas, wpairs, intra, km, conf, cover = parse_wordvec()
    h(doc, "4.1 基于预训练词向量的文本表示与语义分析", 2)
    h(doc, "4.1.1 实验目的", 3)
    para(doc, "掌握使用预训练词向量进行文本表示的方法，理解 Word2Vec 与 GloVe 的差异；"
              "验证词向量的语义推理能力，并通过文档向量与聚类/降维可视化观察主题分布。")
    h(doc, "4.1.2 预处理说明", 3)
    para(doc, "本实验使用腾讯 AI Lab 中文词向量。原版模型体积达数 GB，官方下载链接已失效，"
              "故改用其官方发布的 800 万词轻量版（Light 版，143613 词 × 200 维，116 MB），"
              "由 gensim 以 Word2Vec 二进制格式直接加载。")

    h(doc, "4.1.3 算法原理", 3)
    para(doc, "（1）Word2Vec 与 GloVe 的差异。Word2Vec（本实验使用的模型家族）是预测式方法："
              "CBOW 用上下文预测中心词、Skip-gram 用中心词预测上下文，本质是训练一个浅层神经网络，"
              "词向量是该网络的副产物。GloVe 是计数式方法：先统计全局共现矩阵，再对其做加权最小二乘分解，"
              "直接拟合“词-词共现概率的比值”。两者最终都能得到“语义相近的词向量夹角小”的效果，"
              "Word2Vec 更偏局部上下文、训练更灵活，GloVe 更充分利用全局统计信息。")
    para(doc, "（2）语义推理。词向量空间具有线性结构，可用向量加减做类比推理："
              "vec(国王) − vec(男人) + vec(女人) ≈ vec(王后)。实现上调用 "
              "most_similar(positive=[国王, 女人], negative=[男人]) 求最相近的词。")
    para(doc, "（3）文档向量（平均池化）。词向量只表示词，要表示一篇文档，最简单有效的方式是对文档中"
              "所有词的词向量取平均：v_doc = (1/|W|)·Σ v_word，即 Doc2Vec 平均池化。"
              "它假设各词贡献均等、不考虑词序，但实现简单且在主题分类任务上表现稳定。")
    para(doc, "（4）PCA / t-SNE 与 KMeans。PCA 是线性降维，保留方差最大的方向，能反映全局结构；"
              "t-SNE 是非线性降维，通过保持高维空间中近邻点的概率分布来投影，更擅长展现局部簇结构。"
              "KMeans 在 200 维文档向量上做 K=3 聚类，用聚类纯度 Purity 与调整兰德指数 ARI 衡量"
              "“无监督聚类结果与真实主题的一致性”。")

    h(doc, "4.1.4 关键代码解读", 3)
    add_image(doc, os.path.join(SHOT, "exp2_wordvec_load.png"),
              "图 4-1 Gensim 加载预训练词向量与语义推理（白底代码截图）")
    para(doc, "代码要点：用 KeyedVectors.load_word2vec_format 加载二进制模型；"
              "类比推理的正负样本方向必须写对——欲求 a − b + c，应传 positive=[a, c]、negative=[b]。"
              "本实验最初写反为 positive=[b, c]、negative=[a]，结果返回“是男人”这类错误答案，修正后正确命中“王后”。")
    add_image(doc, os.path.join(SHOT, "exp2_parse_doc.png"),
              "图 4-2 新闻文件元信息解析：按首个空行严格切分（parse_doc）")
    para(doc, "代码要点：元信息块与正文之间有一个空行，必须按**首个空行**切分。"
              "早期实现用 raw.split(\"\\n\", 3)[3] 取正文，只切掉 3 个换行，"
              "结果把 news20 特有的 group= / rewrite= 两行当成正文词混入文档（实测 doc 01 的正文以"
              "“group=R1\\nrewrite=\\n\\n\\n智东西…”开头），会虚增词表覆盖率。"
              "本实验的三个主题目录没有这两行，因此主题文档向量结果不受影响，但该缺陷一旦遇到带标注的语料就会污染向量。")
    add_image(doc, os.path.join(SHOT, "exp2_docvector.png"),
              "图 4-3 词向量平均池化生成文档向量（doc_vector）")
    para(doc, "代码要点：只累加词表中存在的词向量（OOV 词直接跳过），并同时返回命中词数与总词数，"
              "以便统计词表覆盖率；若一篇文档所有词都不在词表则返回 None 并丢弃，避免产生零向量污染聚类与可视化。")
    add_image(doc, os.path.join(SHOT, "exp2_kmeans.png"),
              "图 4-4 KMeans 文本聚类与 Purity/ARI 评估（白底代码截图）")

    h(doc, "4.1.5 实验结果", 3)
    para(doc, f"模型信息：{model}。")
    add_table(doc, ["向量运算", "期望词", "实际 Top-3（含余弦相似度）"],
              [[f"{a}−{b}+{c}", f"≈{e}", top + (" ★" if hit else "")] for a, b, c, e, top, hit in anas],
              cap="表 4-1 词向量类比推理结果", widths=[1.6, 1.0, 3.4])
    add_table(doc, ["词对", "余弦相似度"], [[f"sim({w1}, {w2})", s] for w1, w2, s in wpairs],
              cap="表 4-2 12 组词对的余弦相似度", widths=[2.4, 2.4])
    add_table(doc, ["指标", "数值"], [
        ["类内平均相似度（同主题文档两两）", intra.group(1)],
        ["类间平均相似度（跨主题文档两两）", intra.group(2)],
        ["KMeans 聚类纯度 Purity", km.group(1)],
        ["调整兰德指数 ARI", km.group(2)],
        ["词表覆盖率（命中词数/总词数）", cover.group(1) if cover else "-"],
    ], cap="表 4-3 文档向量的主题可分性与聚类效果", widths=[3.4, 1.6])
    add_table(doc, ["真实主题", "三个聚类簇中的样本数"], [[n, c] for n, c in conf],
              cap="表 4-4 KMeans 混淆矩阵（行=真实主题，列=聚类簇）", widths=[1.6, 3.4])
    add_image(doc, os.path.join(FIG, "exp2_wordvec_pca_tsne.png"),
              "图 4-5 文档向量 PCA / t-SNE 降维可视化与 KMeans 聚类结果")

    h(doc, "4.1.6 结果分析", 3)
    for s in [
        "语义推理：6 组类比中 3 组完全命中（国王−男人+女人→王后 0.705、北京−中国+法国→巴黎 0.686、"
        "中国−北京+伦敦→英国 0.769）。其余 3 组虽未命中期望词，但 Top-3 全部落在同一语义场："
        "父亲−儿子+母亲 返回“父母亲/外婆/奶奶”（亲属称谓），医生−医院+学校 返回“学生/老师/班主任”（校园角色），"
        "太阳−白天+月亮 返回“木星/月亮和太阳/星星”（天体）。说明词向量的语义结构确实成立，"
        "类比推理未命中的常见原因是：这类词在训练语料中的搭配分布更集中在近义/上位词上"
        "（如“母亲”更容易联想到“父母亲、外婆、奶奶”），即向量的“最近邻”语义场正确、"
        "但线性偏移量不足以精确指向某一个特定词。",
        "词对相似度：结果符合直觉——近义/强相关词对得分高，如 sim(医生, 护士)=0.8134、"
        "sim(北京, 上海)=0.8051、sim(电影, 电视剧)=0.7500、sim(老师, 学生)=0.7438、sim(手机, 电脑)=0.7228；"
        "而语义跨度大的词对得分明显偏低，如 sim(中国, 北京)=0.5500、sim(苹果, 手机)=0.5659、"
        "sim(冠军, 奥运)=0.5867。值得注意的是 sim(苹果, 香蕉)=0.6102 与 sim(苹果, 手机)=0.5659 非常接近，"
        "说明词向量无法区分“水果苹果”与“品牌苹果”这种一词多义，是静态词向量的典型缺陷"
        "（ELMo/BERT 等上下文相关表示正是为解决该问题而提出）。",
        "文档向量质量：类内平均相似度 0.9081 明显高于类间 0.7993，说明 200 维平均池化向量已能区分主题；"
        "KMeans 聚类纯度达 0.94、ARI 0.8319，属于“无监督结果与人工标注高度一致”。"
        "需要正确解读混淆矩阵（行=真实主题，列=簇 0/1/2）：科技类 50 篇全部落在簇 0，"
        "娱乐类 50 篇全部落在簇 1，二者被完美分开；**体育类是唯一被拆开的类**——"
        "41 篇落在簇 2、7 篇落在簇 1、2 篇落在簇 0。"
        "也就是说并非“体育被整类错分”，而是体育内部本身不够紧凑：体育新闻常夹杂人物故事、"
        "赛事花絮，用词与娱乐题材重叠，这也解释了为何类间相似度（0.7993）整体偏高。",
        "词表覆盖率（表 4-3）：150 篇文档共 74339 个内容词，其中 66465 个能在 143613 词的轻量版词表中命中，"
        "整体覆盖率 89.41%（体育 82.63% / 科技 90.31% / 娱乐 90.84%）。"
        "体育类覆盖率最低，主要是运动员姓名、队名等专有名词不在轻量版词表内——"
        "平均池化会直接丢弃这些 OOV 词，而它们恰恰是体育新闻最有区分度的信息。"
        "若换成完整版（800 万词）词向量，这一指标与本实验的聚类效果都有提升空间。",
        "PCA 与 t-SNE 的对比（图 4-5）：PCA 平面上三类文档彼此重叠较多，反映的是全局方差结构；"
        "t-SNE 平面上三类形成较为分离的团簇，局部结构更清晰。"
        "这是二者的典型差异——PCA 保留全局距离、t-SNE 强调局部近邻，实际分析中常两者并用。",
    ]:
        para(doc, s)

    # ---------- 4.2 加权 SimHash ----------
    head, gold, res, res_mixed, sweep = parse_simhash()
    ndoc = head.group(1)
    n_near, n_same, n_mixed_gold = (gold.group(1), gold.group(2), gold.group(3)) if gold else ("12", "6", "21")
    h(doc, "4.2 基于加权 SimHash 的网页新闻相似度计算", 2)
    h(doc, "4.2.1 实验目的", 3)
    para(doc, "理解并实现基于 SimHash 的长文本相似度计算，在传统 SimHash 基础上引入 TF-IDF 权重，"
              "能够根据实际场景调整特征权重；通过查准率/查全率/F1 对比，验证加权策略的有效性。")

    h(doc, "4.2.2 算法原理（加权 SimHash）", 3)
    para(doc, "SimHash 是一种局部敏感哈希（LSH），把任意长度的文档压缩成固定长度的指纹（本实验 64 位），"
              "使得内容相近的文档指纹差异很小（海明距离小）。算法步骤如下：")
    for f in [
        "① 分词并去重，为每个特征词计算一个 64 位哈希值 h（本实验取 md5 前 16 个十六进制字符，保证确定性）；",
        "② 初始化 64 维权重累加向量 v = 0；对每个特征词，遍历其哈希的每一位：该位为 1 则 v[i] += w，为 0 则 v[i] −= w；",
        "③ 最后按符号生成指纹：v[i] > 0 则指纹第 i 位取 1，否则取 0。",
    ]:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Pt(28)
        p.paragraph_format.space_after = Pt(2)
        set_run(p.add_run(f), size=10.5)
    para(doc, "加权策略是本实验的核心改进。传统 SimHash 对每个词取等权（或仅按词频 w=TF），"
              "导致“的、了、是”这类高频停用词在累加中反复投票、稀释了真正有区分度词的贡献，"
              "生成大量“模糊指纹”，使不同主题的文档也可能因停用词主导而落入海明距离≤3 的范围（假阳性）。"
              "本实验引入两类权重调整：")
    for f in [
        "高 TF-IDF 值加权：w = TF-IDF(t, d)，使只在少数文档出现的专有名词（人名、机构名、技术术语）"
        "获得高权重，主导指纹生成——这些词恰恰是判断“是否同一事件”的关键；",
        "停用词降权：对命中停用词表的词，权重再乘 0.2（STOP_SCALE），进一步压制其投票能力。",
    ]:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Pt(28)
        p.paragraph_format.space_after = Pt(2)
        set_run(p.add_run("• " + f), size=10.5)
    para(doc, "相似度判定：两篇文档指纹逐位异或后统计 1 的个数即为海明距离 d(A,B) = popcount(A ⊕ B)，"
              "本实验设定 d ≤ 3 判定为近似重复（64 位指纹中最多允许 3 位不同）。")

    h(doc, "4.2.3 数据集设计", 3)
    para(doc, f"共 {ndoc} 篇网页新闻，按作业要求覆盖三类：① 同一事件的不同报道；② 转载改写；③ 完全不同主题。"
              f"数据集以真实新闻为源文，共 7 个分组。")
    add_table(doc, ["分组", "文档数", "类型", "组内平均 Jaccard", "说明"], [
        ["R1", "4", "转载改写（同一事件）", "0.991",
         "扎克伯格深度专访/中美 AI 竞争：源文 + 换标题转载 + 轻度改写 + 中度改写"],
        ["R2", "4", "转载改写（同一事件）", "0.974",
         "国米 vs 罗马赛后评论：源文 + 换标题转载 + 轻度改写 + 中度改写"],
        ["D1", "3", "同一事件不同报道", "0.153", "佟丽娅 / 陈思诚相关报道（三家媒体，行文迥异）"],
        ["D2", "3", "同一事件不同报道", "0.228", "萨拉赫单场 3 球 1 助攻（三家媒体）"],
        ["D3", "3", "标注待核", "0.173",
         "原标注为同事件，经复核 15 号（女子现代五项团体夺金）与 16/17 号（男子铁人三项摘银）"
         "分属不同事件，故不计入近似重复"],
        ["U1~U3", "3", "完全不同主题", "—", "百川智能融资 / CrowdStrike 故障 / 倪萍访谈，互不相关"],
    ], cap="表 4-5 20 篇新闻数据集的分组设计与实测组内相似度",
        widths=[0.75, 0.75, 1.4, 1.15, 2.65], size=8)
    para(doc, "**金标准分层（本实验关键的评估口径）**：组内平均 Jaccard 显示数据天然分成两档——"
              "改写簇 R1/R2 为 0.96~1.00（几乎同文，属真正的“近似重复”），"
              "而同事件不同报道 D1/D2 只有 0.11~0.26（事件相同但文本几乎不重叠）。"
              "把两者混在同一条 P/R/F1 里统计，会让召回率被系统性压低、掩盖方法差异。"
              "因此本实验把正样本定义为**改写簇组内对（12 对）**，"
              "并同时给出“初版混合口径（所有同组对，21 对）”的结果以便对照。")

    h(doc, "4.2.4 关键代码解读", 3)
    add_image(doc, os.path.join(SHOT, "exp2_simhash_fp.png"),
              "图 4-6 64 位加权 SimHash 指纹与海明距离（白底代码截图）")
    para(doc, "代码要点：v 用 float64 以容纳可变的权重；内层循环按位（bit）累加 ±w；"
              "指纹用 Python 大整数按位或拼装，海明距离用 bin(a^b).count('1') 计算，简洁且无溢出风险。")
    add_image(doc, os.path.join(SHOT, "exp2_simhash_main.png"),
              "图 4-7 三种权重方案的构造（TF-IDF 按词元 / 等权词频 / 唯一词消融）")
    para(doc, "代码要点：① 在 20 篇文档上训练 TfidfVectorizer，得到每篇文档每个词的 TF-IDF 权重矩阵 X；"
              "② 遍历文档词序列，从 X 中取出该词的权重作为 w；③ 若该词命中停用词表则 w *= 0.2 实现降权。"
              "注意此处分词函数刻意保留停用词（只过滤纯标点/数字），否则“停用词降权”这条分支永远不会被触发。"
              "另外，取权重时用 t.lower() 与特征名对齐——这与实验一(1) 修正的是同一类大小写陷阱。"
              "④ 额外构造“按唯一词取 TF-IDF 权重”的消融方案，用于检验“按词元累加”这一设计选择是否真的有效。")
    add_image(doc, os.path.join(SHOT, "exp2_simhash_gold.png"),
              "图 4-8 三层金标准与分组内相似度自检")
    para(doc, "代码要点：脚本在计算指标之前先打印每个分组的组内相似度与 D3 组的三条标题，"
              "把“金标准为什么这样分层”的证据固化在输出里，而不是只写在报告正文中——"
              "这样任何人重跑脚本都能看到分层依据，也便于发现标注错误。")

    h(doc, "4.2.5 实验结果", 3)
    w_p, w_r, w_f, w_tp, w_fp, w_fn = res["TF-IDF加权"]
    e_p, e_r, e_f, e_tp, e_fp, e_fn = res["等权(词频)"]
    u_p, u_r, u_f, u_tp, u_fp, u_fn = res["TF-IDF唯一词(消融)"]
    add_table(doc, ["方法", "查准率 P", "查全率 R", "F1", "TP", "FP", "FN"], [
        ["TF-IDF 加权 SimHash（按词元）", w_p, w_r, w_f, w_tp, w_fp, w_fn],
        ["TF-IDF 加权 SimHash（唯一词，消融）", u_p, u_r, u_f, u_tp, u_fp, u_fn],
        ["等权（词频）SimHash", e_p, e_r, e_f, e_tp, e_fp, e_fn],
    ], cap="表 4-6 三种 SimHash 权重方案的去重效果对比（修正口径，海明距离 ≤ 3；正样本 12 对）",
        widths=[2.4, 0.85, 0.85, 0.8, 0.6, 0.6, 0.6], size=8.5)
    para(doc, f"说明：数据集 {ndoc} 篇，修正口径正样本 {n_near} 对（改写簇 R1/R2 组内对）；"
              f"初版混合口径正样本 {n_mixed_gold} 对（所有同组对）。"
              f"TF-IDF 加权方案 P={w_p}、R={w_r}、F1={w_f}；等权方案 P={e_p}、R={e_r}、F1={e_f}。"
              f"按 F1 计算，加权方案是等权的 {float(w_f)/float(e_f):.1f} 倍，改进显著。"
              f"三种方案在初版口径下的对比见 out/_baseline_original/ 与 out/AUDIT_NOTES.md。")

    rows10 = [[f"{t}", f"{p1}/{r1}/{f1}", f"{p2}/{r2}/{f2}", f"{p3}/{r3}/{f3}"]
              for t, (p1, r1, f1), (p2, r2, f2), (p3, r3, f3) in sweep]
    add_table(doc, ["海明距离阈值", "TF-IDF 加权（P/R/F1）", "等权（P/R/F1）", "唯一词消融（P/R/F1）"], rows10,
              cap="表 4-7 海明距离阈值扫描（修正口径，正样本=改写簇 12 对）",
              widths=[1.1, 1.55, 1.45, 1.55], size=8.5)
    add_image(doc, os.path.join(FIG, "exp2_simhash_prf.png"),
              "图 4-9 三种方案的 P/R/F1 对比（实心=修正口径，虚线框=初版口径）与阈值对 F1 的影响")

    h(doc, "4.2.6 结果分析", 3)
    for s in [
        f"加权 SimHash 的查准率达到 {w_p}，即检出的 10 对全部命中；而等权 SimHash 查准率仅 {e_p}，"
        f"它检出的 78 对里有 {e_fp} 对是误报（且把 12 对正样本全部检出，R=1.000）。"
        "查看明细可见，等权方案把“扎克伯格访谈”（R1）与国米罗马评论（R2）、佟丽娅报道（D1）、"
        "甚至百川智能融资（U1）都判成了重复——根源正在于停用词与通用词在等权累加中主导了指纹，"
        "使不同主题的文档指纹趋于“均值化”，海明距离被人为压小。"
        "这组对比（F1 0.267 vs 0.909）说明：**只是把权重从词频换成 TF-IDF 并给停用词降权，"
        "就能把误报从 66 对压到 0 对**，这是本实验最有说服力的一处结论。",
        "“按词元累加”这一设计选择是被验证有效的，不是缺陷：加权方案按词的出现次数累加 TF-IDF 权重"
        "（同一词出现 3 次则加 3 次），隐含效果是权重随词频近似二次增长。"
        "为检验这一选择，本实验额外实现了“按唯一词只加一次”的消融方案："
        f"唯一词版 P={u_p}、R={u_r}、F1={u_f}（TP={u_tp}/FN={u_fn}），"
        f"召回率明显低于原方案的 {w_r}，查准率同为 1.000。"
        "原因是改写簇内的高频内容词（人名、机构、关键术语）被重复投票后贡献更大，"
        "使同源文档的指纹更稳定——这与经典 SimHash 用 TF 加权、重复词加强投票的直觉一致。"
        "因此保留原设计，并把这组消融数据作为依据。",
        "关于查全率 0.833（漏判 2 对）：修正口径下 12 对改写簇正样本中检出 10 对，漏判 2 对。"
        "漏判来自改写幅度最大的样本——同义替换后高权重关键词被换掉，指纹跳变超过 3 位。"
        "这说明“只靠词形匹配”的 SimHash 对深度改写天然不敏感；"
        "而初版报告中把召回率记为 0.476，其实是因为金标准里混入了 9 对"
        "“同事件不同报道 / 不同事件”的样本，那些样本文本相似度只有 0.11~0.26，"
        "本就不该被 SimHash 判为近似重复。**修正金标准后召回率从 0.476 变为 0.833**，"
        "这个变化全部来自评估口径而非算法改动。",
        "阈值的影响（表 4-7、图 4-9 右）：加权方案的 P 在阈值 0~5 全程保持 1.000，"
        "说明其误报几乎为零，放宽阈值只增加召回、不引入噪声；"
        "F1 随阈值单调上升，阈值 6 时达到 0.960（R=1.000）。等权方案的 F1 在阈值 0~10 几乎不动"
        "（0.267~0.308），因为其误报是“系统性”的而非“边界性”的——误报对的海明距离本就很小，"
        "提高阈值无法区分。这从另一角度印证了加权策略的有效性。",
        "工程启示：作业规定的 d ≤ 3 是一个偏保守的经典取值（64 位指纹、约 4.7% 的位差异）。"
        "本数据集上加权方案在 d ≤ 3 时已达 P=1.000/R=0.833，说明该阈值在本任务上是合适的；"
        "若把阈值放宽到 6，召回可补满到 1.000 且不损失查准率。"
        "但阈值必须结合业务权衡：查重场景怕误伤（重准确率，取小阈值），"
        "内容聚合/爬虫去重场景怕漏抓（重查全率，可放宽阈值）。"
        "更重要的是：**阈值要按目标相似度区间标定**，而目标区间取决于金标准怎么定义“重复”。",
    ]:
        para(doc, s)

    # ===== 五、学习笔记 =====
    h(doc, "五、实验学习笔记", 1)
    notes = [
        ("“重复”不是一个客观量，取决于你怎么定义", "本次实验最大的收获来自评估口径。"
         "同样一套 SimHash 指纹，金标准定义不同，指标可以从 F1=0.645 变成 F1=0.909；"
         "同样一批 MinHash 结果，“最优阈值”可以落在 0.1 也可以落在 0.4。"
         "原因是数据里天然存在三个层次：**逐字重复**（Jaccard≈1.0）、**同事件改写**（0.1~0.3）、"
         "**同主题不同事件**（≈0）。把这三层混进同一条 P/R/F1，得到的数字既不可复现也不可解释。"
         "正确做法是先把“什么算重复”写清楚，再定阈值——而不是先跑出数字再解释。"),
        ("标注错误比算法缺陷更致命", "news20 的 D3 组把“女子现代五项团体夺金”与“男子铁人三项摘银”"
         "标成了同一事件。这 2 对错误标注混在 21 对金标准里，直接把加权 SimHash 的召回率"
         "从 0.833 压到 0.476，让人误以为“SimHash 对改写不敏感”。"
         "而实际上算法本身没问题。这件事的教训是：**指标异常时，第一件事是查金标准，而不是改算法**。"
         "同时也说明评估脚本应该把分层依据（如组内相似度）打印出来，让标注问题自己暴露。"),
        ("大小写、空行、空格——数据清洗决定结论", "本次修正的缺陷大多不是算法问题："
         "① TF-IDF 回查权重时 `AI` 与特征名 `ai` 不匹配，一个词频 82 的高频词被误报成“权重 0”；"
         "② 读取新闻时 `split(\"\\n\", 3)[3]` 把 `group=` / `rewrite=` 当成正文；"
         "③ 语料里 3 条仅空格差异的标题，让余弦相似度恒为 1.0000 并霸占 Top-10。"
         "三处都属于“算法对、工程错”。它们共同说明：**特征矩阵算对了，不代表按名字取值就取对了**。"),
        ("精确 vs 近似的权衡思维", "MinHash 用 128 维签名替代原始集合，LSH 用分桶替代全量比较，"
         "两者都是“用可控的精度损失换数量级的效率提升”。"
         "500 篇文档时精确 Jaccard 约 134 ms、MinHash 全量约 635 ms、而 LSH 建桶只要 8~28 ms，"
         "且 MinHash 估计的平均绝对误差仅 0.0064。"
         "关键洞察是：**签名与索引是一次性成本**，建成后每次查询只与同桶文档比较；"
         "而精确方法每来一次查询都要重算一遍。规模越大，这个差距越决定性。"),
        ("参数必须按目标区间标定，不能照搬经验", "LSH 的分桶参数 (b, r) 直接决定能召回什么相似度的文档。"
         "本次实测发现 (b=16, r=8) 在真实新闻标题上几乎剪掉一切（200 篇时候选 0 对），"
         "因为它只对相似度 ≥0.9 的文档有效；而真实标题两两的 Jaccard 普遍低于 0.3。"
         "要用它做去重，必须换成 (b=64, r=2) 这类小 r 配置。"
         "这也提醒我：做规模实验时**不能自己造“太好”的数据**——"
         "早期版本用 6 条用例重复拼接来放大规模，文档几乎相同，候选对高达 27640 对，"
         "恰好把“参数需要标定”这个真问题掩盖了。"),
        ("算法原理正确 ≠ 实验结果可信", "本次复现确认了，即使代码“能跑出漂亮数字”，"
         "仍可能同时在四个层面出错：数据解析（元信息混入正文）、特征回查（大小写不匹配）、"
         "评估口径（金标准分层错误）、实验设计（造数据导致失真）。"
         "因此我在修正后的脚本里加了三条自检并固化到输出：金标准分层自检、"
         "分组内相似度打印、以及“是否进入特征集”标记。"
         "让证据先于结论出现，而不是只写在报告里。"),
        ("P/R/F1 的取舍要看业务", "加权 SimHash 是 P=1.000 / R=0.833，等权是 P=0.154 / R=1.000——"
         "前者“宁可漏判不误判”，后者“宁可误判不漏判”。单看某个指标都会得出片面结论。"
         "真实系统里，论文查重、版权比对怕误伤（重查准率），"
         "而爬虫去重、内容聚合怕漏抓（重查全率），F1 只是中性参考。"),
        ("词向量的可解释性与局限", "t-SNE 图上三类文档聚成清晰团簇、KMeans 纯度 0.94，"
         "很有说服力地展示了“词向量的平均能代表文档语义”。"
         "但同时 sim(苹果, 香蕉)=0.6102 > sim(苹果, 手机)=0.5659 暴露了静态词向量无法处理一词多义的硬伤；"
         "体育类词表覆盖率只有 82.63%（运动员姓名、队名多为 OOV 被丢弃）也说明"
         "轻量版词表对专有名词不友好。这两点让我理解了从 Word2Vec 到 BERT 的演进动机。"),
    ]
    for i, (t, c) in enumerate(notes, 1):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2)
        set_run(p.add_run(f"{i}. {t}"), size=11, bold=True)
        para(doc, c)

    # ===== 六、附录 =====
    h(doc, "六、附录", 1)
    h(doc, "6.1 文件清单", 3)
    add_table(doc, ["类型", "路径", "说明"], [
        ["实验一(1)", "exp1_tfidf.py", "TF-IDF 特征 + 余弦 Top-10 + 词频权重柱状图"],
        ["实验一(2)", "exp1_minhash.py", "MinHash(k=128) + LSH + 阈值/效率对比"],
        ["实验二(1)", "exp2_wordvec.py", "词向量加载/语义推理/平均池化/KMeans/PCA+t-SNE"],
        ["实验二(2)", "exp2_simhash.py", "加权 SimHash + 海明距离 + P/R/F1 对比"],
        ["语料", "data/titles.txt", "2579 条新闻标题（规范化去重后 2576 条参与计算）"],
        ["语料", "data/{sports,tech,ent}/", "三类主题各 50 篇全文"],
        ["语料", "data/news20/ + manifest.json", "20 篇相似度实验新闻（含分组标注）"],
        ["语料", "data/short_texts.txt", "6 条去重测试用例"],
        ["结果", "out/*_results.txt", "四个实验的控制台结果落盘"],
        ["结果", "out/AUDIT_NOTES.md", "复现审计与逐项修正说明（含修正前后对照）"],
        ["结果", "out/_baseline_original/", "复刻前的原始落盘结果（用于逐行对照）"],
        ["图片", "out/figures/*.png", "5 张可视化图"],
        ["图片", "out/screenshots/*.png", "13 张关键代码白底截图"],
        ["抓取脚本", "tools/scraper.py 等", "新闻抓取与数据集构造脚本"],
        ["报告脚本", "tools/build_report.py", "由结果文件 + 图片自动生成本报告"],
    ], cap="表 6-1 提交文件清单", widths=[1.1, 2.0, 2.9])

    h(doc, "6.2 复现步骤", 3)
    for i, s in enumerate([
        "安装依赖：pip install -r requirements.txt",
        "下载腾讯 AI Lab 中文词向量（Light 版），重命名为 light_Tencent_AILab_ChineseEmbedding.bin 并放入 model/ 目录；",
        "依次运行：python exp1_tfidf.py → python exp1_minhash.py → python exp2_wordvec.py → python exp2_simhash.py；",
        "结果文本输出到 out/*_results.txt，图像输出到 out/figures/；",
        "（可选）python tools/make_screenshots.py 生成白底代码截图；python tools/build_report.py 重建本报告；",
        "（可选）如需重新抓取语料，运行 tools/ 下的抓取脚本（需联网）。",
    ], 1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Pt(28)
        p.paragraph_format.space_after = Pt(2)
        set_run(p.add_run(f"（{i}）{s}"), size=10.5)

    h(doc, "6.3 本轮修正与复现审计", 3)
    para(doc, "本次提交前对整个项目做了一次完整的复现审计：把工程复刻到本机后重新运行全部四个实验，"
              "与原落盘结果逐行对照，并逐项核查数据解析、特征回查、评估口径与实验设计。"
              "共发现并修正 8 处问题（5 处正确性/金标准问题、3 处方法学/实验设计问题），"
              "同时确认 1 处初看可疑、经消融实验验证为**合理设计选择**而非缺陷。"
              "完整的「修正前 → 修正后」对照、证据与复现命令见 out/AUDIT_NOTES.md；"
              "原始结果备份于 out/_baseline_original/ 以便逐行核对。主要修正如下表。")
    add_table(doc, ["编号", "问题", "影响", "修正后"], [
        ["C1", "读取新闻时 split(\"\\n\",3)[3] 取正文", "group= / rewrite= 被当成正文词混入文档",
         "改按首个空行切分"],
        ["C2", "回查 TF-IDF 权重时大小写不匹配", "高频词“AI”被误报为权重 0.0000",
         "分词统一小写对齐特征名；结果增加“进入特征集”列"],
        ["C3", "语料未规范化", "3 条仅空格差异的标题使余弦相似度恒为 1.0 并霸占 Top-10",
         "按去空白+小写去重"],
        ["C4", "news20 的 D3 组标注错误", "把“女子现代五项夺金”与“男子铁人三项摘银”当成同一事件",
         "金标准分三层，D3 不计入近似重复正样本"],
        ["C5", "P/R 在分母为空时取 1.0", "出现“无预测却 F1=1.000”的错误结论",
         "改取 0 并同时输出 TP/FP/FN"],
        ["C6", "批量计时实验用重复用例造规模", "文档几乎相同、候选对虚高，时间对比失真",
         "改用真实标题语料扩展规模"],
        ["C7", "实验一(2) 把 T1~T4 全当重复", "阈值 0.1 处出现“假最优”，掩盖方法差异",
         "拆为近重复/同事件改写/不相关三层"],
        ["C8", "加权 SimHash 按词元累加权重（初看可疑）", "经消融实验验证召回 0.833 > 唯一词版 0.583",
         "判定为合理设计选择，保留并补充消融数据"],
    ], cap="表 6-2 本轮复现审计发现的 8 处问题与修正", widths=[0.5, 1.8, 2.0, 1.9], size=8)

    # 按作业要求的命名格式：姓名+学号+第1次实验报告.docx
    name = "<成员一姓名>+<成员一学号>+第1次实验报告.docx"
    path = os.path.join(OUT, name)
    doc.save(path)
    print("报告已生成:", path)
    return path


if __name__ == "__main__":
    build()
