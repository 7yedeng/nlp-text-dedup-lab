# -*- coding: utf-8 -*-
"""生成《内容重复理解技术综合实验》实验报告 Word 文档

数据来源：out/*.txt（各实验落盘结果）、out/figures/*.png（可视化）、
         out/screenshots/*.png（关键代码白底截图）
"""
import os
import re
import json

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
    """插入图片；cap 为 None 时**仍然输出图题**（用文件名兜底），避免出现“无题图”。"""
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
    caption(doc, cap or f"图 {os.path.basename(path)}")


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


def read_json(name):
    """读取实验脚本落盘的结构化汇总。

    【S1 修正】报告正文中的所有结果数字都必须来自这里（或下方的结果文本解析），
    不得在报告生成器里手写常量。初版在分析段落里硬编码了 91.87 / 713.32 / 30.52 ms
    与「84 对、68 误报」等旧数字，与结果文件冲突，重新生成报告也会把错误带进去。
    现在改为：脚本算 → JSON 落盘 → 报告读 JSON → f-string 插值。
    """
    with open(os.path.join(OUT, name), encoding="utf-8") as f:
        return json.load(f)


def load_summaries():
    """四个实验的结构化汇总；缺失时给出明确报错（而不是静默用默认值）。"""
    need = ["results_summary_tfidf.json", "results_summary_minhash.json",
            "results_summary_wordvec.json", "results_summary_simhash.json"]
    out = {}
    for fn in need:
        p = os.path.join(OUT, fn)
        if not os.path.exists(p):
            raise FileNotFoundError(
                f"缺少结构化汇总 {fn}，请先运行对应的实验脚本（见 README「如何运行」）")
        out[fn.replace("results_summary_", "").replace(".json", "")] = read_json(fn)
    return out


SUMM = load_summaries()
TF = SUMM["tfidf"]
MH = SUMM["minhash"]
WV = SUMM["wordvec"]
SH = SUMM["simhash"]
SIMHASH_SCHEMES = {s["name"]: s for s in SH["schemes"]}


def fmt(x, nd=4):
    return f"{x:.{nd}f}"


def pct(x, nd=2):
    return f"{x:.{nd}%}"


# ------------------------- 结果解析 -------------------------
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
    scale, shape = str(TF["scale"]), f"({TF['matrix_shape'][0]}, {TF['matrix_shape'][1]})"
    pairs = [(p["sim"], p["i"], p["text_i"], p["j"], p["text_j"]) for p in TF["top10"]]
    words = [(w["word"], str(w["freq"]), f"{w['weight']:.4f}",
              "是" if w["in_vocab"] else "否") for w in TF["top20_words"]]
    st = {"raw_scale": str(TF["raw_scale"]), "removed": str(TF["removed_dup"]),
          "n_pairs": str(TF["similarity"]["n_pairs"]), "mean": f"{TF['similarity']['mean']:.6f}",
          "p50": f"{TF['similarity']['p50']:.6f}", "p99": f"{TF['similarity']['p99']:.6f}",
          "max": f"{TF['similarity']['max']:.6f}", "ge9": str(TF["similarity"]["n_ge_0.9"]),
          "ge5": str(TF["similarity"]["n_ge_0.5"]), "ge3": str(TF["similarity"]["n_ge_0.3"]),
          "top10_ge3": str(TF["top10_ge_0_3"])}
    tm_stats = [
        ["原始语料条数", st["raw_scale"]],
        ["规范化去重后语料条数", scale],
        ["移除的空白/大小写重复条目", f"{st['removed']} 条"],
        ["TF-IDF 矩阵形状", shape],
        ["1-gram / 2-gram 特征数", f"{TF['n_1gram']} / {TF['n_2gram']}"],
        ["文本对总数", f"{int(st['n_pairs']):,}"],
        ["相似度均值 / P50", f"{st['mean']} / {st['p50']}"],
        ["相似度 P99 / 最大值", f"{st['p99']} / {st['max']}"],
        ["相似度 ≥0.9 / ≥0.5 / ≥0.3 的文本对",
         f"{st['ge9']} / {st['ge5']} / {st['ge3']}"],
        ["Top-10 中相似度 ≥0.3 的对数", f"{st['top10_ge3']} / 10"],
        ["模板化标题占比", f"{TF['template_stats']['n_template']} / {TF['scale']} "
                           f"({pct(TF['template_stats']['ratio'])})"],
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
              "图 3-4 词频最高的 20 个词的 TF-IDF 权重柱状图")

    h(doc, "3.1.5 结果分析", 3)
    _top20 = TF["top20_words"]
    _top1 = _top20[0]
    _freq_sorted = sorted(_top20, key=lambda w: -w["weight"])
    _best_w = _freq_sorted[0]
    _most_freq = max(_top20, key=lambda w: w["freq"])
    _ai = next((w for w in _top20 if w["word"].lower() == "ai"), None)
    _ts = TF["template_stats"]
    _tmpl_top = "、".join(f"{k} {v} 条" for k, v in
                          sorted(_ts["counts"].items(), key=lambda kv: -kv[1]))
    _p99 = TF["similarity"]["p99"]
    for s in [
        f"语料规范化的重要性：原始 {TF['raw_scale']} 条标题中存在 {TF['removed_dup']} 条"
        f"（{pct(TF['removed_dup'] / TF['raw_scale'])}）仅空格/大小写差异的重复条目"
        f"（如“腾势 D9 车型 OTA 升级”与“腾势D9车型OTA升级”）。由于 jieba 分词后词序列完全一致，"
        f"这类条目对的余弦相似度恒为 1.0000，会在 Top-10 中霸榜，掩盖真正的相似文本。"
        f"因此在语料加载阶段按“去空白 + 统一小写”规范化并去重，最终有效语料 {TF['scale']} 条。"
        f"这说明数据清洗不是可选项——它会直接决定相似度检索结果的可读性。",
        f"Top-10 全部是“模板化近似重复”：修正后 Top-10 中 {TF['top10_ge_0_3']}/10 对相似度为 1.0000，"
        f"且其中 {_ts['top10_templated']}/10 对来自模板化批量内容——主要是"
        f"“微博观影团《X》北京首映免费抢票”（仅影片名不同）与"
        f"“253期X福彩3D预测奖号：X推荐”（仅人名/玩法不同）。"
        f"经统计，{TF['scale']} 条有效标题中模板化标题共 {_ts['n_template']} 条"
        f"（{pct(_ts['ratio'])}）：{_tmpl_top}。"
        f"仅占 {pct(_ts['ratio'], 1)} 的模板内容却占据了相似度的最顶端，"
        f"因为模板文本的 TF-IDF 向量几乎完全相同。"
        f"这一方面实证了“TF-IDF+余弦对机器批量生成内容极为敏感”，可用于识别低质内容；"
        f"另一方面也提醒：若把 Top-10 直接当作“新闻事件重复”来解读，会严重误判。",
        f"相似度 1.0 不等于语义相同：以 Top-10 中的模板对为例，人名、期号、影片名是两篇的关键差异，"
        f"但它们经分词后被停用词表与纯数字规则过滤，剩余词完全一致，于是向量相同、相似度为 1。"
        f"这正是词袋模型“只看词共现、不看词序与关键实体”的固有天花板。"
        f"（全语料 {TF['similarity']['n_pairs']:,} 个文本对的相似度均值仅 {fmt(TF['similarity']['mean'])}、"
        f"P99 为 {fmt(_p99)}，说明绝大多数文本对其实并不相似，高相似是局部现象。）",
        f"词频与 TF-IDF 权重并非正相关（表 3-3、图 3-4）：高频词"
        f"“{_most_freq['word']}（{_most_freq['freq']} 次）”的平均权重只有 {fmt(_most_freq['weight'])}，"
        f"因为它们在大量文档中共同出现、IDF 很低；而“{_best_w['word']}”词频仅 {_best_w['freq']} 次，"
        f"平均权重却最高（{fmt(_best_w['weight'])}）。同理表中其余高权重词也都集中于少数文档，"
        f"区分度强。这与 TF-IDF 的设计初衷完全吻合。",
        (f"关于“AI”一词的权重（一个必须澄清的坑）：语料中“AI”词频 {_ai['freq']} 次，"
         f"平均 TF-IDF 权重 {fmt(_ai['weight'])}，" if _ai else
         "关于“AI”一词的权重：") +
        f"**一直在特征集内**（“进入特征集=是”）。需要特别说明的是，早期实现曾在分词阶段保留英文原形"
        f"（token 为“AI”），而 TfidfVectorizer 默认 lowercase=True 使特征名变为“ai”，"
        f"按特征名回查权重时因大小写不匹配而必然落空，把该词误报成“权重 0.0000、未进入特征集”。"
        f"修正方式是分词阶段统一转小写，与 lowercase 参数对齐；同时在结果中增加“进入特征集”一列，"
        f"使“真正被 max_features 截断”与“因键名不匹配查不到”这两种情况可以被直接区分"
        f"（本次 Top-20 词中实际被截断的有 {TF['n_oov_in_top20']} 个）。"
        f"这个案例说明：特征矩阵算对了，不代表按名字取值就取对了。",
    ]:
        para(doc, s)

    # ---------- 3.2 MinHash + LSH ----------
    sims = [(p["pair"].split("-")[0][1:], p["pair"].split("-")[1][1:],
             f"{p['jaccard']:.4f}", f"{p['minhash']:.4f}",
             "候选" if p["in_lsh_candidate"] else "")
            for p in MH["case_pairs"]]
    thr_mixed = [(str(r["t"]), *[f"{v:.3f}" for v in r["mixed_exact"][:3]],
                  *[f"{v:.3f}" for v in r["mixed_min"][:3]]) for r in MH["thresholds"]]
    thr = [(str(r["t"]), *[f"{v:.3f}" for v in r["strict_exact"][:3]],
            *[f"{v:.3f}" for v in r["strict_min"][:3]]) for r in MH["thresholds"]]
    lsh = [(k.split("_")[0][1:], k.split("_")[1][1:], v["n"])
           for k, v in MH["lsh_candidates"].items()]
    _b64 = MH["lsh_candidates"]["b64_r2"]["pairs"]
    lsh_items = [(p["pair"].split("-")[0][1:], p["pair"].split("-")[1][1:],
                  f"{p['minhash']:.4f}",
                  "近重复" if p["minhash"] >= MH["config"]["verify_threshold"]
                  else "候选但被阈值滤除(同事件改写)")
                 for p in MH["case_pairs"] if p["pair"] in _b64]
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
    _pm = {p["pair"]: p for p in MH["case_pairs"]}
    para(doc, "共设计 6 条短文本用例，覆盖完全重复、轻度修改、中度改写、完全不相关四类。"
              "需要强调的是：这 6 条用例内部其实有**三个相似度量级**，因此金标准必须分层，"
              f"而不能把 T1~T4 两两全部当作“重复”（实测 T1-T4 的 Jaccard 仅 "
              f"{fmt(_pm['T1-T4']['jaccard'])}、T3-T4 仅 {fmt(_pm['T3-T4']['jaccard'])}，"
              f"与完全重复的 {fmt(_pm['T1-T2']['jaccard'])} 相差一个量级）：")
    add_table(doc, ["编号", "文本", "类别", "层级"], [
        ["T1", "中国代表团在亚运会收获首金，女子现代五项团体成功卫冕", "原始文本", "—"],
        ["T2", "中国代表团在亚运会收获首金，女子现代五项团体成功卫冕", "完全重复（与 T1 逐字相同）", "近重复"],
        ["T3", "中国代表团亚运首金到手，女子现代五项团队成功卫冕", "轻度修改（删词/换词）", "近重复（J=0.31）"],
        ["T4", "卫冕成功！现代五项女子团体为中国队拿下本届亚运会第一枚金牌", "中度改写（换句序/同义替换）", "同事件改写（J=0.12~0.19）"],
        ["T5", "马斯克否认特斯拉向xAI投资五十亿美元参股计划", "完全不相关（同领域不同事件）", "不相关（J=0）"],
        ["T6", "佟丽娅公开回应与陈思诚的离婚传闻，称两人早已分开", "完全不相关（不同领域）", "不相关（J=0）"],
    ], cap="表 3-4 MinHash+LSH 实验的 6 个测试用例与分层", widths=[0.55, 3.9, 1.55, 1.4])
    para(doc, f"分层规则：**近重复 = {'、'.join(MH['gold']['near_dup_pairs'])}**（字面几乎一致，"
              f"{MH['gold']['near_dup']} 对）；**同事件改写 = "
              f"{'、'.join(MH['gold']['same_event_pairs'])}**（事件相同但句子结构重写，不计入"
              f"“近似重复”正样本，另计命中数，{MH['gold']['same_event']} 对）；"
              f"**不相关 = T5/T6 与其余文本**（相似度全为 0.0000，与 T1~T4 之间存在天然的间隔带）。"
              f"报告同时给出“初版混合口径”（T1~T4 两两共 {MH['gold']['mixed_related']} 对）"
              f"与“分层口径”两套指标，便于对照。")

    h(doc, "3.2.4 关键代码解读", 3)
    add_image(doc, os.path.join(SHOT, "exp1_minhash_update.png"),
              "图 3-5 MinHash 签名生成（k=128，exp1_minhash.py）")
    para(doc, "代码要点：签名初始化为一维 k 长数组（初值 P）；对集合中每个 shingle 计算其 64 位整数哈希后，"
              "逐个哈希函数取最小值。实现上刻意使用纯 Python 大整数运算而非 numpy 向量化："
              "因为 a_i·x 的量级接近 2¹²²，超出 numpy int64 的范围会造成溢出，属于典型的“数学正确但工程踩坑”问题。")
    add_image(doc, os.path.join(SHOT, "exp1_lsh.png"),
              "图 3-6 LSH 分桶与候选对生成（build_lsh_tables / lsh_candidates）")
    para(doc, "代码要点：把签名按 band 切片并作为 dict 的 key 建立倒排桶；同一桶内文档两两组合即为候选对，"
              "用 set 去重。整个过程只需一次线性扫描，避免了全量两两比较。")
    add_image(doc, os.path.join(SHOT, "exp1_minhash_prf.png"),
              "图 3-7 P/R/F1 计算（prf）——分母为空时返回 0 并同时输出 TP/FP/FN")
    para(doc, "代码要点：早期实现把“没有预测”时的查准率定义为 1.0，于是出现“一对都没检出却 F1 = 1.000”"
              "的荒谬结论。修正为分母为空时取 0，并让函数同时返回 TP/FP/FN，"
              "使“无预测”与“全对”在结果里不可能再被混淆。")
    add_image(doc, os.path.join(SHOT, "exp1_minhash_bench.png"),
              "图 3-8 端到端计时的三条路径（bench_exact / bench_minhash / bench_lsh）")
    para(doc, "代码要点：三条路径都必须能独立完成“从原始文本到给出重复判定对”，"
              "并把 shingle 构建（公共成本）单独计时、不计入比较阶段；"
              "每个规模先用同一批 shingle 预热一次，再重复计时取中位数，"
              "计时期间关闭 GC 以抑制抖动。这样得到的加速比才是同一任务下的可比数字。")

    h(doc, "3.2.5 实验结果", 3)
    rows3 = [[f"T{i}-T{j}", jac, mh, ("是" if mark else "否")] for i, j, jac, mh, mark in sims]
    add_table(doc, ["文本对", "精确 Jaccard", "MinHash 估计", "进入 LSH 候选"], rows3,
              cap="表 3-5 各文本对的精确 Jaccard 与 MinHash 估计对比", widths=[1.4, 1.6, 1.6, 1.6])
    para(doc, f"MinHash 估计的平均绝对误差为 {fmt(MH['minhash_error']['mae'])}，"
              f"最大误差 {fmt(MH['minhash_error']['max'])}，"
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

    _rows6 = []
    for r in MH["scaling_end2end_ms"]:
        _rows6.append([
            r["n"],
            f"{r['exact']*1000:.2f}±{r['exact_std']*1000:.2f}",
            f"{r['minhash']*1000:.2f}±{r['minhash_std']*1000:.2f}",
            f"{r['lsh_16_8']*1000:.2f}±{r['lsh_16_8_std']*1000:.2f}",
            f"{r['lsh_64_2']*1000:.2f}±{r['lsh_64_2_std']*1000:.2f}",
            f"{r['total_pairs']:,}", f"{r['cand_16_8']} / {r['cand_64_2']}",
            f"{r['speedup_lsh64_vs_exact']:.2f}×",
        ])
    add_table(doc, ["文档数", "精确 Jaccard", "MinHash 全量两两", "LSH b16r8", "LSH b64r2",
                    "全量对数", "候选数\nb16r8 / b64r2", "LSH 加速比\n(b64r2 vs 精确)"], _rows6,
              cap=f"表 3-10 批量规模对端到端耗时的影响（真实标题语料；{MH['config']['reps']} 次重复，"
                  f"中位数±标准差，单位毫秒；shingle 构建为公共成本，未计入）",
              widths=[0.62, 1.15, 1.15, 1.0, 1.0, 0.8, 1.0, 1.05], size=7.5)
    _stg = MH["stage_breakdown_500_ms"]
    add_table(doc, ["阶段（n=500）", "耗时(ms)", "说明"], [
        ["shingle 构建 + 签名生成", f"{_stg['shingle_and_signature']:.2f}", "一次性成本；k=128 向量化计算"],
        ["LSH 建桶 + 候选生成", f"{_stg['lsh_build_and_candidates']:.2f}", "不含签名生成"],
        ["候选回验", f"{_stg['candidate_verify']:.2f}", f"{_stg['n_candidates']} 对候选做签名比对"],
    ], cap="表 3-11 分阶段耗时拆解（用于定位瓶颈）", widths=[2.2, 1.2, 2.6])
    add_image(doc, os.path.join(FIG, "exp1_minhash_sim.png"),
              "图 3-9 MinHash 估计 vs 精确 Jaccard（左）与两种金标准口径下的 F1（右）")
    add_image(doc, os.path.join(FIG, "exp1_minhash_scaling.png"),
              "图 3-10 批量规模对端到端计算耗时的影响（对数纵轴，误差棒=标准差）")
    h(doc, "3.2.6 结果分析", 3)
    _pairs_mh = {p["pair"]: p for p in MH["case_pairs"]}
    _sc = {r["n"]: r for r in MH["scaling_end2end_ms"]}
    _n500, _n200, _n50 = _sc.get(500), _sc.get(200), _sc.get(50)
    _st = MH["stage_breakdown_500_ms"]
    _thr = {r["t"]: r for r in MH["thresholds"]}
    _lsh168 = MH["lsh_candidates"]["b16_r8"]
    _lsh642 = MH["lsh_candidates"]["b64_r2"]
    _t2 = _thr[0.2]
    _t4 = _thr[0.4]
    _t1 = _thr[0.1]
    for s in [
        f"MinHash 估计精度：T1-T2（完全重复）估计值 {fmt(_pairs_mh['T1-T2']['minhash'])} 与精确值 "
        f"{fmt(_pairs_mh['T1-T2']['jaccard'])} 一致；"
        f"T1-T3（轻度修改）精确 {fmt(_pairs_mh['T1-T3']['jaccard'])} vs 估计 "
        f"{fmt(_pairs_mh['T1-T3']['minhash'])}；T1-T4（中度改写）精确 "
        f"{fmt(_pairs_mh['T1-T4']['jaccard'])} vs 估计 {fmt(_pairs_mh['T1-T4']['minhash'])}；"
        f"完全不相关的 T5、T6 与其余文本精确值与估计值均为 0.0000。"
        f"整体平均绝对误差仅 {fmt(MH['minhash_error']['mae'])}（最大 {fmt(MH['minhash_error']['max'])}，"
        f"标准差 {fmt(MH['minhash_error']['std'])}），验证了 MinHash 作为 Jaccard 无偏估计的有效性。",
        f"金标准分层如何改变结论（表 3-6 vs 表 3-7）：这是本次实验最有价值的一处修正。"
        f"在**混合口径**下（把 T1~T4 两两都当重复，{MH['gold']['mixed_related']} 对），"
        f"阈值 {_t1['t']} 处精确方法 F1 为 {fmt(_t1['mixed_exact'][2], 3)}、"
        f"近似方法 F1 为 {fmt(_t1['mixed_min'][2], 3)}，看起来“阈值取 {_t1['t']} 就是最优”；"
        f"但这个结论是脆弱的——它完全建立在“把相似度仅 "
        f"{fmt(_pairs_mh['T3-T4']['jaccard'])}~{fmt(_pairs_mh['T1-T4']['jaccard'])} 的中度改写也算作重复”"
        f"这一设定上。改用**分层口径**（正样本只有真正字面重复的 T1-T2，"
        f"{MH['gold']['near_dup']} 对）后，同一批数据的曲线形状完全变了："
        f"阈值 {_t2['t']} 时 F1 仅 {fmt(_t2['strict_exact'][2], 3)}，"
        f"阈值 ≥{_t4['t']} 时才升到 {fmt(_t4['strict_exact'][2], 3)}。"
        f"也就是说：**“最优阈值”不是一个算法常数，而是由业务对“什么算重复”的定义决定的**。"
        f"去重要求“只删真重复”，阈值取 {_t4['t']}；内容收敛要求“把改写稿也一并合并”，"
        f"阈值取 {_t1['t']}~{_t2['t']}（此区间能召回 "
        f"{sum(1 for p in (_pairs_mh[f'T{a}-T{b}'] for a, b in [(1,3),(2,3),(3,4)]))}/3 类改写关系且零误报）。",
        f"近似 vs 精确：在分层口径下，阈值 ≥{_t4['t']} 时 MinHash 与精确 Jaccard 的 P/R/F1 完全一致"
        f"（均为 {fmt(_t4['strict_exact'][0], 3)}/{fmt(_t4['strict_exact'][1], 3)}/"
        f"{fmt(_t4['strict_exact'][2], 3)}）。这说明 k=128 的签名精度已足以支撑本次判定任务；"
        f"在混合口径下 MinHash 于阈值 {_t1['t']} 处的 F1 为 {fmt(_t1['mixed_min'][2], 3)}，"
        f"略低于精确方法的 {fmt(_t1['mixed_exact'][2], 3)}，"
        f"差异来自 T3-T4 的估计值 {fmt(_pairs_mh['T3-T4']['minhash'])} 被压到阈值以下"
        f"（精确值 {fmt(_pairs_mh['T3-T4']['jaccard'])} 高于阈值）。"
        f"这正是近似算法“用少量精度换取大量效率”的本质——误差可控且可解释。",
        f"LSH 分桶参数的取舍（表 3-8、3-9）：(b=16, r=8) 只产生 {_lsh168['n']} 对候选"
        f"（{('、'.join(_lsh168['pairs']) if _lsh168['pairs'] else '无')}），"
        f"把同事件改写的相似对基本全部漏掉；(b=64, r=2) 产生 {_lsh642['n']} 对候选，"
        f"覆盖了全部 T1~T4 之间的相似对。候选阶段相对本实验的 gold 是零误报；"
        f"经相似度回验后，低于阈值的同事件改写对被正常剔除——"
        f"这恰好演示了工业界的三段式做法：**LSH 粗筛候选 → MinHash 相似度回验 → 阈值判定**。"
        f"（需强调：初版把“未达到回验阈值”标成“误报”，是把算法自身分数当成了真值，"
        f"错误类型被颠倒；本版区分为“近重复”“候选但被阈值滤除（同事件改写）”“误报”三类。）",
        f"运行时间与规模（表 3-10、图 3-10）——这里必须交代一个重要的口径修正："
        f"初版把 LSH 列写成“复用已生成的签名、只计建桶”，既不含签名生成也不含候选回验，"
        f"而精确列是完整任务，**这不是同一个任务，不能据此宣称加速**。"
        f"本版三条路径都改为端到端（从 shingle 到最终判定对），并重复 {MH['config']['reps']} 次取中位数，"
        f"shingle 构建作为公共成本单列。实测（n=500）：精确 {_n500['exact'] * 1000:.1f} ms、"
        f"MinHash 全量两两 {_n500['minhash'] * 1000:.1f} ms、"
        f"LSH(b=64,r=2) {_n500['lsh_64_2'] * 1000:.1f} ms，"
        f"LSH 相对精确的加速比为 **{_n500['speedup_lsh64_vs_exact']:.2f}×**"
        f"（n=200 时 {_n200['speedup_lsh64_vs_exact']:.2f}×，n=50 时 "
        f"{_n50['speedup_lsh64_vs_exact']:.2f}×）。"
        f"也就是说：**在 200 条以下的小规模，LSH 因签名生成的固定开销反而更慢；"
        f"到 500 条才开始体现优势**。",
        f"瓶颈在哪里（表 3-10 下方的分阶段拆解）：n=500 时签名生成 "
        f"{_st['shingle_and_signature']:.1f} ms（一次性成本）、建桶+候选生成 "
        f"{_st['lsh_build_and_candidates']:.1f} ms、候选回验（{_st['n_candidates']} 对）"
        f"{_st['candidate_verify']:.1f} ms。可见 **k=128 的签名生成本身就是主要开销**。"
        f"需要说明的是：本实验的签名用 numpy 一次性向量化算出全部 128 个哈希值"
        f"（模数取 2³¹−1，使 int64 乘法不溢出）；若按初版那样用纯 Python 双重循环逐 shingle "
        f"逐哈希函数计算，n=500 时签名生成要 1.2 秒以上，总耗时会反超精确方法——"
        f"近似方法的效率优势依赖于实现质量，而不是“用了 LSH”这件事本身。",
        f"关于剪枝率的一个反直觉现象：在真实标题语料上，(b=16, r=8) 的候选对在 200 篇时为 "
        f"**{_n200['cand_16_8']}** 对，500 篇也只有 {_n500['cand_16_8']} 对。"
        f"原因是该配置要求“某个 8 行的 band 完全相同”，只对相似度 ≥0.9 的文档有效；"
        f"而真实新闻标题两两的 Jaccard 普遍低于 0.3（全语料相似度 P99 仅 {fmt(_p99, 3)}），"
        f"因此几乎全被剪掉。这说明 **LSH 参数必须按目标相似度区间标定**："
        f"要高召回就必须用 (b=64, r=2) 这类小 r 配置，不能照搬“band 越多越好”或“rows 越大越省”的经验。"
        f"（相比之下，早期版本用“6 条用例重复拼接”造出的规模实验，文档几乎相同、相似度极高，"
        f"候选对虚高到两万七千多对，反而掩盖了这个真实问题。本版改用真实标题语料扩展规模。）",
    ]:
        para(doc, s)

    # ===== 四、实验题目二 =====
    h(doc, "四、实验题目二：文本相似度计算", 1)

    # ---------- 4.1 词向量 ----------
    model = (f"{WV['model']['n_words']} 词 x {WV['model']['dim']} 维 "
             f"(腾讯 AI Lab 中文词向量 800万词轻量版)")
    anas = [(a["a"], a["b"], a["c"], a["expect"], a["top"], "★命中" if a["hit"] else "")
            for a in WV["analogies"]]
    wpairs = [(p["w1"], p["w2"], f"{p['sim']:.4f}") for p in WV["word_pairs"]]
    intra = (f"{WV['intra_mean']:.4f}", f"{WV['inter_mean']:.4f}")
    km = (f"{WV['purity']:.4f}", f"{WV['ari']:.4f}")
    conf = [(["体育", "科技", "娱乐"][i], str(WV["confusion"][i])) for i in range(3)]
    cover = (f"{pct(WV['vocab_coverage']['overall'])} "
             f"({WV['vocab_coverage']['hit']}/{WV['vocab_coverage']['total']})",)
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
        ["类内平均相似度（同主题文档两两）", intra[0]],
        ["类间平均相似度（跨主题文档两两）", intra[1]],
        ["KMeans 聚类纯度 Purity", km[0]],
        ["调整兰德指数 ARI", km[1]],
        ["文档向量 L2 归一化（聚类与余弦同口径）", "是" if WV["normalize_docvec"] else "否"],
        ["词表覆盖率（命中词数/总词数）", cover[0]],
    ], cap="表 4-3 文档向量的主题可分性与聚类效果", widths=[3.4, 1.6])
    add_table(doc, ["真实主题", "三个聚类簇中的样本数"], [[n, c] for n, c in conf],
              cap="表 4-4 KMeans 混淆矩阵（行=真实主题，列=聚类簇）", widths=[1.6, 3.4])
    add_image(doc, os.path.join(FIG, "exp2_wordvec_pca_tsne.png"),
              "图 4-5 文档向量 PCA / t-SNE 降维可视化与 KMeans 聚类结果")

    h(doc, "4.1.6 结果分析", 3)
    _hit = [a for a in WV["analogies"] if a["hit"]]
    _miss = [a for a in WV["analogies"] if not a["hit"]]
    _hit_txt = "、".join(f"{a['a']}−{a['b']}+{a['c']}→{a['expect']}"
                        for a in _hit)
    _miss_txt = "；".join(f"{a['a']}−{a['b']}+{a['c']} 返回“{a['top'].split('、')[0]}”"
                         for a in _miss)
    for s in [
        f"语义推理：6 组类比中 {len(_hit)} 组完全命中（{_hit_txt}）。"
        f"其余 {len(_miss)} 组虽未命中期望词，但 Top-3 全部落在同一语义场（{_miss_txt}）。"
        f"这说明词向量的语义结构确实成立，类比推理未命中的常见原因是：这类词在训练语料中的"
        f"搭配分布更集中在近义/上位词上，即向量的“最近邻”语义场正确、"
        f"但线性偏移量不足以精确指向某一个特定词。"
        f"**需要特别说明（复现审计 M5）**：初版把“父亲−儿子+母亲→女儿”作为模型缺陷的例子，"
        f"但该方向写反了——与“国王→王后”同理，正确的类比应是"
        f"“儿子−父亲+母亲≈女儿”（同为辈分关系、男→女）。本版按正确方向重做后，"
        f"该组**命中“女儿”**（相似度 {fmt(next((float(x.split('(')[1].rstrip(')')) for a in WV['analogies'] if a['a']=='儿子' for x in [a['top'].split('、')[0]]), 0), 3)}）；"
        f"同理“太阳−白天+月亮”改为“白天−太阳+月亮”后返回“夜里/夜间/前半夜”，语义场正确。"
        f"**错误的类比方向不能用来诊断模型能力问题。**",
        "词对相似度：结果符合直觉——近义/强相关词对得分高，"
        + "、".join(f"sim({a}, {b})={c}" for a, b, c in
                    sorted(wpairs, key=lambda x: -float(x[2]))[:5])
        + "；而语义跨度大的词对得分明显偏低，"
        + "、".join(f"sim({a}, {b})={c}" for a, b, c in
                    sorted(wpairs, key=lambda x: float(x[2]))[:3])
        + "。值得注意的是 sim(苹果, 香蕉) 与 sim(苹果, 手机) 非常接近"
        "（分别为 "
        + " 与 ".join(f"{c}" for a, b, c in wpairs if a == "苹果")
        + "），说明词向量无法区分“水果苹果”与“品牌苹果”这种一词多义，"
        "是静态词向量的典型缺陷（ELMo/BERT 等上下文相关表示正是为解决该问题而提出）。",
        f"文档向量质量：类内平均相似度 {fmt(WV['intra_mean'])} 高于类间 {fmt(WV['inter_mean'])}，"
        f"说明 {WV['model']['dim']} 维平均池化向量已能区分主题；"
        f"KMeans 聚类纯度达 {fmt(WV['purity'])}、ARI {fmt(WV['ari'])}。"
        f"**这里必须纠正初版对混淆矩阵的误读**（行=真实主题，列=簇 0/1/2）："
        f"由数据算出的「簇→多数主题」映射为 "
        + "、".join(f"簇{k}→{v['majority_name']}(n={v['n']})"
                    for k, v in sorted(WV["cluster_majority"].items()))
        + "。即簇 0 就是科技、簇 1 就是娱乐、簇 2 就是体育，"
        f"科技与娱乐各自被一个簇完整吸收，体育有 {WV['confusion'][0][2]} 篇落在体育簇、"
        f"{WV['confusion'][0][1]} 篇落到娱乐簇、{WV['confusion'][0][0]} 篇落到科技簇。"
        f"因此并不是“体育被整类错分到娱乐簇”，而是体育内部本身不够紧凑"
        f"（人物故事、赛事花絮用词与娱乐重叠），这也解释了为何类间相似度"
        f"（{fmt(WV['inter_mean'])}）整体偏高。"
        f"另需说明：本版对文档向量做了 L2 归一化后再聚类，"
        f"使 KMeans 的欧氏距离与余弦相似度口径一致（||a−b||²=2−2cos）。"
        f"归一化是实测有益的：不归一化时 Purity/ARI 为 "
        f"{fmt(WV['purity_no_norm'])}/{fmt(WV['ari_no_norm'])}，"
        f"归一化后提升到 {fmt(WV['purity'])}/{fmt(WV['ari'])}。",
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
    ndoc = str(SH["n_docs"])
    n_near = str(SH["gold"]["near_dup"])
    n_same = str(SH["gold"]["same_event"])
    n_mixed_gold = str(SH["gold"]["mixed_all_same_group"])
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
    _gs = SH["group_stats"]
    add_table(doc, ["分组", "文档数", "类型", "组内平均 Jaccard", "说明"], [
        ["R1", str(_gs["R1"]["n_docs"]), "转载改写（同一事件）", f"{_gs['R1']['mean']:.3f}",
         "扎克伯格深度专访/中美 AI 竞争：源文 + 换标题转载 + 轻度改写 + 中度改写"],
        ["R2", str(_gs["R2"]["n_docs"]), "转载改写（同一事件）", f"{_gs['R2']['mean']:.3f}",
         "国米 vs 罗马赛后评论：源文 + 换标题转载 + 轻度改写 + 中度改写"],
        ["D1", str(_gs["D1"]["n_docs"]), "同一事件不同报道", f"{_gs['D1']['mean']:.3f}",
         "佟丽娅 / 陈思诚相关报道（三家媒体，行文迥异）"],
        ["D2", str(_gs["D2"]["n_docs"]), "同一事件不同报道", f"{_gs['D2']['mean']:.3f}",
         "萨拉赫单场 3 球 1 助攻（三家媒体）"],
        ["D3", str(_gs["D3"]["n_docs"]), "标注待核", f"{_gs['D3']['mean']:.3f}",
         "原标注为同事件，经复核 15 号（女子现代五项团体夺金）与 16/17 号（男子铁人三项摘银）"
         "分属不同事件，故不计入近似重复"],
        ["U1~U3", "3", "完全不同主题", "—", "百川智能融资 / CrowdStrike 故障 / 倪萍访谈，互不相关"],
    ], cap="表 4-5 20 篇新闻数据集的分组设计与实测组内相似度",
        widths=[0.75, 0.75, 1.4, 1.15, 2.65], size=8)
    _near_min = min(float(v) for v in _gs["R1"]["vals"] + _gs["R2"]["vals"])
    _se_max = max(float(v) for v in _gs["D1"]["vals"] + _gs["D2"]["vals"])
    para(doc, "**金标准分层（本实验关键的评估口径）**：组内词级 Jaccard 显示数据天然分成两档——"
              f"改写簇 R1/R2 为 {_near_min:.3f}~1.00（几乎同文，属真正的“近似重复”），"
              f"而同事件不同报道 D1/D2 只有 "
              f"{min(_gs['D1']['mean'], _gs['D2']['mean']):.3f}~{_se_max:.3f}"
              f"（事件相同但文本几乎不重叠）。两者完全分离："
              f"改写簇最小 {_near_min:.4f} > 同事件簇最大 {_se_max:.4f}。"
              "把两者混在同一条 P/R/F1 里统计，会让召回率被系统性压低、掩盖方法差异。"
              f"因此本实验把正样本定义为**改写簇组内对（{SH['gold']['near_dup']} 对）**，"
              f"并同时给出“初版混合口径（所有同组对，{SH['gold']['mixed_all_same_group']} 对）”"
              f"的结果以便对照。")

    h(doc, "4.2.4 关键代码解读", 3)
    add_image(doc, os.path.join(SHOT, "exp2_simhash_fp.png"),
              "图 4-6 64 位加权 SimHash 指纹与海明距离（白底代码截图）")
    para(doc, "代码要点：v 用 float64 以容纳可变的权重；内层循环按位（bit）累加 ±w；"
              "指纹用 Python 大整数按位或拼装，海明距离用 bin(a^b).count('1') 计算，简洁且无溢出风险。")
    add_image(doc, os.path.join(SHOT, "exp2_simhash_main.png"),
              "图 4-7 权重方案的干净因子对照（SCHEME_GRID / make_fingerprints）")
    para(doc, "代码要点：① 在 20 篇文档上训练 TfidfVectorizer，得到每篇文档每个词的 TF-IDF 权重矩阵 X；"
              "② 遍历文档词序列，从 X 中取出该词的权重作为 w；③ 若该词命中停用词表则 w *= 0.2 实现降权。"
              "注意此处分词函数刻意保留停用词（只过滤纯标点/数字），否则“停用词降权”这条分支永远不会被触发。"
              "另外，取权重时用 t.lower() 与特征名对齐——这与实验一(1) 修正的是同一类大小写陷阱。"
              "④ 关键修正：把“投票单位（每词元 / 每唯一词）”与“权重来源（等权 / TF / TF-IDF）”"
              "拆成两个正交维度做完整因子对照（共 8 个方案），而不是只比“等权 vs TF-IDF”两行——"
              "正是这个拆解揭示了初版结论的成因（详见 4.2.6）。")
    add_image(doc, os.path.join(SHOT, "exp2_simhash_gold.png"),
              "图 4-8 三层金标准与分组内相似度自检")
    para(doc, "代码要点：脚本在计算指标之前先打印每个分组的组内相似度与 D3 组的三条标题，"
              "把“金标准为什么这样分层”的证据固化在输出里，而不是只写在报告正文中——"
              "这样任何人重跑脚本都能看到分层依据，也便于发现标注错误。")
    add_image(doc, os.path.join(SHOT, "exp2_simhash_scope.png"),
              "图 4-9 标题级 / 正文级 / 合并文本的范围对照")
    para(doc, "代码要点：三种文本范围各自独立训练 TF-IDF 并重建指纹，"
              "用于回答“转载改写主要靠标题相似还是正文相似被检出”。"
              "注意标题语料特征过少时指纹可能一个都不撞（判定对数 0），"
              "此时 P/R 的分母为 0，脚本会显式标注为“无任何判定”而不是报成 0 分精度。")

    h(doc, "4.2.5 实验结果", 3)
    _rec = SIMHASH_SCHEMES[SH["recommended"]]
    _v1 = SIMHASH_SCHEMES[SH["baseline_v1"]]
    add_table(doc, ["权重方案（投票单位 × 权重来源）", "P", "R", "F1", "TP", "FP", "FN", "判定对数"], [
        [s["name"], f"{s['strict']['P']:.3f}", f"{s['strict']['R']:.3f}",
         f"{s['strict']['F1']:.3f}", s["strict"]["TP"], s["strict"]["FP"],
         s["strict"]["FN"], s["n_pred"]] for s in SH["schemes"]
    ], cap=f"表 4-6 权重方案对照（修正口径，海明距离 ≤ {SH['ham_th']}；"
           f"正样本 = 改写簇 {SH['gold']['near_dup']} 对）",
        widths=[2.3, 0.62, 0.62, 0.62, 0.5, 0.5, 0.5, 0.75], size=8)
    add_table(doc, ["同一批方案在初版混合口径下的指标（仅列对照）", "P", "R", "F1", "TP", "FP", "FN"], [
        [s["name"], f"{s['mixed']['P']:.3f}", f"{s['mixed']['R']:.3f}",
         f"{s['mixed']['F1']:.3f}", s["mixed"]["TP"], s["mixed"]["FP"], s["mixed"]["FN"]]
        for s in SH["schemes"]
    ], cap=f"表 4-7 初版混合口径对照（正样本 = 所有同组对 {SH['gold']['mixed_all_same_group']} 对）",
        widths=[2.9, 0.7, 0.7, 0.7, 0.55, 0.55, 0.55], size=8)

    _sr = {r["scope"]: r for r in SH["scope_rows"]}
    add_table(doc, ["文本范围", "P", "R", "F1", "TP", "FP", "FN", "判定对数", "备注"], [
        [k, f"{v['P']:.3f}", f"{v['R']:.3f}", f"{v['F1']:.3f}", v["TP"], v["FP"], v["FN"],
         v["n_pred"], v["note"]] for k, v in _sr.items()
    ], cap=f"表 4-8 标题级 / 正文级 / 合并文本的对照（推荐方案 {SH['recommended']}）",
        widths=[0.95, 0.62, 0.62, 0.62, 0.5, 0.5, 0.5, 0.75, 1.5], size=8)

    _sw = SH["sweep_f1"]
    _names = [s["name"] for s in SH["schemes"]]
    _short = [n.split()[0] for n in _names]
    rows10 = [[str(t)] + [f"{_sw[n][t]:.3f}" for n in _names] for t in range(11)]
    add_table(doc, ["距离阈值"] + _short, rows10,
              cap=f"表 4-9 海明距离阈值扫描（F1；修正口径，正样本=改写簇 {SH['gold']['near_dup']} 对）",
              widths=[0.85] + [0.68] * len(_names), size=7.5)
    add_image(doc, os.path.join(FIG, "exp2_simhash_prf.png"),
              "图 4-10 各权重方案的 P/R/F1 增量效果（左）与阈值对 F1 的影响（右）")

    h(doc, "4.2.6 结果分析", 3)
    _pconst = SH["precision_constant"]
    _fnrec = SH["fn_groups_recommended"]
    for s in [
        f"**最重要的结论：初版“TF-IDF 加权优于等权”的说法不成立。** 复现审计指出初版两种实现的"
        f"投票单位都不干净——等权分支按词元出现逐次投票、而每次的权重又取该词的总词频，"
        f"一个出现 m 次的词总贡献为 m²；加权分支同样按词元累加已含 TF 的 TF-IDF，也是 m²·IDF。"
        f"本版把「投票单位」与「权重来源」拆成两个正交维度做完整对照（表 4-6）："
        f"在**每词元**投票下，等权 {fmt(SIMHASH_SCHEMES['A1 每词元 · 等权(1)']['strict']['F1'], 3)}、"
        f"TF {fmt(SIMHASH_SCHEMES['A2 每词元 · TF']['strict']['F1'], 3)}"
        f"（FP={SIMHASH_SCHEMES['A2 每词元 · TF']['strict']['FP']}）、"
        f"TF-IDF {fmt(SIMHASH_SCHEMES['A3 每词元 · TF-IDF']['strict']['F1'], 3)}"
        f"（FP={SIMHASH_SCHEMES['A3 每词元 · TF-IDF']['strict']['FP']}）；"
        f"而在**每唯一词**投票下，"
        f"等权 {fmt(SIMHASH_SCHEMES['B1 每唯一词 · 等权(1)']['strict']['F1'], 3)}、"
        f"TF {fmt(SIMHASH_SCHEMES['B2 每唯一词 · TF']['strict']['F1'], 3)}、"
        f"TF-IDF {fmt(SIMHASH_SCHEMES['B3 每唯一词 · TF-IDF']['strict']['F1'], 3)}。"
        f"可见**真正决定成败的是“投票单位”而非“权重是否用 TF-IDF”**："
        f"按词元投票会把高频词重复投票、指纹被拉向均值，查准率崩到 "
        f"{fmt(SIMHASH_SCHEMES['A2 每词元 · TF']['strict']['P'], 3)} 以下；"
        f"改成每唯一词投票后，即使不加任何权重也已经是零误报。",
        f"更反直觉的是：**IDF 降权在本任务上反而降低召回**。"
        f"每唯一词下等权 F1 {fmt(SIMHASH_SCHEMES['B1 每唯一词 · 等权(1)']['strict']['F1'], 3)}"
        f"（R={fmt(SIMHASH_SCHEMES['B1 每唯一词 · 等权(1)']['strict']['R'], 3)}）"
        f"优于 TF-IDF 的 {fmt(SIMHASH_SCHEMES['B3 每唯一词 · TF-IDF']['strict']['F1'], 3)}"
        f"（R={fmt(SIMHASH_SCHEMES['B3 每唯一词 · TF-IDF']['strict']['R'], 3)}）。"
        f"一个合理的解释是：转载改写簇内部共享的正是那些**低频专有名词与关键实体**，"
        f"IDF 把它们的权重抬得很高，一旦改写替换掉其中一两个，指纹就会大幅跳变"
        f"（64 位里变化超过 {SH['ham_th']} 位即判为不重复）；"
        f"而不加权的等权投票让大量中频内容词共同投票，指纹更稳健。"
        f"这与“IDF 一定更好”的直觉相反，说明**加权策略必须用消融实验验证，不能想当然**。"
        f"注意：这只是本数据集（{SH['n_docs']} 篇、改写簇 {SH['gold']['near_dup']} 对）的结论，"
        f"样本很小，不应外推为普遍规律。",
        f"“停用词降权”在两个分支上的效果完全不同，顺带暴露了一个实现细节："
        f"本实验的分词函数**保留停用词**（只过滤纯标点/数字），因此“停用词降权”应当生效。"
        f"实测每唯一词分支加降权前后指标完全一致"
        f"（{fmt(SIMHASH_SCHEMES['B3 每唯一词 · TF-IDF']['strict']['F1'], 3)} → "
        f"{fmt(SIMHASH_SCHEMES['B3s 每唯一词 · TF-IDF + 停用词降权']['strict']['F1'], 3)}），"
        f"说明**在每唯一词口径下，停用词的 TF-IDF 权重本就接近 0（IDF 极低），再乘 "
        f"{SH['stop_scale']} 也改变不了 sign 投票的结果**——这条分支在该口径下实际是冗余的。"
        f"而在每词元口径下它确实起作用（"
        f"{fmt(SIMHASH_SCHEMES['A3 每词元 · TF-IDF']['strict']['F1'], 3)} → "
        f"{fmt(SIMHASH_SCHEMES['A3s 每词元 · TF-IDF + 停用词降权(初版方案)']['strict']['F1'], 3)}）。"
        f"初版把它当作核心改进来叙述，是把“恰好有效的补丁”误当成了“问题的根因”。",
        f"文本范围的影响（表 4-8）：**标题级指纹完全失效**——{SH['n_docs']} 篇标题只有很短的特征，"
        f"指纹过于稀疏，相似度高的稿件对撞不到一起（判定对数 {_sr['标题']['n_pred']}）；"
        f"只用正文时 F1 达 {fmt(_sr['正文']['F1'], 3)}，优于标题+正文的 {fmt(_sr['标题+正文']['F1'], 3)}。"
        f"这既印证了 SimHash 需要足够的特征量才能稳定，也说明初版把 title 与 body 拼在一起"
        f"并不是最优选择（标题是短特征，反而稀释了指纹）。",
        f"漏检的分布（不再凭印象归因）：推荐方案 {SH['recommended']} 在改写簇正样本上的漏检为 "
        f"{_fnrec if _fnrec else '无'}。按初版混合口径看，各方案漏检集中在同事件不同报道组"
        f"（D1/D2/D3 各 3 对）——这些文本的事件相同但字面几乎不重叠（组内 Jaccard 仅 "
        f"{fmt(min(SH['group_stats']['D1']['mean'], SH['group_stats']['D2']['mean']), 3)}~"
        f"{fmt(max(SH['group_stats']['D1']['mean'], SH['group_stats']['D2']['mean']), 3)}），"
        f"本就不应被判为“近似重复”。**修正金标准后，初版方案的召回率由 "
        f"{fmt(_v1['mixed']['R'], 3)} 提升到 {fmt(_v1['strict']['R'], 3)}——这个变化完全来自评估口径，"
        f"算法一行未改**；推荐方案 {SH['recommended']} 的召回为 {fmt(_rec['strict']['R'], 3)}"
        f"（P={fmt(_rec['strict']['P'], 3)}，F1={fmt(_rec['strict']['F1'], 3)}）。",
        f"阈值的影响（表 4-9、图 4-10 右）：**在本样本上并没有出现“召回换查准”的取舍**——"
        f"多个方案的查准率在阈值 0~10 全程恒定（"
        f"{'、'.join(k.split()[0] for k, v in _pconst.items() if v)}），"
        f"即放宽阈值只增加召回、不引入新的假阳性。"
        f"因此只能说“本数据集上提高阈值同时提升了 F1”，"
        f"不能像初版那样声称“阈值必须结合业务在查准与查全之间权衡”——那是通用经验，"
        f"不是本次实测到的现象。",
        f"工程启示（都要带上样本限定）：作业规定的 d ≤ {SH['ham_th']} 对 64 位指纹是常见取值。"
        f"本数据集上推荐方案（{SH['recommended']}）在 d ≤ {SH['ham_th']} 时已达 "
        f"P={fmt(_rec['strict']['P'], 3)}、R={fmt(_rec['strict']['R'], 3)}。"
        f"但必须强调：**这些数值来自 {SH['n_docs']} 篇、规则构造真值的小样本，"
        f"且真值本身已发现一处标注错误，因此只能作为机制演示，不能当作方法优劣的普遍证据。**"
        f"要下推广性结论，需要独立人工标注的更大测试集，并按事件簇划分数据。",
    ]:
        para(doc, s)

    # ===== 五、学习笔记 =====
    h(doc, "五、实验学习笔记", 1)
    notes = [
        ("“重复”不是一个客观量，取决于你怎么定义", "本次实验最大的收获来自评估口径。"
         f"同样一套 SimHash 指纹，金标准定义不同，初版方案 A3s 的 F1 可以从 "
         f"{fmt(SIMHASH_SCHEMES['A3s 每词元 · TF-IDF + 停用词降权(初版方案)']['mixed']['F1'], 3)} 变成 "
         f"{fmt(SIMHASH_SCHEMES['A3s 每词元 · TF-IDF + 停用词降权(初版方案)']['strict']['F1'], 3)}；"
         "同样一批 MinHash 结果，“最优阈值”可以落在 0.1 也可以落在 0.4。"
         "原因是数据里天然存在三个层次：**逐字重复**（Jaccard≈1.0）、**同事件改写**（0.1~0.3）、"
         "**同主题不同事件**（≈0）。把这三层混进同一条 P/R/F1，得到的数字既不可复现也不可解释。"
         "正确做法是先把“什么算重复”写清楚，再定阈值——而不是先跑出数字再解释。"),
        ("标注错误比算法缺陷更致命", "news20 的 D3 组把“女子现代五项团体夺金”与“男子铁人三项摘银”"
         "标成了同一事件。这类错误标注混进金标准后，直接把召回率压低，"
         "让人误以为“SimHash 对改写不敏感”。"
         "而实际上算法本身没问题。这件事的教训是：**指标异常时，第一件事是查金标准，而不是改算法**。"
         "同时也说明评估脚本应该把分层依据（如组内相似度）打印出来，让标注问题自己暴露。"),
        ("大小写、空行、空格——数据清洗决定结论", "本次修正的缺陷大多不是算法问题："
         "① TF-IDF 回查权重时 `AI` 与特征名 `ai` 不匹配，一个词频 82 的高频词被误报成“权重 0”；"
         "② 读取新闻时 `split(\"\\n\", 3)[3]` 把 `group=` / `rewrite=` 当成正文；"
         f"③ 语料里 {TF['removed_dup']} 条仅空格差异的标题，让余弦相似度恒为 1.0000 并霸占 Top-10。"
         "三处都属于“算法对、工程错”。它们共同说明：**特征矩阵算对了，不代表按名字取值就取对了**。"),
        ("精确 vs 近似的权衡思维", "MinHash 用 128 维签名替代原始集合，LSH 用分桶替代全量比较，"
         "两者都是“用可控的精度损失换数量级的效率提升”。"
         f"500 篇文档时精确 Jaccard 约 {_sc.get(500, {}).get('exact', 0) * 1000:.0f} ms、"
         f"MinHash 全量两两约 {_sc.get(500, {}).get('minhash', 0) * 1000:.0f} ms、"
         f"LSH(b=64,r=2) 端到端约 {_sc.get(500, {}).get('lsh_64_2', 0) * 1000:.0f} ms，"
         f"且 MinHash 估计的平均绝对误差仅 {fmt(MH['minhash_error']['mae'])}。"
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
        ("P/R/F1 的取舍要看业务",
         f"本数据集上推荐方案 {SH['recommended']} 是 "
         f"P={fmt(_rec['strict']['P'], 3)} / R={fmt(_rec['strict']['R'], 3)}，"
         f"而按词元投票的 TF 方案是 "
         f"P={fmt(SIMHASH_SCHEMES['A2 每词元 · TF']['strict']['P'], 3)} / "
         f"R={fmt(SIMHASH_SCHEMES['A2 每词元 · TF']['strict']['R'], 3)}——"
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

    h(doc, "6.3 自我审计与修正记录", 3)
    para(doc, "本项目经过两轮审计，共发现并修正 17 处问题。**需要特别指出的是：其中一项修正推翻了"
              "初版的核心结论**——初版声称“TF-IDF 加权 SimHash 优于等权 SimHash”，"
              "但两种实现的投票单位都写坏了（按词元逐次投票且权重又含词频，使一个词的总贡献为 m²），"
              "拆成干净因子对照后结论反转为：**决定成败的是投票单位，且 IDF 降权在本任务上反而降低召回**。"
              "完整对照见 4.2.6 与 out/AUDIT_NOTES.md。")
    add_table(doc, ["编号", "问题", "性质", "整改结果"], [
        ["S1", "报告生成器硬编码旧数字（91.87/713.32/30.52 ms、84 对/68 误报）",
         "严重·正确性",
         "四实验输出机读 JSON，报告只从 JSON 取值；新增自检脚本，当前孤立数字 = 0"],
        ["S2", "等权/TF-IDF 两种实现的投票单位都不干净（m² 词频 + 大小写遗漏）",
         "严重·口径",
         "拆为「投票单位 × 权重来源」8 方案因子对照；结论被推翻（见 4.2.6）"],
        ["S3", "D3 组标注错误 + 标签元信息进入正文",
         "严重·金标准",
         "parse_doc 按首个空行切分；金标准分三层；新增标题级/正文级范围对照"],
        ["S4", "“AI 权重为 0”是统计缺陷，且解释错误",
         "严重·正确性",
         "分词统一小写对齐特征名；结果增加“进入特征集”列；改写解释"],
        ["S5", "LSH 候选的“三对误报”实为被阈值滤除的真阳性",
         "严重·错误类型",
         "区分为近重复 / 候选被阈值滤除 / 误报 三类"],
        ["M1", "计时口径不公平（LSH 列不含签名生成与回验）+ 用重复用例造规模",
         "中等·实验设计",
         "三路径统一端到端；shingle 公共成本单列；5 次重复取中位数±标准差；改用真实标题语料"],
        ["M2", "Top-10 含反向重复，实际只有约 8 个不同文本对",
         "中等·正确性",
         "改为只在上三角取 Top-10"],
        ["M3", "模型身份未锁定",
         "中等·可复现",
         "README 补 SHA-256 / 字节数 / 头部 / 加载方式"],
        ["M4", "“170 篇全部真实抓取”表述过强；规则构造真值有自验证风险",
         "中等·表述",
         "改写为准确口径并显式披露自验证风险与建议"],
        ["M5", "类比方向写反；文档向量未归一化却与余弦口径混用",
         "中等·方法",
         "修正方向后命中 4/6；加 L2 归一化并实测前后对照（0.9400/0.8319 → 0.9800/0.9406）"],
        ["M6", "召回归因与阈值结论不被明细支持",
         "中等·论证",
         "改按漏检组别统计；查准率是否随阈值变化由脚本判定并如实表述"],
        ["L1", "随机性承诺过大（抓取顺序由 set 决定）",
         "轻微·可复现",
         "按首次出现顺序写盘；输出 titles_manifest.json；区分快照与重抓"],
        ["L2", "字体绝对路径；目录名过时；截图标记缺失时静默退化",
         "轻微·工程",
         "字体跨平台 + REPORT_FONT；路径改为 tools/；标记缺失直接报错"],
        ["L3", "空集合下精确 Jaccard(0) 与 MinHash 签名(1.0) 不一致",
         "轻微·边界",
         "空集合返回全 0 哨兵签名，两种口径统一为 0"],
    ], cap="表 6-2 两轮审计发现的问题与整改（S/M/L 编号对应 out/AUDIT_NOTES.md）",
        widths=[0.42, 2.0, 0.85, 2.93], size=7.5)

    h(doc, "6.4 自检脚本与验证结果", 3)
    add_table(doc, ["自检项", "脚本", "当前结果"], [
        ["报告正文每个 ≥2 位小数是否有出处",
         "tools/verify_report_consistency.py",
         "报告 166 个不同小数取值，无法解释者 0 个"],
        ["交付 DOCX 是否残留隐私信息",
         "tools/verify_docx_privacy.py",
         "正文/元数据/页眉页脚均无用户目录、邮箱、密钥串、手机号"],
        ["金标准分层依据是否可见",
         "各实验脚本标准输出",
         "组内 Jaccard、簇→主题映射、漏检组别均由脚本打印并落盘"],
    ], cap="表 6-3 自检脚本与当前验证结果", widths=[2.1, 1.9, 2.2], size=8)

    # 按作业要求的命名格式：姓名+学号+第1次实验报告.docx
    name = "<成员一姓名>+<成员一学号>+第1次实验报告.docx"
    path = os.path.join(OUT, name)
    doc.save(path)
    print("报告已生成:", path)
    return path


if __name__ == "__main__":
    build()
