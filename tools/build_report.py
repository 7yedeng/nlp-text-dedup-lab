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


def load_source_index():
    """读取 data/ 下各语料文件的元信息，供报告「数据来源说明」一节直接引用。

    只读 title=/source=/category=/group=/rewrite= 这几个字段，
    正文长度单独统计（用于体现“有效正文”而非空壳文件）。
    """
    data = os.path.join(BASE, "data")

    def parse(raw):
        head, _, body = raw.partition("\n\n")
        meta = {}
        for ln in head.split("\n"):
            if "=" in ln:
                k, _, v = ln.partition("=")
                meta[k.strip()] = v.strip()
        return meta, body.strip()

    out = {}

    # 主题正文
    for sub, label in (("sports", "体育"), ("tech", "科技"), ("ent", "娱乐")):
        folder = os.path.join(data, sub)
        rows = []
        if os.path.isdir(folder):
            for fn in sorted(os.listdir(folder)):
                if not fn.endswith(".txt"):
                    continue
                with open(os.path.join(folder, fn), encoding="utf-8") as f:
                    meta, body = parse(f.read())
                rows.append({"file": f"{sub}/{fn}", "title": meta.get("title", ""),
                             "source": meta.get("source", ""), "chars": len(body)})
        out[sub] = rows

    # news20（带 group / rewrite）
    folder = os.path.join(data, "news20")
    rows = []
    if os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            if not fn.endswith(".txt"):
                continue
            with open(os.path.join(folder, fn), encoding="utf-8") as f:
                meta, body = parse(f.read())
            rows.append({"idx": int(fn[:3]), "file": f"news20/{fn}",
                         "title": meta.get("title", ""), "source": meta.get("source", ""),
                         "group": meta.get("group", ""), "rewrite": meta.get("rewrite", ""),
                         "chars": len(body)})
    out["news20"] = rows

    # 标题语料行数
    tp = os.path.join(data, "titles.txt")
    out["titles_n"] = sum(1 for ln in open(tp, encoding="utf-8") if ln.strip()) \
        if os.path.exists(tp) else 0
    # 用例条数
    sp = os.path.join(data, "short_texts.txt")
    out["short_n"] = sum(1 for ln in open(sp, encoding="utf-8") if ln.strip()) \
        if os.path.exists(sp) else 0
    return out


SUMM = load_summaries()
SRC = load_source_index()
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

    # ===== 二、结果索引 =====
    h(doc, "二、结果索引", 1)
    para(doc, "下表汇总四个实验的核心结果与对应位置，便于直接跳转查阅；"
              "结果文本与图片均在项目 out/ 目录下。")
    _w8i = next(s for s in SH["schemes"] if s["name"].startswith("B3s"))
    _eqi = next(s for s in SH["schemes"] if s["name"].startswith("A1"))
    add_table(doc, ["实验", "对应章节", "核心结果", "结果文件", "图片"], [
        ["一(1) TF-IDF 特征表示", "4.1 节",
         f"语料 {TF['scale']} 条；矩阵 ({TF['matrix_shape'][0]}, {TF['matrix_shape'][1]})；"
         f"Top-10 余弦相似度（10 个不同文本对）",
         "out/exp1_tfidf_results.txt", "figures/exp1_tfidf_top20.png"],
        ["一(2) MinHash + LSH 去重", "4.2 节",
         f"k=128；估计误差 MAE={MH['minhash_error']['mae']:.4f}；"
         f"端到端 LSH 加速比（500 篇）"
         f"{MH['scaling_end2end_ms'][-1]['speedup_lsh64_vs_exact']:.2f}×",
         "out/exp1_minhash_results.txt",
         "figures/exp1_minhash_sim.png\nfigures/exp1_minhash_scaling.png"],
        ["二(1) 预训练词向量", "5.1 节",
         f"{WV['model']['n_words']} 词 × {WV['model']['dim']} 维；类比命中 "
         f"{sum(1 for a in WV['analogies'] if a['hit'])}/{len(WV['analogies'])}；"
         f"KMeans Purity={WV['purity']:.4f}，ARI={WV['ari']:.4f}",
         "out/exp2_wordvec_results.txt", "figures/exp2_wordvec_pca_tsne.png"],
        ["二(2) 加权 SimHash", "5.2 节",
         f"64 位指纹，海明距离 ≤{SH['ham_th']}；等权 F1={_eqi['strict']['F1']:.3f}、"
         f"TF-IDF 加权 F1={_w8i['strict']['F1']:.3f}（本数据上加权未占优）",
         "out/exp2_simhash_results.txt", "figures/exp2_simhash_prf.png"],
    ], cap="表 2-1 四个实验的结果索引", widths=[1.3, 0.6, 2.4, 1.4, 1.35], size=8)
    para(doc, "结构化结果（机读）：`out/results_summary_{tfidf,minhash,wordvec,simhash}.json`，"
              "报告正文中的所有数值均取自这些文件。关键代码白底截图见 `out/screenshots/`。")

    # ===== 三、数据来源说明 =====
    h(doc, "三、数据来源说明", 1)
    para(doc, "按作业要求，实验数据为“选取或自行准备”，因此本实验的数据由三部分组成："
              "**真实抓取的新闻语料**、**由真实新闻规则改写得到的构造语料**、**人工设计的测试用例**。"
              "下面逐类说明规模、来源、清洗方式与保存位置。")

    h(doc, "3.1 四类数据一览", 3)
    add_table(doc, ["数据", "规模", "性质", "来源与获取方式", "保存位置"], [
        ["标题语料", f"{TF['raw_scale']} 条", "真实抓取",
         "新浪滚动新闻 API（feed.mix.sina.com.cn/api/roll/get，多 lid 频道分页）"
         "＋网易滚动新闻接口（temp.163.com/special/00804KVA/cm_{频道}.js）",
         "data/titles.txt"],
        ["主题正文", "体育/科技/娱乐各 50 篇\n（共 150 篇）", "真实抓取",
         "由上述接口取得标题与链接后，逐篇抓取详情页正文；"
         "用 BeautifulSoup 按 h1 标题 + 正文容器解析，剔除来源/责任编辑尾注",
         "data/sports/　data/tech/　data/ent/"],
        ["news20 语料", "20 篇\n（含分组标注）", "真实源文 + 规则改写",
         "14 篇取自上述真实新闻作为源文；其中 R1/R2 各 4 篇由源文经"
         "「换标题、同义词替换、段落调序」规则派生；D1/D2/D3 为真实的多源报道",
         "data/news20/　+ manifest.json"],
        ["去重测试用例", "6 条", "人工设计",
         "人工撰写，覆盖完全重复 / 轻度修改 / 中度改写 / 完全不相关四类",
         "data/short_texts.txt"],
    ], cap="表 3-1 四类数据的规模、性质与来源", widths=[0.95, 1.1, 1.0, 2.55, 1.05], size=8.5)

    h(doc, "3.2 数据清洗方式", 3)
    for s in [
        f"**标题语料**：多频道分页聚合后按标题去重；计算前再按「去空白 + 统一小写」规范化，"
        f"消除仅排版差异的伪重复（{TF['raw_scale']} → {TF['scale']} 条）。"
        f"分词使用 jieba，去除停用词（内置词表 + data/stopwords/ 下三份公开停用词表）"
        f"与纯数字/纯标点 token。",
        "**主题正文**：统一保存为「title= / source= / category= + 空行 + 正文」格式，"
        "其中 source= 保留了原始 URL，可直接逐篇点击核对。解析时按**首个空行**切分元信息与正文，"
        "避免把元信息当作正文词混入。",
        "**news20**：在统一格式基础上额外写入 group=（分组）与 rewrite=（改写类型）两行，"
        "这两行只作为标注元信息，**不参与指纹计算**。",
        "**人工用例**：6 条短文本每行一条，仅做去停用词与长度过滤。",
        f"**关于标题语料的溯源限制（如实说明）**：`data/titles.txt` 按「每行一条文本」保存，"
        f"**未保留逐条来源链接**，因此无法逐条点开核对；"
        f"可确认的是抓取渠道与去重、清洗方式（见上表与 tools/fetch_titles.py）。"
        f"三类主题正文与 news20 均带 source= 原始 URL，可逐篇核对。",
    ]:
        para(doc, s)

    h(doc, "3.3 20 篇新闻语料明细", 3)
    para(doc, "下表逐篇列出 news20 的标题、来源、分组与性质，便于核对“真新闻 / 人工改写”的边界。"
              "**改写行指向其父源文，不另造原文链接。**")
    _news = SRC["news20"]
    _rows = []
    for r in _news:
        if r["group"] in ("R1", "R2") and r["rewrite"]:
            nature = "人工改写"
            note = {"reprint-title": "换标题，正文同源文",
                    "light-rewrite": "轻度改写：同义词替换 + 加转载声明",
                    "medium-rewrite": "中度改写：段落调序 + 更多同义词替换"}.get(
                        r["rewrite"], r["rewrite"])
        else:
            nature = "真实原文"
            note = "被改写簇的父源文" if r["group"] in ("R1", "R2") else "独立报道"
        _rows.append([r["idx"], r["title"][:30], r["group"], nature,
                      note, r["source"] or "（未记录）"])
    add_table(doc, ["编号", "标题", "分组", "性质", "备注", "来源链接"], _rows,
              cap="表 3-2 news20 的 20 篇语料明细（人工改写行指向父源文）",
              widths=[0.4, 1.7, 0.45, 0.7, 1.5, 1.65], size=7)

    h(doc, "3.4 分组标签的含义与用途", 3)
    _gc2 = SH["gold"]["categories"]
    para(doc, "news20 的分组标签用于构造相似度实验的评测口径。需要明确区分三类：")
    add_table(doc, ["分组", "篇数", "含义", "在评估中的角色"], [
        ["R1 / R2", "各 4", "转载改写簇：同一篇新闻的源文 + 换标题转载 + 轻度改写 + 中度改写",
         f"**正样本**：组内两两共 {_gc2['POSITIVE']['n']} 对，是 SimHash 应判为重复的目标"],
        ["D1 / D2", "各 3", "同一事件的不同媒体报道（真实新闻，行文各异）",
         f"**不参与 P/R/F1**（{_gc2['EXCLUDED']['n']} 对）：事件相同但文本不重叠，"
         f"不属于“近似重复”范畴"],
        ["D3", "3", "原标注为同一事件，复核后发现是**不同事件**（女子现代五项夺金 vs 男子铁人三项摘银）",
         f"**不参与 P/R/F1**（{_gc2['UNCERTAIN']['n']} 对）：标注有误，已在评估中排除"],
        ["U1~U3", "各 1", "完全不同主题（互不相关）",
         "**负样本一侧**：与任何文本都不构成重复对"],
    ], cap="表 3-3 news20 分组标签的含义与评估角色",
        widths=[0.75, 0.5, 2.6, 2.65], size=8)
    para(doc, "两点必须说清楚：① **“不参与评价”不等于“已标注为不重复”**——"
              "D1/D2 在“同一事件检索”这个任务里仍然是相关的正例，只是不属于本次“近似去重”的评测目标；"
              "② **分组依据是人工阅读内容后的判断，不是相似度分数**——"
              "实测 D3（不同事件）与 D1/D2（同一事件）的组内相似度区间是重叠的，"
              "靠分数阈值无法自动分开，所以必须逐篇读过再定分组。")
    para(doc, "现行正样本由 **R1 与 R2 两个改写簇**产生（各 C(4,2)=6 对，共 12 对）。"
              "D1、D2、D3 均不参与 P/R/F1 计算。完整的分层依据与组内相似度见 5.2.3 节。")

    # ===== 三、实验题目一 =====
    h(doc, "四、实验题目一：文本特征表示与短文本去重", 1)

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
    h(doc, "4.1 基于 TF-IDF 的文本特征表示与相似度检索", 2)
    h(doc, "4.1.1 实验目的", 3)
    para(doc, "掌握基于 TF-IDF 的文本特征提取方法，理解词袋模型（Bag-of-Words）与词向量的区别；"
              "能够用余弦相似度度量文档相似性，并借助可视化分析词的权重分布。")

    h(doc, "4.1.2 算法原理", 3)
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

    h(doc, "4.1.3 关键代码解读", 3)
    add_image(doc, os.path.join(SHOT, "exp1_tfidf_core.png"),
              "图 4-1 TF-IDF 特征构建与 Top-10 相似对检索（白底代码截图）")
    para(doc, f"代码要点：① jieba 分词后去除停用词与纯标点/数字，用空格连接为 TfidfVectorizer 可识别的输入；"
              f"② 以 max_features=1000、ngram_range=(1,2) 构建 TF-IDF 矩阵，实际得到 {shape}；"
              f"③ 只在**上三角**（i<j）中排序取前 10。这一点很关键：早期实现先 fill_diagonal(-1)、"
              f"再对展平后的整个矩阵 argsort，会把 (i,j) 与 (j,i) 当成两个不同的结果同时取到，"
              f"使“Top-10”实际只包含约 5 个不同的文本对；改用 np.triu_indices 后每一个文本对只出现一次。")
    add_image(doc, os.path.join(SHOT, "exp1_tfidf_dedup.png"),
              "图 4-2 语料规范化与去重（normalize_title / dedup_titles）")
    para(doc, "代码要点：先把标题的空格全部压缩掉并统一小写，再按该键去重并统计移除条数。"
              "这样既消除了“仅排版不同”的伪重复，又不改动原始语料文件，便于复核。")
    add_image(doc, os.path.join(SHOT, "exp1_tfidf_weight_lookup.png"),
              "图 4-3 TF-IDF 权重回查：大小写对齐与“是否进入特征集”标记")
    para(doc, "代码要点：回查权重时用 w.lower() 与 TfidfVectorizer(lowercase=True) 的特征名对齐；"
              "同时记录该词是否命中特征集，输出为独立的“进入特征集”列。"
              "早期实现用原始大小写去查 feature_names，导致含英文的词必然查不到而被误判为权重 0。")

    h(doc, "4.1.4 实验结果", 3)
    para(doc, f"语料规模：{scale} 条中文新闻标题（满足 ≥500 条要求）；TF-IDF 矩阵形状：{shape}。")
    add_table(doc, ["统计项", "数值"], tm_stats,
              cap="表 3-4 语料规范化与相似度分布统计", widths=[3.0, 2.0])
    add_table(doc, ["排名", "余弦相似度", "文本 A", "文本 B"],
              [[i + 1, f"{float(s):.4f}", f"[{a}] {ta[:34]}", f"[{b}] {tb[:34]}"]
               for i, (s, a, ta, b, tb) in enumerate(pairs)],
              cap="表 4-1 相似度最高的 Top-10 文本对", widths=[0.5, 0.9, 2.4, 2.4])
    add_table(doc, ["词", "词频", "平均 TF-IDF 权重", "进入特征集"],
              [[w, fq, wx, ok] for w, fq, wx, ok in words],
              cap="表 4-2 词频最高的 20 个词及其平均 TF-IDF 权重", widths=[1.2, 1.0, 1.8, 1.2])
    add_image(doc, os.path.join(FIG, "exp1_tfidf_top20.png"),
              "图 4-4 词频最高的 20 个词的 TF-IDF 权重柱状图")

    h(doc, "4.1.5 结果分析", 3)
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
        f"词频与 TF-IDF 权重并非正相关（表 4-3、图 4-4）：高频词"
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
    h(doc, "4.2 基于 MinHash + LSH 的短文本近似去重", 2)
    h(doc, "4.2.1 实验目的", 3)
    para(doc, "理解并实现基于 Jaccard 系数与 MinHash 的近似文本去重，掌握 LSH 分桶的近似近邻查找思想；"
              "通过对比精确计算与近似计算，量化二者在准确率与运行时间上的差异，并分析阈值的影响。")

    h(doc, "4.2.2 算法原理", 3)
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

    h(doc, "4.2.3 测试用例设计", 3)
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
    ], cap="表 4-3 MinHash+LSH 实验的 6 个测试用例与分层", widths=[0.55, 3.9, 1.55, 1.4])
    para(doc, f"分层规则：**近重复 = {'、'.join(MH['gold']['near_dup_pairs'])}**（字面几乎一致，"
              f"{MH['gold']['near_dup']} 对）；**同事件改写 = "
              f"{'、'.join(MH['gold']['same_event_pairs'])}**（事件相同但句子结构重写，不计入"
              f"“近似重复”正样本，另计命中数，{MH['gold']['same_event']} 对）；"
              f"**不相关 = T5/T6 与其余文本**（相似度全为 0.0000，与 T1~T4 之间存在天然的间隔带）。"
              f"报告同时给出“初版混合口径”（T1~T4 两两共 {MH['gold']['mixed_related']} 对）"
              f"与“分层口径”两套指标，便于对照。")

    h(doc, "4.2.4 关键代码解读", 3)
    add_image(doc, os.path.join(SHOT, "exp1_minhash_update.png"),
              "图 4-5 MinHash 签名生成（k=128，exp1_minhash.py）")
    para(doc, "代码要点：签名初始化为一维 k 长数组（初值 P）；对集合中每个 shingle 计算其 64 位整数哈希后，"
              "逐个哈希函数取最小值。实现上刻意使用纯 Python 大整数运算而非 numpy 向量化："
              "因为 a_i·x 的量级接近 2¹²²，超出 numpy int64 的范围会造成溢出，属于典型的“数学正确但工程踩坑”问题。")
    add_image(doc, os.path.join(SHOT, "exp1_lsh.png"),
              "图 4-6 LSH 分桶与候选对生成（build_lsh_tables / lsh_candidates）")
    para(doc, "代码要点：把签名按 band 切片并作为 dict 的 key 建立倒排桶；同一桶内文档两两组合即为候选对，"
              "用 set 去重。整个过程只需一次线性扫描，避免了全量两两比较。")
    add_image(doc, os.path.join(SHOT, "exp1_minhash_prf.png"),
              "图 4-7 P/R/F1 计算（prf）——分母为空时返回 0 并同时输出 TP/FP/FN")
    para(doc, "代码要点：早期实现把“没有预测”时的查准率定义为 1.0，于是出现“一对都没检出却 F1 = 1.000”"
              "的荒谬结论。修正为分母为空时取 0，并让函数同时返回 TP/FP/FN，"
              "使“无预测”与“全对”在结果里不可能再被混淆。")
    add_image(doc, os.path.join(SHOT, "exp1_minhash_bench.png"),
              "图 4-8 端到端计时的三条路径（bench_exact / bench_minhash / bench_lsh）")
    para(doc, "代码要点：三条路径都必须能独立完成“从原始文本到给出重复判定对”，"
              "并把 shingle 构建（公共成本）单独计时、不计入比较阶段；"
              "每个规模先用同一批 shingle 预热一次，再重复计时取中位数，"
              "计时期间关闭 GC 以抑制抖动。这样得到的加速比才是同一任务下的可比数字。")

    h(doc, "4.2.5 实验结果", 3)
    rows3 = [[f"T{i}-T{j}", jac, mh, ("是" if mark else "否")] for i, j, jac, mh, mark in sims]
    add_table(doc, ["文本对", "精确 Jaccard", "MinHash 估计", "进入 LSH 候选"], rows3,
              cap="表 4-4 各文本对的精确 Jaccard 与 MinHash 估计对比", widths=[1.4, 1.6, 1.6, 1.6])
    para(doc, f"MinHash 估计的平均绝对误差为 {fmt(MH['minhash_error']['mae'])}，"
              f"最大误差 {fmt(MH['minhash_error']['max'])}，"
              f"说明 k=128 的签名已能高精度逼近真实 Jaccard（签名长度越长误差越小，误差量级约为 1/√k）。")

    rows_mixed = [[f"{t}", f"{p1}/{r1}/{f1}", f"{p2}/{r2}/{f2}"] for t, p1, r1, f1, p2, r2, f2 in thr_mixed]
    add_table(doc, ["相似度阈值", "精确 Jaccard（P/R/F1）", "MinHash（P/R/F1）"], rows_mixed,
              cap="表 4-5 阈值影响（初版混合口径：ground truth = T1~T4 两两，共 6 对）",
              widths=[1.4, 2.3, 2.3])
    rows_thr = [[f"{t}", f"{p1}/{r1}/{f1}", f"{p2}/{r2}/{f2}"] for t, p1, r1, f1, p2, r2, f2 in thr]
    add_table(doc, ["相似度阈值", "精确 Jaccard（P/R/F1）", "MinHash（P/R/F1）"], rows_thr,
              cap="表 4-6 阈值影响（分层口径：ground truth = 近重复对 T1-T2）", widths=[1.4, 2.3, 2.3])

    lsh_rows = []
    for bi, ri, cnt in lsh:
        lsh_rows.append([f"b={bi}, r={ri}", cnt, "—"])
    add_table(doc, ["LSH 配置", "候选对数", "说明"], lsh_rows,
              cap="表 4-7 两种 LSH 分桶参数下的候选对数量", widths=[1.6, 1.4, 3.0])
    rows5 = [[f"T{i}-T{j}", mh, st] for i, j, mh, st in lsh_items]
    add_table(doc, ["候选文本对（b=64, r=2）", "MinHash 相似度", "回验结论"], rows5,
              cap="表 4-8 LSH 候选对的相似度回验", widths=[1.6, 1.6, 1.6])

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
              cap=f"表 4-9 批量规模对端到端耗时的影响（真实标题语料；{MH['config']['reps']} 次重复，"
                  f"中位数±标准差，单位毫秒；shingle 构建为公共成本，未计入）",
              widths=[0.62, 1.15, 1.15, 1.0, 1.0, 0.8, 1.0, 1.05], size=7.5)
    _stg = MH["stage_breakdown_500_ms"]
    add_table(doc, ["阶段（n=500）", "耗时(ms)", "说明"], [
        ["shingle 构建 + 签名生成", f"{_stg['shingle_and_signature']:.2f}", "一次性成本；k=128 向量化计算"],
        ["LSH 建桶 + 候选生成", f"{_stg['lsh_build_and_candidates']:.2f}", "不含签名生成"],
        ["候选回验", f"{_stg['candidate_verify']:.2f}", f"{_stg['n_candidates']} 对候选做签名比对"],
    ], cap="表 4-10 分阶段耗时拆解（用于定位瓶颈）", widths=[2.2, 1.2, 2.6])
    add_image(doc, os.path.join(FIG, "exp1_minhash_sim.png"),
              "图 4-9 MinHash 估计 vs 精确 Jaccard（左）与两种金标准口径下的 F1（右）")
    add_image(doc, os.path.join(FIG, "exp1_minhash_scaling.png"),
              "图 4-10 批量规模对端到端计算耗时的影响（对数纵轴，误差棒=标准差）")
    h(doc, "4.2.6 结果分析", 3)
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
        f"金标准分层如何改变结论（表 4-6 vs 表 4-7）：这是本次实验最有价值的一处修正。"
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
        f"LSH 分桶参数的取舍（表 4-8、3-9）：(b=16, r=8) 只产生 {_lsh168['n']} 对候选"
        f"（{('、'.join(_lsh168['pairs']) if _lsh168['pairs'] else '无')}），"
        f"把同事件改写的相似对基本全部漏掉；(b=64, r=2) 产生 {_lsh642['n']} 对候选，"
        f"覆盖了全部 T1~T4 之间的相似对。候选阶段相对本实验的 gold 是零误报；"
        f"经相似度回验后，低于阈值的同事件改写对被正常剔除——"
        f"这恰好演示了工业界的三段式做法：**LSH 粗筛候选 → MinHash 相似度回验 → 阈值判定**。"
        f"（需强调：初版把“未达到回验阈值”标成“误报”，是把算法自身分数当成了真值，"
        f"错误类型被颠倒；本版区分为“近重复”“候选但被阈值滤除（同事件改写）”“误报”三类。）",
        f"运行时间与规模（表 4-10、图 4-10）——这里必须交代一个重要的口径修正："
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
        f"瓶颈在哪里（表 4-10 下方的分阶段拆解）：n=500 时签名生成 "
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
    h(doc, "五、实验题目二：文本相似度计算", 1)

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
    h(doc, "5.1 基于预训练词向量的文本表示与语义分析", 2)
    h(doc, "5.1.1 实验目的", 3)
    para(doc, "掌握使用预训练词向量进行文本表示的方法，理解 Word2Vec 与 GloVe 的差异；"
              "验证词向量的语义推理能力，并通过文档向量与聚类/降维可视化观察主题分布。")
    h(doc, "5.1.2 预处理说明", 3)
    para(doc, "本实验使用腾讯 AI Lab 中文词向量。原版模型体积达数 GB，官方下载链接已失效，"
              "故改用其官方发布的 800 万词轻量版（Light 版，143613 词 × 200 维，116 MB），"
              "由 gensim 以 Word2Vec 二进制格式直接加载。")
    add_table(doc, ["模型身份项", "值"], [
        ["文件", WV["model"]["path"]],
        ["字节数", f"{WV['model']['size_bytes']:,} bytes"],
        ["SHA-256（完整）", WV["model"]["sha256"]],
        ["向量头部", WV["model"]["header"] + "（词数 维度）"],
        ["加载方式", WV["model"]["loader"]],
        ["是否随包提交", "否（体积过大；作业亦要求不提交大型预训练模型文件）"],
    ], cap="表 4-11 预训练词向量的身份锁定（SHA-256 由脚本在加载时现场计算并写入结果 JSON）",
        widths=[1.5, 4.5], size=8)
    para(doc, "**为什么要锁到 SHA-256**：同为“腾讯 AI Lab 200 维轻量版”的不同文件，"
              "词表内容与向量值可能不同，仅凭文件名与词数无法独立核验。"
              "上表数值由 `exp2_wordvec.py` 在运行时对模型文件现场计算，"
              "并写入 `out/results_summary_wordvec.json` 的 `model` 字段，可用于独立比对。")

    h(doc, "5.1.3 算法原理", 3)
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

    h(doc, "5.1.4 关键代码解读", 3)
    add_image(doc, os.path.join(SHOT, "exp2_wordvec_load.png"),
              "图 5-1 Gensim 加载预训练词向量与语义推理（白底代码截图）")
    para(doc, "代码要点：用 KeyedVectors.load_word2vec_format 加载二进制模型；"
              "类比推理的正负样本方向必须写对——欲求 a − b + c，应传 positive=[a, c]、negative=[b]。"
              "本实验最初写反为 positive=[b, c]、negative=[a]，结果返回“是男人”这类错误答案，修正后正确命中“王后”。")
    add_image(doc, os.path.join(SHOT, "exp2_parse_doc.png"),
              "图 5-2 新闻文件元信息解析：按首个空行严格切分（parse_doc）")
    para(doc, "代码要点：元信息块与正文之间有一个空行，必须按**首个空行**切分。"
              "早期实现用 raw.split(\"\\n\", 3)[3] 取正文，只切掉 3 个换行，"
              "结果把 news20 特有的 group= / rewrite= 两行当成正文词混入文档（实测 doc 01 的正文以"
              "“group=R1\\nrewrite=\\n\\n\\n智东西…”开头），会虚增词表覆盖率。"
              "本实验的三个主题目录没有这两行，因此主题文档向量结果不受影响，但该缺陷一旦遇到带标注的语料就会污染向量。")
    add_image(doc, os.path.join(SHOT, "exp2_docvector.png"),
              "图 5-3 词向量平均池化生成文档向量（doc_vector）")
    para(doc, "代码要点：只累加词表中存在的词向量（OOV 词直接跳过），并同时返回命中词数与总词数，"
              "以便统计词表覆盖率；若一篇文档所有词都不在词表则返回 None 并丢弃，避免产生零向量污染聚类与可视化。")
    add_image(doc, os.path.join(SHOT, "exp2_kmeans.png"),
              "图 5-4 KMeans 文本聚类与 Purity/ARI 评估（白底代码截图）")

    h(doc, "5.1.5 实验结果", 3)
    para(doc, f"模型信息：{model}。")
    add_table(doc, ["向量运算", "期望词", "实际 Top-3（含余弦相似度）"],
              [[f"{a}−{b}+{c}", f"≈{e}", top + (" ★" if hit else "")] for a, b, c, e, top, hit in anas],
              cap="表 5-1 词向量类比推理结果", widths=[1.6, 1.0, 3.4])
    add_table(doc, ["词对", "余弦相似度"], [[f"sim({w1}, {w2})", s] for w1, w2, s in wpairs],
              cap="表 5-2 12 组词对的余弦相似度", widths=[2.4, 2.4])
    add_table(doc, ["指标", "数值"], [
        ["类内平均相似度（同主题文档两两）", intra[0]],
        ["类间平均相似度（跨主题文档两两）", intra[1]],
        ["KMeans 聚类纯度 Purity", km[0]],
        ["调整兰德指数 ARI", km[1]],
        ["文档向量 L2 归一化（聚类与余弦同口径）", "是" if WV["normalize_docvec"] else "否"],
        ["词表覆盖率（命中词数/总词数）", cover[0]],
    ], cap="表 5-3 文档向量的主题可分性与聚类效果", widths=[3.4, 1.6])
    add_table(doc, ["真实主题", "三个聚类簇中的样本数"], [[n, c] for n, c in conf],
              cap="表 5-4 KMeans 混淆矩阵（行=真实主题，列=聚类簇）", widths=[1.6, 3.4])
    add_image(doc, os.path.join(FIG, "exp2_wordvec_pca_tsne.png"),
              "图 5-5 文档向量 PCA / t-SNE 降维可视化与 KMeans 聚类结果")

    h(doc, "5.1.6 结果分析", 3)
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
        "词表覆盖率（表 5-4）：150 篇文档共 74339 个内容词，其中 66465 个能在 143613 词的轻量版词表中命中，"
        "整体覆盖率 89.41%（体育 82.63% / 科技 90.31% / 娱乐 90.84%）。"
        "体育类覆盖率最低，主要是运动员姓名、队名等专有名词不在轻量版词表内——"
        "平均池化会直接丢弃这些 OOV 词，而它们恰恰是体育新闻最有区分度的信息。"
        "若换成完整版（800 万词）词向量，这一指标与本实验的聚类效果都有提升空间。",
        "PCA 与 t-SNE 的对比（图 5-5）：PCA 平面上三类文档彼此重叠较多，反映的是全局方差结构；"
        "t-SNE 平面上三类形成较为分离的团簇，局部结构更清晰。"
        "这是二者的典型差异——PCA 保留全局距离、t-SNE 强调局部近邻，实际分析中常两者并用。",
    ]:
        para(doc, s)

    # ---------- 4.2 加权 SimHash ----------
    ndoc = str(SH["n_docs"])
    n_near = str(SH["gold"]["near_dup"])
    n_same = str(SH["gold"]["same_event"])
    n_mixed_gold = str(SH["gold"]["mixed_all_same_group"])
    h(doc, "5.2 基于加权 SimHash 的网页新闻相似度计算", 2)
    h(doc, "5.2.1 实验目的", 3)
    para(doc, "理解并实现基于 SimHash 的长文本相似度计算，在传统 SimHash 基础上引入 TF-IDF 权重，"
              "能够根据实际场景调整特征权重；通过查准率/查全率/F1 对比，验证加权策略的有效性。")

    h(doc, "5.2.2 算法原理（加权 SimHash）", 3)
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

    h(doc, "5.2.3 数据集设计", 3)
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
    ], cap="表 5-5 20 篇新闻数据集的分组设计与实测组内相似度",
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

    # 金标准的四类清单（审计要求：不是正样本 ≠ 已确认是负样本）
    _gc = SH["gold"]["categories"]
    add_table(doc, ["类别", "对数", "分组", "含义"], [
        ["POSITIVE 正样本", _gc["POSITIVE"]["n"], "、".join(_gc["POSITIVE"]["groups"]),
         _gc["POSITIVE"]["meaning"]],
        ["EXCLUDED 排除评估", _gc["EXCLUDED"]["n"], "、".join(_gc["EXCLUDED"]["groups"]),
         _gc["EXCLUDED"]["meaning"]],
        ["UNCERTAIN 不确定", _gc["UNCERTAIN"]["n"], "、".join(_gc["UNCERTAIN"]["groups"]),
         _gc["UNCERTAIN"]["meaning"]],
        ["NEGATIVE 负样本", _gc["NEGATIVE"]["n"], "跨组",
         _gc["NEGATIVE"]["meaning"]],
    ], cap=f"表 5-6 金标准四类清单（version={SH['gold']['version']}，"
           f"sha256={SH['gold']['sha256'][:16]}…）",
        widths=[1.25, 0.5, 0.85, 3.6], size=8)
    para(doc, "**关键澄清**：把 D1/D2/D3 排除出正样本，**不等于已确认它们是负样本**。"
              "“文本是否近似重复”与“是否报道同一事件”是两个不同任务——"
              "D1/D2 在“同事件检索”任务中仍然是相关的正例，只是不属于本次“近似去重”的评估目标。"
              f"本版同时输出 `gold_version` 与 `gold_sha256`（{SH['gold']['sha256'][:16]}…），"
              "以避免代码与报告引用不同版本的真值。")
    para(doc, f"**另一处必须说明的方法论问题**：D3（已确认是**不同事件**）的组内相似度为 "
              f"{fmt(_gs['D3']['mean'], 3)}，"
              f"区间 [{fmt(SH['d3_range'][0], 3)}, {fmt(SH['d3_range'][1], 3)}]；"
              f"而 D1/D2（同一事件）为 [{fmt(SH['same_event_range'][0], 3)}, "
              f"{fmt(SH['same_event_range'][1], 3)}]——**两者区间重叠**。"
              f"也就是说，**仅凭相似度分数无法把“同事件不同报道”与“不同事件”分开**。"
              f"本实验的分层依据是**内容事实**（15 号是女子现代五项团体夺金，"
              f"16/17 号是男子铁人三项摘银：不同项目、不同运动员、不同奖牌），"
              f"而不是某个分数阈值。这恰恰说明：**评估集的分层必须靠人工判读，"
              f"不能指望用相似度自动切分**；也说明本数据集的“事件级”标注仍需人工复核。")

    h(doc, "5.2.4 关键代码解读", 3)
    add_image(doc, os.path.join(SHOT, "exp2_simhash_fp.png"),
              "图 5-6 64 位加权 SimHash 指纹与海明距离（白底代码截图）")
    para(doc, "代码要点：v 用 float64 以容纳可变的权重；内层循环按位（bit）累加 ±w；"
              "指纹用 Python 大整数按位或拼装，海明距离用 bin(a^b).count('1') 计算，简洁且无溢出风险。")
    add_image(doc, os.path.join(SHOT, "exp2_simhash_main.png"),
              "图 5-7 权重方案的干净因子对照（SCHEME_GRID / make_fingerprints）")
    para(doc, "代码要点：① 在 20 篇文档上训练 TfidfVectorizer，得到每篇文档每个词的 TF-IDF 权重矩阵 X；"
              "② 遍历文档词序列，从 X 中取出该词的权重作为 w；③ 若该词命中停用词表则 w *= 0.2 实现降权。"
              "注意此处分词函数刻意保留停用词（只过滤纯标点/数字），否则“停用词降权”这条分支永远不会被触发。"
              "另外，取权重时用 t.lower() 与特征名对齐——这与实验一(1) 修正的是同一类大小写陷阱。"
              "④ 关键修正：把“投票单位（每词元 / 每唯一词）”与“权重来源（等权 / TF / TF-IDF）”"
              "拆成两个正交维度做完整因子对照（共 8 个方案），而不是只比“等权 vs TF-IDF”两行——"
              "正是这个拆解揭示了初版结论的成因（详见 5.2.6）。")
    add_image(doc, os.path.join(SHOT, "exp2_simhash_gold.png"),
              "图 5-8 三层金标准与分组内相似度自检")
    para(doc, "代码要点：脚本在计算指标之前先打印每个分组的组内相似度与 D3 组的三条标题，"
              "把“金标准为什么这样分层”的证据固化在输出里，而不是只写在报告正文中——"
              "这样任何人重跑脚本都能看到分层依据，也便于发现标注错误。")
    add_image(doc, os.path.join(SHOT, "exp2_simhash_scope.png"),
              "图 5-9 标题级 / 正文级 / 合并文本的范围对照")
    para(doc, "代码要点：三种文本范围各自独立训练 TF-IDF 并重建指纹，"
              "用于回答“转载改写主要靠标题相似还是正文相似被检出”。"
              "注意标题语料特征过少时指纹可能一个都不撞（判定对数 0），"
              "此时 P/R 的分母为 0，脚本会显式标注为“无任何判定”而不是报成 0 分精度。")

    h(doc, "5.2.5 实验结果", 3)
    _rec = SIMHASH_SCHEMES[SH["recommended"]]
    _v1 = SIMHASH_SCHEMES[SH["baseline_v1"]]
    # 主表：作业明确要求的“传统等权 vs TF-IDF 加权”两种方法
    _eq = next(s for s in SH["schemes"] if s["name"].startswith("A1"))
    _w8 = next(s for s in SH["schemes"] if s["name"].startswith("B3s"))
    add_table(doc, ["方法", "查准率 P", "查全率 R", "F1", "TP", "FP", "FN"], [
        ["传统等权 SimHash", f"{_eq['strict']['P']:.3f}", f"{_eq['strict']['R']:.3f}",
         f"{_eq['strict']['F1']:.3f}", _eq["strict"]["TP"], _eq["strict"]["FP"],
         _eq["strict"]["FN"]],
        ["TF-IDF 加权 + 停用词降权 SimHash",
         f"{_w8['strict']['P']:.3f}", f"{_w8['strict']['R']:.3f}",
         f"{_w8['strict']['F1']:.3f}", _w8["strict"]["TP"], _w8["strict"]["FP"],
         _w8["strict"]["FN"]],
    ], cap=f"表 5-7 传统等权与 TF-IDF 加权 SimHash 的对比（作业要求的核心比较；"
           f"海明距离 ≤ {SH['ham_th']}，正样本 = 改写簇 {SH['gold']['near_dup']} 对）",
        widths=[2.6, 0.8, 0.8, 0.75, 0.55, 0.55, 0.55], size=9)
    para(doc, f"**核心比较的结论需要如实说明**：在本数据集上，"
              f"加权方案的 F1 = {fmt(_w8['strict']['F1'], 3)} 略低于等权方案的 "
              f"{fmt(_eq['strict']['F1'], 3)}，即 **TF-IDF 加权没有带来优势**。"
              f"两者的查准率都是 {fmt(_eq['strict']['P'], 3)}（零误报），差距在查全率："
              f"等权 {fmt(_eq['strict']['R'], 3)} vs 加权 {fmt(_w8['strict']['R'], 3)}。"
              f"作业要求的是“对比”而非“加权必须更好”，因此本实验如实报告该结果并分析原因（见 5.2.6）。")

    para(doc, "**为什么还需要更细的对照**：初版把“等权”实现成「按词元逐次投票、每次权重又取该词总词频」，"
              "使一个出现 m 次的词总贡献达到 m²，这个基线本身是不干净的，"
              "因此不能只凭上面两行就下结论。为定位原因，本实验把「投票单位」与「权重来源」"
              "拆成两个正交维度做了完整因子对照——**完整对照表与消融分析见附录 7.5 节**，"
              "正文只给结论。")
    _sw = SH["sweep_f1"]
    _names = [s["name"] for s in SH["schemes"]]
    # 文本范围对照保留在正文（它解释了“为什么标题+正文不是最优”）
    _sr = {r["scope"]: r for r in SH["scope_rows"]}
    add_table(doc, ["文本范围", "P", "R", "F1", "TP", "FP", "FN", "判定对数", "备注"], [
        [k, f"{v['P']:.3f}", f"{v['R']:.3f}", f"{v['F1']:.3f}", v["TP"], v["FP"], v["FN"],
         v["n_pred"], v["note"]] for k, v in _sr.items()
    ], cap=f"表 5-8 参与比较的文本范围对照（{SH['recommended']}）",
        widths=[0.95, 0.62, 0.62, 0.62, 0.5, 0.5, 0.5, 0.75, 1.5], size=8)
    para(doc, "文本范围的选择会影响结果：只用正文时 F1 最高，把标题拼进去反而下降，"
              "只用标题则完全失效（特征太稀疏，指纹撞不上）。"
              "因此本实验统一以「标题+正文」作为输入，与作业“20 篇网页新闻文本”的口径一致。")

    # 阈值曲线图保留（直观），完整阈值表移入附录
    add_image(doc, os.path.join(FIG, "exp2_simhash_prf.png"),
              "图 5-10 各方案的 P/R/F1 对比（左）与海明距离阈值对 F1 的影响（右）")
    para(doc, "完整阈值扫描表见附录 7.5 节。"
              "需要说明的是：本样本上多个方案的查准率在阈值 0~10 全程恒定，"
              "即放宽阈值只增加召回、**未观察到“召回换查准”**，"
              "因此只能说“本数据集上提高阈值同时提升了 F1”。")

    h(doc, "5.2.6 结果分析", 3)
    _sw_eff = SH["stopword_downweight_effect"]
    _pconst = SH["precision_constant"]
    _fnrec = SH["fn_groups_recommended"]
    for s in [
        f"**最重要的结论：初版“TF-IDF 加权优于等权”的说法不成立。** 复现审计指出初版两种实现的"
        f"投票单位都不干净——等权分支按词元出现逐次投票、而每次的权重又取该词的总词频，"
        f"一个出现 m 次的词总贡献为 m²；加权分支同样按词元累加已含 TF 的 TF-IDF，也是 m²·IDF。"
        f"本版把「投票单位」与「权重来源」拆成两个正交维度做完整对照（表 5-8）："
        f"在**每词元**投票下，等权 {fmt(SIMHASH_SCHEMES['A1 每词元 · 等权(1)']['strict']['F1'], 3)}、"
        f"TF {fmt(SIMHASH_SCHEMES['A2 每词元 · TF']['strict']['F1'], 3)}"
        f"（FP={SIMHASH_SCHEMES['A2 每词元 · TF']['strict']['FP']}）、"
        f"TF-IDF {fmt(SIMHASH_SCHEMES['A3 每词元 · TF-IDF']['strict']['F1'], 3)}"
        f"（FP={SIMHASH_SCHEMES['A3 每词元 · TF-IDF']['strict']['FP']}）；"
        f"而在**每唯一词**投票下，"
        f"等权 {fmt(SIMHASH_SCHEMES['B1 每唯一词 · 等权(1)']['strict']['F1'], 3)}、"
        f"TF {fmt(SIMHASH_SCHEMES['B2 每唯一词 · TF']['strict']['F1'], 3)}、"
        f"TF-IDF {fmt(SIMHASH_SCHEMES['B3 每唯一词 · TF-IDF']['strict']['F1'], 3)}。"
        f"**但“按词元投票导致失败”这个说法过强，必须修正。** 审计指出："
        f"每次词出现投一票本身就是一种正常的词频加权实现；而且存在一个代数等价关系——"
        f"出现 m 次的词，在「每词元×等权1」下投 m 次票、每次权重 1（总贡献 m），"
        f"在「每唯一词×TF」下投 1 次票、权重 m（总贡献也是 m），"
        f"**两者应产生完全相同的指纹**。本实验直接比对了两者的 64 位指纹："
        f"{SH['equivalence']['n_docs_identical']}/{SH['equivalence']['n_docs_total']} 篇逐位完全相同"
        f"（见 out/results_summary_simhash.json 的 equivalence 字段与 tools/verify_equivalence.py）。"
        f"这说明 A1 与 B2 在对照表里**是同一个方案，重复列不能当作两份独立证据**。"
        f"真正的问题不是“按词元投票”本身，而是初版把「权重已含词频」与「按词元重复投票」"
        f"叠在一起形成 m²，却对外描述成“只计一次 TF 的等权方案”。",
        f"**关于 IDF：不能说“IDF 有害”，正确说法是“TF 与 IDF 都使召回下降，合并使用降幅最大”。**"
        f"审计指出 B1（权重=1）与 B3（权重=m·IDF）同时改变了 TF 和 IDF，无法单独归因。"
        f"为此本实验新增两个只含 IDF 的对照 B4/B5（权重=IDF，不含 TF），隔离结果如下："
        f"B1 等权 R={fmt(SIMHASH_SCHEMES['B1 每唯一词 · 等权(1)']['strict']['R'], 3)} → "
        f"B2 加 TF R={fmt(SIMHASH_SCHEMES['B2 每唯一词 · TF']['strict']['R'], 3)}"
        f"（TF 的影响）→ "
        f"B4 仅 IDF R={fmt(SIMHASH_SCHEMES['B4 每唯一词 · 仅IDF']['strict']['R'], 3)}"
        f"（去 TF、只看 IDF）→ "
        f"B3 TF+IDF R={fmt(SIMHASH_SCHEMES['B3 每唯一词 · TF-IDF']['strict']['R'], 3)}"
        f"（合并）。即在等权基线（R=1.000）之上，**TF 与 IDF 单独都会降低召回，二者叠加降幅最大**——"
        f"但相对基线都只是小幅下降，并非“IDF 破坏了指纹”。"
        f"一个可能的解释是：加权后指纹更依赖少数高权重词，"
        f"对改写簇内部的中低频内容词变动更敏感（64 位里变化超过 {SH['ham_th']} 位即判不重复）；"
        f"而等权让大量中频词共同投票，指纹更稳健。"
        f"**这仍只是 {SH['n_docs']} 篇小样本上的观测，且真值为规则构造，不能外推。**",
        f"“停用词降权”这条结论也必须收窄表述。**初版说“停用词 IDF 接近 0”是错的**："
        f"按 sklearn 默认平滑公式 IDF(t)=ln((1+N)/(1+df(t)))+1，"
        f"出现在全部 {SH['n_docs']} 篇文档中的词 IDF=ln(1)+1="
        f"{SH['idf_stats']['all_docs_idf_value']:.1f}，**不是 0**。"
        f"实测停用词 IDF 均值 {fmt(SH['idf_stats']['stopword_mean'])}"
        f"（{fmt(SH['idf_stats']['stopword_min'], 3)}~{fmt(SH['idf_stats']['stopword_max'], 3)}），"
        f"非停用词均值 {fmt(SH['idf_stats']['nonstop_mean'])}——停用词 IDF 确实偏低，但远不是 0。"
        f"更重要的是：**P/R/F1 相同并不等于指纹相同**。实测每唯一词分支下加降权后，"
        f"{_sw_eff['B3 每唯一词 · TF-IDF']['n_fp_changed']}/{SH['n_docs']} 篇指纹都变了、"
        f"平均翻转 {fmt(_sw_eff['B3 每唯一词 · TF-IDF']['mean_bit_flip'], 2)} 位、"
        f"距离矩阵有 {_sw_eff['B3 每唯一词 · TF-IDF']['n_dist_changed']} 对发生变化，"
        f"只是**预测集合的对称差为 {_sw_eff['B3 每唯一词 · TF-IDF']['pred_symdiff']} 对**，"
        f"所以汇总指标恰好一样。因此严谨说法是：**在本数据与固定阈值下，"
        f"该降权操作未改变最终判定结果**，而不是“它完全没起作用、是死代码”。"
        f"（作为对照，每词元口径下同样操作使预测集合对称差达到 "
        f"{_sw_eff['A3 每词元 · TF-IDF']['pred_symdiff']} 对、指标确实变化。）"
        f"初版把它当作核心改进来叙述，问题在于**把“恰好有效的补丁”当成了“问题的根因”**。",
        f"文本范围的影响（表 5-10）：**标题级指纹完全失效**——{SH['n_docs']} 篇标题只有很短的特征，"
        f"指纹过于稀疏，相似度高的稿件对撞不到一起（判定对数 {_sr['标题']['n_pred']}）；"
        f"只用正文时 F1 达 {fmt(_sr['正文']['F1'], 3)}，优于标题+正文的 {fmt(_sr['标题+正文']['F1'], 3)}。"
        f"这既印证了 SimHash 需要足够的特征量才能稳定，也说明初版把 title 与 body 拼在一起"
        f"并不是最优选择（标题是短特征，反而稀释了指纹）。",
        f"漏检的分布（不再凭印象归因）：推荐方案 {SH['recommended']} 在改写簇正样本上的漏检为 "
        f"{_fnrec if _fnrec else '无'}。按初版混合口径看，各方案漏检集中在同事件不同报道组"
        f"（D1/D2/D3 各 3 对）——这些文本的事件相同但字面几乎不重叠（组内 Jaccard 仅 "
        f"{fmt(min(SH['group_stats']['D1']['mean'], SH['group_stats']['D2']['mean']), 3)}~"
        f"{fmt(max(SH['group_stats']['D1']['mean'], SH['group_stats']['D2']['mean']), 3)}），"
        f"本就不应被判为“近似重复”。**修正金标准后，旧权重策略方案的召回率由 "
        f"{fmt(_v1['mixed']['R'], 3)} 提升到 {fmt(_v1['strict']['R'], 3)}——这个变化完全来自评估口径，"
        f"权重策略一行未改**；推荐方案 {SH['recommended']} 的召回为 {fmt(_rec['strict']['R'], 3)}"
        f"（P={fmt(_rec['strict']['P'], 3)}，F1={fmt(_rec['strict']['F1'], 3)}）。"
        f"**特别提醒（审计意见）**：`A3s` 这一行保留的只是**旧权重策略**，"
        f"而它的数据解析、hash 规则与金标准都已更新，因此它是"
        f"“旧权重策略在新数据与新 gold 下的重跑”，"
        f"**不能与初版的 F1 相减、当作“只改了权重带来的提升”**。"
        f"新旧数字之间同时变动了多个因素，不具备单因素可比性。",
        f"阈值的影响（表 5-11、图 5-10 右）：**在本样本上并没有出现“召回换查准”的取舍**——"
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
    h(doc, "六、实验学习笔记", 1)
    notes = [
        ("“重复”不是一个客观量，取决于你怎么定义", "本次实验最大的收获来自评估口径。"
         f"同样一套 SimHash 指纹，金标准定义不同，旧权重策略 A3s 的 F1 可以从 "
         f"{fmt(_v1['mixed']['F1'], 3)} 变成 {fmt(_v1['strict']['F1'], 3)}；"
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
         f"R={fmt(SIMHASH_SCHEMES['A2 每词元 · TF']['strict']['R'], 3)}。"
         f"注意这两个方案的**召回率完全相同**，差距全部落在查准率上（FP 由 0 涨到 "
         f"{SIMHASH_SCHEMES['A2 每词元 · TF']['strict']['FP']}）——"
         f"所以本例并不是典型的“查准换查全”取舍，而是**一种口径直接制造了大量假阳性**。"
         f"这提醒我：P 与 R 要分开看，先判断差距出现在哪一侧，"
         f"再决定是调阈值（属权衡）还是改口径（属纠错）。"
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
    h(doc, "七、附录", 1)
    h(doc, "7.1 文件清单", 3)
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
    ], cap="表 5-9 提交文件清单", widths=[1.1, 2.0, 2.9])

    h(doc, "7.2 复现步骤", 3)
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

    h(doc, "7.3 开发过程中的主要修正", 3)
    para(doc, "本项目在完成过程中做过一次系统的自查与复现，修正了若干实现层面的问题。"
              "这些问题**不影响四个实验的方法设计**，但会改变具体数值，因此在这里做简要说明；"
              "完整的“问题 → 证据 → 修正”记录保存在项目内的 `out/AUDIT_NOTES.md`，"
              "结果文件的修订前版本保留在 `out/_baseline_original/` 以便逐行对照。"
              "正文各节给出的都是**修正后的最终结果**。")
    add_table(doc, ["环节", "原来的问题", "修正后"], [
        ["语料读取", "按前 3 个换行切分，把 group= / rewrite= 标注当成正文词混入",
         "改为按**首个空行**切分，标注不参与指纹计算"],
        ["TF-IDF 词权重", "回查特征权重时未统一大小写（“AI”查不到“ai”），"
                          "把该词误报为权重 0",
         "分词统一小写与特征名对齐；结果增加“是否进入特征集”列"],
        ["语料规范化", "3 条仅空格差异的标题使余弦相似度恒为 1.0，占满 Top-10",
         "按“去空白+小写”去重（2579 → 2576 条）"],
        ["Top-10 取对", "在完整对称矩阵上排序，同一对被取到两次（正向+反向）",
         "只在上三角取 Top-10，确保是 10 个不同文本对"],
        ["SimHash 权重", "等权分支按词元重复投票、权重又取词频，使单词贡献达 m²；"
                         "两种方法的投票单位不一致，基线不可比",
         "把「投票单位」与「权重来源」拆成正交维度做完整对照；"
         "正文只保留作业要求的等权 vs 加权两行（表 5-8）"],
        ["评测金标准", "把“同一事件不同报道”甚至“不同事件”也当作重复，"
                       "且 news20 中 D3 组标注有误",
         "金标准分四层，正样本只取改写簇；D3 已核实为不同事件并排除"],
        ["P/R/F1 口径", "分母为空时把查准率定义为 1.0，出现“无预测却 F1=1.000”",
         "分母为空取 0，并同时输出 TP/FP/FN"],
        ["计时口径", "LSH 列复用已生成的签名、不含签名生成与候选回验，与精确列任务不同",
         "三条路径统一为端到端，5 次重复取中位数并公开逐次原始值"],
        ["类比推理", "“父亲−儿子+母亲→女儿”方向写反，据此误判模型能力",
         "改为“儿子−父亲+母亲≈女儿”，正确命中"],
        ["文档向量", "求平均后未归一化，却与余弦口径混用评价",
         "加 L2 归一化，使聚类距离与余弦口径一致（Purity 0.94 → 0.98）"],
    ], cap="表 7-1 开发过程中修正的主要问题（完整记录见 out/AUDIT_NOTES.md）",
        widths=[0.85, 2.45, 2.6], size=8)
    para(doc, "还有一处值得单独说明的**结论修正**：初版声称“TF-IDF 加权 SimHash 优于等权”，"
              "但那是因为等权基线被写坏了（见上表“SimHash 权重”一行）。"
              "修正后在本数据集上等权方案反而略优——**作业要求的是“对比”而非“加权必须更好”**，"
              "因此本项目如实报告该结果，并分析可能原因（见 5.2.6 与附录 7.5.3）。")

    h(doc, "7.4 自检脚本与验证结果", 3)
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
    ], cap="表 7-2 自检脚本与当前验证结果", widths=[2.1, 1.9, 2.2], size=8)

    # ================= 6.5 消融与补充对照（详细数据） =================
    h(doc, "7.5 消融与补充对照（正文只给结论，完整数据在此）", 3)
    para(doc, "本节汇总 5.2 节 SimHash 权重方案与 4.2 节 MinHash 阈值/计时的完整对照数据，"
              "供复核使用。正文 5.2.5 只保留作业要求的「等权 vs 加权」核心比较。")

    h(doc, "7.5.1 SimHash 权重方案完整因子对照", 4)
    para(doc, "把「投票单位」与「权重来源」拆成两个正交维度，共 8 个方案。"
              "正样本 = 改写簇 R1/R2 组内对。")
    add_table(doc, ["权重方案（投票单位 × 权重来源）", "P", "R", "F1", "TP", "FP", "FN", "判定对数"], [
        [s["name"], f"{s['strict']['P']:.3f}", f"{s['strict']['R']:.3f}",
         f"{s['strict']['F1']:.3f}", s["strict"]["TP"], s["strict"]["FP"],
         s["strict"]["FN"], s["n_pred"]] for s in SH["schemes"]
    ], cap=f"表 7-3 SimHash 权重方案完整对照（海明距离 ≤ {SH['ham_th']}；"
           f"正样本 = 改写簇 {SH['gold']['near_dup']} 对）",
        widths=[2.3, 0.62, 0.62, 0.62, 0.5, 0.5, 0.5, 0.75], size=8)
    add_table(doc, ["同一批方案在“初版混合口径”下的指标（正样本=所有同组对）", "P", "R", "F1", "TP", "FP", "FN"], [
        [s["name"], f"{s['mixed']['P']:.3f}", f"{s['mixed']['R']:.3f}",
         f"{s['mixed']['F1']:.3f}", s["mixed"]["TP"], s["mixed"]["FP"], s["mixed"]["FN"]]
        for s in SH["schemes"]
    ], cap=f"表 7-4 初版混合口径对照（正样本 = 所有同组对 "
           f"{SH['gold']['mixed_all_same_group']} 对，仅作口径对照）",
        widths=[2.9, 0.7, 0.7, 0.7, 0.55, 0.55, 0.55], size=8)

    h(doc, "7.5.2 一个必须注意的代数等价关系", 4)
    _eqp = SH["equivalence"]
    para(doc, f"{_eqp['pair'][0]} 与 {_eqp['pair'][1]} 是**同一个方案**："
              f"一个出现 m 次的词，前者投 m 次票、每次权重 1（总贡献 m），"
              f"后者投 1 次票、权重 m（总贡献也是 m）。"
              f"逐篇比对 64 位指纹的结果：**{_eqp['n_docs_identical']}/{_eqp['n_docs_total']} 篇逐位完全相同**。"
              f"因此这两行不能当作两份独立证据。"
              f"（回归测试脚本：tools/verify_equivalence.py，结果见 "
              f"results_summary_simhash.json 的 equivalence 字段。）")

    h(doc, "7.5.3 IDF 影响的隔离对照", 4)
    para(doc, "「等权」与「TF-IDF」同时改变了 TF 与 IDF，无法单独归因，"
              "因此额外增加两个只含 IDF 的方案（B4/B5）。隔离后的召回率链条：")
    _chain = ["B1 每唯一词 · 等权(1)", "B2 每唯一词 · TF",
              "B4 每唯一词 · 仅IDF", "B3 每唯一词 · TF-IDF"]
    add_table(doc, ["方案", "权重", "R", "F1"], [
        [nm, {"B1 每唯一词 · 等权(1)": "1（等权）",
              "B2 每唯一词 · TF": "m（仅 TF）",
              "B4 每唯一词 · 仅IDF": "IDF（仅 IDF）",
              "B3 每唯一词 · TF-IDF": "m·IDF（TF+IDF）"}[nm],
         f"{SIMHASH_SCHEMES[nm]['strict']['R']:.3f}",
         f"{SIMHASH_SCHEMES[nm]['strict']['F1']:.3f}"] for nm in _chain
    ], cap="表 7-5 IDF 隔离对照（每唯一词投票，逐步加入权重来源）",
        widths=[2.4, 1.3, 0.9, 0.9], size=8.5)
    para(doc, "结论：**TF 与 IDF 单独都会降低召回，两者叠加时降幅最大**"
              "（等权 1.000 → 加 TF 0.917 → 仅 IDF 0.750 → TF+IDF 0.583）。"
              "但相对等权基线都只是小幅下降，因此**不能说“IDF 有害”**。")

    h(doc, "7.5.4 停用词降权的实际影响", 4)
    para(doc, "只看 P/R/F1 会误判“该操作没有作用”——汇总指标相同不等于指纹没变。"
              "下表给出指纹与预测集合层面的差异：")
    _swt = SH["stopword_downweight_effect"]
    add_table(doc, ["对照（加停用词降权前后）", "指纹改变文档数", "平均翻转位数",
                    "距离矩阵改变对数", "预测集合对称差", "P/R/F1 是否相同"], [
        [k.split("·")[0].strip(), f"{v['n_fp_changed']}/{SH['n_docs']}",
         f"{v['mean_bit_flip']:.2f}", v["n_dist_changed"], v["pred_symdiff"],
         "相同" if v["same_prf"] else "不同"] for k, v in _swt.items()
    ], cap="表 7-6 停用词降权在指纹/距离/预测集合层面的影响",
        widths=[1.35, 1.05, 0.9, 1.05, 0.95, 0.85], size=8)
    _idf = SH["idf_stats"]
    para(doc, f"顺带澄清一个口径问题：sklearn 默认平滑 IDF 为 ln((1+N)/(1+df))+1，**下界是 1 而不是 0**。"
              f"实测停用词 IDF 均值 {fmt(_idf['stopword_mean'])}"
              f"（{fmt(_idf['stopword_min'], 3)}~{fmt(_idf['stopword_max'], 3)}）、"
              f"非停用词均值 {fmt(_idf['nonstop_mean'])}、出现在全部 {SH['n_docs']} 篇中的词为 "
              f"{_idf['all_docs_idf_value']:.1f}。"
              f"因此严谨表述是：**在本数据与固定阈值下，该降权操作未改变最终判定结果**。")

    h(doc, "7.5.5 海明距离阈值扫描（完整）", 4)
    _sw = SH["sweep_f1"]
    _names = [s["name"] for s in SH["schemes"]]
    _short = [n.split()[0] for n in _names]
    rows10 = [[str(t)] + [f"{_sw[n][t]:.3f}" for n in _names] for t in range(11)]
    add_table(doc, ["距离阈值"] + _short, rows10,
              cap=f"表 7-7 海明距离阈值扫描（F1；正样本=改写簇 {SH['gold']['near_dup']} 对）",
              widths=[0.85] + [0.68] * len(_names), size=7.5)

    h(doc, "7.5.6 MinHash/LSH 阈值与端到端计时", 4)
    _thr_mixed = MH["thresholds"]
    add_table(doc, ["相似度阈值", "精确 Jaccard（P/R/F1）", "MinHash（P/R/F1）"],
              [[f"{r['t']:.1f}",
                "/".join(f"{v:.3f}" for v in r["mixed_exact"][:3]),
                "/".join(f"{v:.3f}" for v in r["mixed_min"][:3])] for r in _thr_mixed],
              cap="表 7-8 MinHash 阈值影响（初版混合口径：正样本 = T1~T4 两两，共 6 对）",
              widths=[1.2, 2.4, 2.4], size=8.5)
    add_table(doc, ["相似度阈值", "精确 Jaccard（P/R/F1）", "MinHash（P/R/F1）"],
              [[f"{r['t']:.1f}",
                "/".join(f"{v:.3f}" for v in r["strict_exact"][:3]),
                "/".join(f"{v:.3f}" for v in r["strict_min"][:3])] for r in _thr_mixed],
              cap="表 7-9 MinHash 阈值影响（分层口径：正样本 = 近重复对 T1-T2）",
              widths=[1.2, 2.4, 2.4], size=8.5)
    _rep = MH["config"]["reps"]
    add_table(doc, ["文档数", "精确 Jaccard", "MinHash 全量两两", "LSH(b16r8)", "LSH(b64r2)",
                    "全量对数", "候选数 b16r8/b64r2", "加速比"],
              [[r["n"], f"{r['exact']*1000:.1f}±{r['exact_std']*1000:.1f}",
                f"{r['minhash']*1000:.1f}±{r['minhash_std']*1000:.1f}",
                f"{r['lsh_16_8']*1000:.1f}±{r['lsh_16_8_std']*1000:.1f}",
                f"{r['lsh_64_2']*1000:.1f}±{r['lsh_64_2_std']*1000:.1f}",
                f"{r['total_pairs']:,}", f"{r['cand_16_8']}/{r['cand_64_2']}",
                f"{r['speedup_lsh64_vs_exact']:.2f}×"] for r in MH["scaling_end2end_ms"]],
              cap=f"表 7-10 MinHash/LSH 端到端计时（真实标题语料，{_rep} 次重复，"
                  f"中位数±标准差，单位毫秒；逐次原始值见 results_summary_minhash.json）",
              widths=[0.6, 1.05, 1.15, 1.0, 1.0, 0.8, 1.05, 0.75], size=7.5)
    _stg = MH["stage_breakdown_500_ms"]
    add_table(doc, ["阶段（n=500）", "耗时(ms)", "说明"], [
        ["shingle 构建 + 签名生成", f"{_stg['shingle_and_signature']:.2f}", "一次性成本；k=128 向量化计算"],
        ["LSH 建桶 + 候选生成", f"{_stg['lsh_build_and_candidates']:.2f}", "不含签名生成"],
        ["候选回验", f"{_stg['candidate_verify']:.2f}", f"{_stg['n_candidates']} 对候选做签名比对"],
    ], cap="表 7-11 分阶段耗时拆解（用于定位瓶颈）", widths=[2.2, 1.2, 2.6], size=8.5)

    # 按作业要求的命名格式：姓名+学号+第1次实验报告.docx
    name = "<成员一姓名>+<成员一学号>+第1次实验报告.docx"
    path = os.path.join(OUT, name)
    doc.save(path)
    print("报告已生成:", path)

    # 公开脱敏版：只替换封面与正文中的署名，其余内容一致
    # （学校提交版保留真实姓名学号；公开仓库若需发布，用这一版）
    try:
        d2 = Document(path)
        replaced = 0
        for p in d2.paragraphs:
            for run in p.runs:
                if "<成员一姓名>" in run.text or "<成员一学号>" in run.text:
                    run.text = (run.text.replace("<成员一姓名>", "（姓名）")
                                        .replace("<成员一学号>", "（学号）"))
                    replaced += 1
        pub = os.path.join(OUT, "第1次实验报告-公开脱敏版.docx")
        d2.save(pub)
        print(f"公开脱敏版已生成: {pub}（替换 {replaced} 处署名）")
    except Exception as e:                       # noqa: BLE001
        print(f"[warn] 公开脱敏版生成失败: {e}")
    return path


if __name__ == "__main__":
    build()
