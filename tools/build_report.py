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
    scale = re.search(r"语料规模: (\d+)", txt).group(1)
    shape = re.search(r"矩阵形状: (\([\d, ]+\))", txt).group(1)
    pairs = re.findall(r"\d+\. 相似度=([\d.]+)\n\s+A\[(\d+)\]: (.*?)\n\s+B\[(\d+)\]: (.*)", txt)
    words = re.findall(r"^(\S+)\t词频=(\d+)\t平均TF-IDF=([\d.]+)", txt, re.M)
    return scale, shape, pairs, words


def parse_minhash():
    txt = read("exp1_minhash_results.txt")
    sims = re.findall(r"T(\d+)-T(\d+): Jaccard=([\d.]+)\s+MinHash=([\d.]+)\s+LSH候选=(\S*)", txt)
    err = re.search(r"平均绝对误差: ([\d.]+)\s+最大: ([\d.]+)", txt)
    thr = re.findall(r"^ ([\d.]+) \| ([\d.]+)/([\d.]+)/([\d.]+) \| ([\d.]+)/([\d.]+)/([\d.]+)", txt, re.M)
    lsh = re.findall(r"^--- LSH\(b=(\d+), r=(\d+)\) 候选 (\d+) 对 ---", txt, re.M)
    lsh_items = re.findall(r"T(\d+)-T(\d+): MinHash 相似度=([\d.]+) -> (\S+)", txt)
    run = re.findall(r"文档数=\s*(\d+): 精确Jaccard=([\d.]+)ms\s+MinHash全对比=([\d.]+)ms\s+LSH建桶\+候选=([\d.]+)ms \(候选(\d+)对\)", txt)
    return sims, err, thr, lsh, lsh_items, run


def parse_wordvec():
    txt = read("exp2_wordvec_results.txt")
    model = re.search(r"模型信息: (.*)", txt).group(1)
    analogies = re.findall(r"^  (\S+)-(\S+)\+(\S+) 期望≈(\S+) \| 实际: (.*?)(★命中)?$", txt, re.M)
    pairs = re.findall(r"sim\((\S+), (\S+)\) = ([\d.]+)", txt)
    intra = re.search(r"类内平均相似度: ([\d.]+)\s+类间平均相似度: ([\d.]+)", txt)
    km = re.search(r"聚类纯度 Purity = ([\d.]+)\s+调整兰德指数 ARI = ([\d.]+)", txt)
    conf = re.findall(r"^    (体育|科技|娱乐): \[([\d, ]+)\]", txt, re.M)
    return model, analogies, pairs, intra, km, conf


def parse_simhash():
    txt = read("exp2_simhash_results.txt")
    head = re.search(r"数据集: (\d+) 篇新闻.*Ground truth重复对=(\d+)", txt)
    res = {m[0]: m[1:] for m in re.findall(r"^(\S+?) SimHash: P=([\d.]+) R=([\d.]+) F1=([\d.]+)", txt, re.M)}
    sweep = re.findall(r"阈值=\s*(\d+): TF-IDF加权 P=([\d.]+) R=([\d.]+) F1=([\d.]+) \| 等权 P=([\d.]+) R=([\d.]+) F1=([\d.]+)", txt)
    hits = re.findall(r"^  (\d+)-(\d+) \[(\S+?)vs(\S+?)\] (.*?) <-> (.*?) (★命中|误报)$", txt, re.M)
    return head, res, sweep, hits


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
                 "姓名：＿＿＿＿＿＿    学号：＿＿＿＿＿＿＿＿",
                 "日期：＿＿＿＿年＿＿月＿＿日"]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run(p.add_run(line), size=12)
    doc.add_page_break()

    # ===== 一、实验环境 =====
    h(doc, "一、实验环境与依赖", 1)
    add_table(doc, ["项目", "说明"], [
        ["操作系统", "Windows"],
        ["开发语言", "Python 3.8"],
        ["中文分词", "jieba"],
        ["机器学习/特征", "scikit-learn（TfidfVectorizer、cosine_similarity、PCA、TSNE、KMeans）"],
        ["词向量", "gensim（KeyedVectors）"],
        ["数值/绘图", "numpy、matplotlib（Microsoft YaHei 中文字体）"],
        ["网页抓取", "urllib / requests + BeautifulSoup(lxml)"],
        ["文档与截图", "python-docx、Pillow"],
        ["预训练词向量模型", "腾讯 AI Lab 中文词向量（800 万词轻量版），143613 词 × 200 维"],
    ], cap="表 1-1 实验环境与依赖", widths=[1.6, 4.4])
    para(doc, "说明：预训练模型体积较大（116 MB），按作业要求不随代码压缩包提交；"
              "运行 exp2_wordvec.py 前需将模型文件放到 model/ 目录（见附录复现步骤）。")

    # ===== 二、实验材料获取 =====
    h(doc, "二、实验材料获取（真实语料抓取）", 1)
    para(doc, "本次实验的全部语料均来自互联网真实新闻站点实时抓取，未使用任何现成的标注数据集，抓取脚本见 "
              "scripts/crawler/ 目录。抓取流程与数据规模如下表。")
    add_table(doc, ["数据文件", "规模", "获取方式", "用途"], [
        ["data/titles.txt", "2579 条", "网易滚动新闻接口（GBK JSON）+ 新浪滚动新闻 API，多频道聚合",
         "实验一(1) TF-IDF 语料（要求≥500 条）"],
        ["data/sports/*.txt\ndata/tech/*.txt\ndata/ent/*.txt", "各 50 篇\n（共 150 篇）",
         "上述接口取标题/链接后，逐篇抓取正文并用 BeautifulSoup 解析（h1 标题 + 正文容器）",
         "实验二(1) 三类主题文档向量"],
        ["data/news20/*.txt\n+ manifest.json", "20 篇",
         "真实新闻为源文：同一事件的多家媒体报道（不同标题/改写）+ 转载改写 + 完全不同主题；"
         "改写簇由同义词替换、换标题、调段序规则化生成，并写入 group/rewrite 标注",
         "实验二(2) 加权 SimHash 相似度"],
        ["data/short_texts.txt", "6 条", "人工设计：完全重复 / 轻度修改 / 中度改写 / 完全不相关四类",
         "实验一(2) MinHash+LSH 去重"],
    ], cap="表 2-1 实验材料获取一览", widths=[1.5, 0.9, 3.0, 1.3])
    para(doc, "每条新闻全文均保存为统一格式：首行 title=、第二行 source=（原始 URL）、第三行 category=，"
              "空行后为正文，便于溯源与复核。")

    # ===== 三、实验题目一 =====
    h(doc, "三、实验题目一：文本特征表示与短文本去重", 1)

    # ---------- 3.1 TF-IDF ----------
    scale, shape, pairs, words = parse_tfidf()
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
              f"③ 计算余弦相似度后先把对角线置为 -1，避免文档与自身（相似度 1.0）占据 Top-10；"
              f"④ 用 np.argsort(...) 展平排序取前 10，再 divmod 还原 (i, j) 下标。")

    h(doc, "3.1.4 实验结果", 3)
    para(doc, f"语料规模：{scale} 条中文新闻标题（满足 ≥500 条要求）；TF-IDF 矩阵形状：{shape}。")
    rows = [[i + 1, f"{float(s):.4f}", f"[{a}] {ta[:38]}", f"[{b}] {tb[:38]}"]
            for i, (s, a, ta, b, tb) in enumerate(pairs)]
    add_table(doc, ["排名", "余弦相似度", "文本 A", "文本 B"], rows,
              cap="表 3-1 相似度最高的 Top-10 文本对", widths=[0.5, 0.9, 2.4, 2.4])
    rows2 = [[w, fq, wx] for w, fq, wx in words]
    add_table(doc, ["词", "词频", "平均 TF-IDF 权重"], rows2,
              cap="表 3-2 词频最高的 20 个词及其平均 TF-IDF 权重", widths=[1.6, 1.4, 2.4])
    add_image(doc, os.path.join(FIG, "exp1_tfidf_top20.png"),
              "图 3-2 词频最高的 20 个词的 TF-IDF 权重柱状图")

    h(doc, "3.1.5 结果分析", 3)
    for s in [
        "Top-10 中出现了多组相似度=1.0000 的文本对，观察其内容可归为三类："
        "① 同一标题的排版差异（如“腾势 D9”与“腾势D9”、“能力 很难说”与“能力，很难说”），"
        "分词后词序列完全一致，故相似度为 1；"
        "② 模板化新闻（彩票预测、足彩指数），仅期号或人名不同，如“109期张世奇”与“109期林必立”，"
        "主体词完全一致；③ 同一模板的跨期文本，如“福彩3D第2026253”与“第2026252”。"
        "这说明 TF-IDF + 余弦相似度对“模板化/机器生成”文本极为敏感，可用于识别批量生产的低质内容。",
        "但需注意：相似度=1.0 并不等于语义完全相同。像“三花智控获增持”与“信义玻璃获增持”，"
        "两者股票名称与数字不同，却因 max_features=1000 截断 + 二元组未覆盖全部数字组合而得到 1.0，"
        "属于典型的“高频模板掩盖低频关键信息”现象，这也是纯词袋模型的固有局限。",
        "从表 3-2 看，词频与 TF-IDF 权重并非正相关：高频词“预测（121 次）”“奖号（119 次）”的权重只有 0.27 左右，"
        "因为它们在大量文档中共同出现，IDF 很低；而“电影”词频仅 40 次，权重却高达 0.4614，"
        "“人（0.4331）”“俄（0.4142）”“特朗普（0.4043）”同理——它们集中于少数文档，区分度强。"
        "这与 TF-IDF 的设计初衷完全吻合。",
        "特例：词“AI”词频 84 次但平均权重为 0.0000。原因是语料中该词多以“AI”原形出现，"
        "而 TfidfVectorizer 配置了 max_features=1000，按词频截断了特征；同时其大小写/中英混排形式不统一，"
        "落入被截断特征中，故未在矩阵中保留。这提示实际工程中应统一大小写并适当放宽 max_features。",
    ]:
        para(doc, s)

    # ---------- 3.2 MinHash + LSH ----------
    sims, err, thr, lsh, lsh_items, run = parse_minhash()
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
    para(doc, "共设计 6 条短文本用例，覆盖完全重复、轻度修改、中度改写、完全不相关四类；"
              "其中 T1~T4 描述同一事件（亚运首金），两两组合构成本实验的 ground truth 重复对（共 6 对）：")
    add_table(doc, ["编号", "文本", "类别"], [
        ["T1", "中国代表团在亚运会收获首金，女子现代五项团体成功卫冕", "原始文本"],
        ["T2", "中国代表团在亚运会收获首金，女子现代五项团体成功卫冕", "完全重复（与 T1 逐字相同）"],
        ["T3", "中国代表团亚运首金到手，女子现代五项团队成功卫冕", "轻度修改（删词/换词）"],
        ["T4", "卫冕成功！现代五项女子团体为中国队拿下本届亚运会第一枚金牌", "中度改写（换句序/同义替换）"],
        ["T5", "马斯克否认特斯拉向xAI投资五十亿美元参股计划", "完全不相关（同领域不同事件）"],
        ["T6", "佟丽娅公开回应与陈思诚的离婚传闻，称两人早已分开", "完全不相关（不同领域）"],
    ], cap="表 3-3 MinHash+LSH 实验的 6 个测试用例", widths=[0.6, 4.2, 1.6])

    h(doc, "3.2.4 关键代码解读", 3)
    add_image(doc, os.path.join(SHOT, "exp1_minhash_update.png"),
              "图 3-3 MinHash 签名生成（k=128，exp1_minhash.py）")
    para(doc, "代码要点：签名初始化为一维 k 长数组（初值 P）；对集合中每个 shingle 计算其 64 位整数哈希后，"
              "逐个哈希函数取最小值。实现上刻意使用纯 Python 大整数运算而非 numpy 向量化："
              "因为 a_i·x 的量级接近 2¹²²，超出 numpy int64 的范围会造成溢出，属于典型的“数学正确但工程踩坑”问题。")
    add_image(doc, os.path.join(SHOT, "exp1_lsh.png"),
              "图 3-4 LSH 分桶与候选对生成（build_lsh_tables / lsh_candidates）")
    para(doc, "代码要点：把签名按 band 切片并作为 dict 的 key 建立倒排桶；同一桶内文档两两组合即为候选对，"
              "用 set 去重。整个过程只需一次线性扫描，避免了全量两两比较。")

    h(doc, "3.2.5 实验结果", 3)
    rows3 = [[f"T{i}-T{j}", jac, mh, ("是" if mark else "否")] for i, j, jac, mh, mark in sims]
    add_table(doc, ["文本对", "精确 Jaccard", "MinHash 估计", "进入 LSH 候选"], rows3,
              cap="表 3-4 各文本对的精确 Jaccard 与 MinHash 估计对比", widths=[1.4, 1.6, 1.6, 1.6])
    para(doc, f"MinHash 估计的平均绝对误差为 {err.group(1)}，最大误差 {err.group(2)}，"
              f"说明 k=128 的签名已能高精度逼近真实 Jaccard（签名长度越长误差越小，误差量级约为 1/√k）。")

    rows4 = [[f"{t}", f"{p1}/{r1}/{f1}", f"{p2}/{r2}/{f2}"] for t, p1, r1, f1, p2, r2, f2 in thr]
    add_table(doc, ["相似度阈值", "精确 Jaccard（P/R/F1）", "MinHash（P/R/F1）"], rows4,
              cap="表 3-5 不同阈值对去重结果的影响（ground truth：T1~T4 两两重复）", widths=[1.4, 2.3, 2.3])

    lsh_rows = []
    for bi, ri, cnt in lsh:
        lsh_rows.append([f"b={bi}, r={ri}", cnt, "—"])
    add_table(doc, ["LSH 配置", "候选对数", "说明"], lsh_rows,
              cap="表 3-6 两种 LSH 分桶参数下的候选对数量", widths=[1.6, 1.4, 3.0])
    rows5 = [[f"T{i}-T{j}", mh, st] for i, j, mh, st in lsh_items]
    add_table(doc, ["候选文本对（b=64, r=2）", "MinHash 相似度", "回验结论"], rows5,
              cap="表 3-7 LSH 候选对的相似度回验", widths=[1.6, 1.6, 1.6])

    rows6 = [[m, ej, mj, lj, f"{cj} 对"] for m, ej, mj, lj, cj in run]
    add_table(doc, ["文档数", "精确 Jaccard", "MinHash 全量对比", "LSH 建桶+候选", "LSH 候选数"], rows6,
              cap="表 3-8 批量规模对运行时间的影响（毫秒）", widths=[1.0, 1.4, 1.6, 1.5, 1.2])
    add_image(doc, os.path.join(FIG, "exp1_minhash_sim.png"),
              "图 3-5 MinHash 估计 vs 精确 Jaccard（左）与不同阈值下的 F1（右）")
    add_image(doc, os.path.join(FIG, "exp1_minhash_scaling.png"),
              "图 3-6 批量规模对计算耗时的影响（对数纵轴）")

    h(doc, "3.2.6 结果分析", 3)
    for s in [
        "MinHash 估计精度：T1-T2（完全重复）估计值 1.0000 与精确值一致；"
        "T1-T3（轻度修改）精确 0.3077 vs 估计 0.3203，T1-T4（中度改写）精确 0.1875 vs 估计 0.1641；"
        "完全不相关的 T5、T6 与其余文本精确值与估计值均为 0.0000。"
        f"整体平均绝对误差仅 {err.group(1)}，验证了 MinHash 作为 Jaccard 无偏估计的有效性。",
        "阈值影响（表 3-5）：阈值取 0.1 时精确与近似方法都达到 P=R=F1=1.000 的最优效果——"
        "因为此时只有 T1~T4 之间的 6 对相似度超过 0.1，而 T1~T4 与 T5/T6 的相似度恰好为 0，"
        "两类样本之间存在天然的“间隔带”。阈值提高到 0.2 后，中度改写的 T1-T4（0.1875）、T3-T4（0.1176）被漏判，"
        "查全率降到 0.5；阈值≥0.4 时只剩完全重复与轻改可被召回，查全率降至 0.167。"
        "结论：阈值必须在“漏判改写”与“误判不同事件”之间折中，本组数据的最佳阈值是 0.1~0.15。",
        "近似 vs 精确：MinHash 在阈值 0.1 处的 F1 为 0.909，略低于精确 Jaccard 的 1.000，"
        "差异来自 T3-T4 的估计值 0.0938 被压到阈值以下（精确值 0.1176 高于阈值）。"
        "这正是近似算法“用少量精度换取大量效率”的本质——误差可控且可解释。",
        "LSH 分桶参数的取舍（表 3-6、3-7）：(b=16, r=8) 只产生了 1 对候选，漏掉了中度改写的相似对（漏判）；"
        "(b=64, r=2) 产生 6 对候选，覆盖了全部真实相似对，但引入了 3 对低相似度候选（误报），"
        "需要用相似度阈值回验剔除。这说明提高 band 数（减小 r）可提升召回，代价是候选集膨胀。",
        "运行时间（表 3-8、图 3-6）：精确 Jaccard 的时间随文档数呈平方增长（O(n²·|S|)），"
        "500 篇时已达 91.87 ms；MinHash 全量对比虽把集合运算换成签名比较，但比较次数仍是 O(n²)，"
        "500 篇耗时 713.32 ms（单次比较更快，但签名计算本身有开销）；"
        "而 LSH 建桶+候选生成只需一次线性扫描，500 篇仅 30.52 ms，且候选对只有 27640 对。"
        "文档规模越大，LSH 的优势越明显——这正是搜索引擎与去重系统工业界普遍采用 LSH 的原因。",
    ]:
        para(doc, s)

    # ===== 四、实验题目二 =====
    h(doc, "四、实验题目二：文本相似度计算", 1)

    # ---------- 4.1 词向量 ----------
    model, anas, wpairs, intra, km, conf = parse_wordvec()
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
    add_image(doc, os.path.join(SHOT, "exp2_docvector.png"),
              "图 4-2 词向量平均池化生成文档向量（doc_vector）")
    para(doc, "代码要点：只累加词表中存在的词向量（OOV 词直接跳过），若一篇文档所有词都不在词表则返回 None 并丢弃，"
              "避免产生零向量污染聚类与可视化。")
    add_image(doc, os.path.join(SHOT, "exp2_kmeans.png"),
              "图 4-3 KMeans 文本聚类与 Purity/ARI 评估（白底代码截图）")

    h(doc, "4.1.5 实验结果", 3)
    para(doc, f"模型信息：{model}。")
    rows7 = [[f"{a}−{b}+{c}", f"≈{e}", top + (" ★" if hit else "")] for a, b, c, e, top, hit in anas]
    add_table(doc, ["向量运算", "期望词", "实际 Top-3（含余弦相似度）"], rows7,
              cap="表 4-1 词向量类比推理结果", widths=[1.6, 1.0, 3.4])
    rows8 = [[f"sim({w1}, {w2})", s] for w1, w2, s in wpairs]
    add_table(doc, ["词对", "余弦相似度"], rows8,
              cap="表 4-2 12 组词对的余弦相似度", widths=[2.4, 2.4])
    add_table(doc, ["指标", "数值"], [
        ["类内平均相似度（同主题文档两两）", intra.group(1)],
        ["类间平均相似度（跨主题文档两两）", intra.group(2)],
        ["KMeans 聚类纯度 Purity", km.group(1)],
        ["调整兰德指数 ARI", km.group(2)],
    ], cap="表 4-3 文档向量的主题可分性与聚类效果", widths=[3.4, 1.6])
    rows9 = [[n, c] for n, c in conf]
    add_table(doc, ["真实主题", "三个聚类簇中的样本数"], rows9,
              cap="表 4-4 KMeans 混淆矩阵（行=真实主题，列=聚类簇）", widths=[1.6, 3.4])
    add_image(doc, os.path.join(FIG, "exp2_wordvec_pca_tsne.png"),
              "图 4-4 文档向量 PCA / t-SNE 降维可视化与 KMeans 聚类结果")

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
        "从混淆矩阵看，科技类（50/50 全对）与娱乐类（50/50 全对）被两个簇完美分开，"
        "而体育类有 41 篇被分到娱乐簇——原因是体育新闻中常夹杂大量人物故事、赛事花絮，"
        "用词与娱乐题材高度重叠，这也解释了为何类间相似度（0.7993）整体偏高。",
        "PCA 与 t-SNE 的对比（图 4-4）：PCA 平面上三类文档呈三条水平带状分布、彼此重叠较多，"
        "反映的是全局方差结构；t-SNE 平面上三类形成较为分离的团簇，局部结构更清晰。"
        "这是二者的典型差异——PCA 保留全局距离、t-SNE 强调局部近邻，实际分析中常两者并用。",
    ]:
        para(doc, s)

    # ---------- 4.2 加权 SimHash ----------
    head, res, sweep, hits = parse_simhash()
    ndoc, ngold = head.group(1), head.group(2)
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
              f"数据集以真实新闻为源文，同组文档视为近似重复，共构成 {ngold} 对 ground truth 重复对。")
    add_table(doc, ["分组", "文档数", "类型", "说明"], [
        ["R1", "4", "同一事件不同报道", "扎克伯格访谈/中美 AI 竞争（不同媒体标题与行文）"],
        ["R2", "4", "同一事件不同报道", "国米 vs 罗马赛后评论（含转载改写）"],
        ["D1", "3", "同一事件不同报道", "佟丽娅陈思诚相关报道"],
        ["D2", "3", "转载改写", "萨拉赫相关报道"],
        ["D3", "3", "转载改写", "亚运首金相关报道"],
        ["U1~U3", "3", "完全不同主题", "百川智能融资 / CrowdStrike 故障等，互不相关"],
    ], cap="表 4-5 20 篇新闻数据集的分组设计", widths=[0.9, 0.8, 1.5, 2.8])

    h(doc, "4.2.4 关键代码解读", 3)
    add_image(doc, os.path.join(SHOT, "exp2_simhash_fp.png"),
              "图 4-5 64 位加权 SimHash 指纹与海明距离（白底代码截图）")
    para(doc, "代码要点：v 用 float64 以容纳可变的权重；内层循环按位（bit）累加 ±w；"
              "指纹用 Python 大整数按位或拼装，海明距离用 bin(a^b).count('1') 计算，简洁且无溢出风险。")
    add_image(doc, os.path.join(SHOT, "exp2_simhash_main.png"),
              "图 4-6 TF-IDF 加权 SimHash 实验主体（权重构造与停用词降权）")
    para(doc, "代码要点：① 在 20 篇文档上训练 TfidfVectorizer，得到每篇文档每个词的 TF-IDF 权重矩阵 X；"
              "② 遍历文档词序列，从 X 中取出该词的权重作为 w；③ 若该词命中停用词表则 w *= 0.2 实现降权。"
              "注意此处分词函数刻意保留停用词（只过滤纯标点/数字），否则“停用词降权”这条分支永远不会被触发——"
              "这是本实验调试中踩过的一个逻辑坑。")

    h(doc, "4.2.5 实验结果", 3)
    w_p, w_r, w_f = res["TF-IDF加权"]
    e_p, e_r, e_f = res["等权(词频)"]
    add_table(doc, ["方法", "查准率 P", "查全率 R", "F1"], [
        ["TF-IDF 加权 SimHash", w_p, w_r, w_f],
        ["等权（词频）SimHash", e_p, e_r, e_f],
    ], cap="表 4-6 两种 SimHash 的去重效果对比（海明距离 ≤ 3）", widths=[2.2, 1.4, 1.4, 1.2])
    para(doc, f"说明：数据集 {ndoc} 篇，ground truth 重复对 {ngold} 对。"
              f"TF-IDF 加权方案 P={w_p}、R={w_r}、F1={w_f}；等权方案 P={e_p}、R={e_r}、F1={e_f}。"
              f"加权方案的 F1 是等权方案的 {float(w_f)/float(e_f):.1f} 倍，改进显著。")

    rows10 = [[f"{t}", f"{p1}/{r1}/{f1}", f"{p2}/{r2}/{f2}"] for t, p1, r1, f1, p2, r2, f2 in sweep]
    add_table(doc, ["海明距离阈值", "TF-IDF 加权（P/R/F1）", "等权（P/R/F1）"], rows10,
              cap="表 4-7 海明距离阈值扫描（P/R/F1）", widths=[1.4, 2.3, 2.3])
    add_image(doc, os.path.join(FIG, "exp2_simhash_prf.png"),
              "图 4-7 等权 vs TF-IDF 加权 SimHash 效果对比（左）与阈值对 F1 的影响（右）")

    h(doc, "4.2.6 结果分析", 3)
    for s in [
        f"加权 SimHash 的查准率达到 {w_p}，即检出的每一对都是真正的重复事件；"
        "而等权 SimHash 查准率仅 0.192，检出的 84 对里有 68 对是误报。"
        "查看明细可见，等权方案把“扎克伯格访谈”（R1）与国米罗马评论（R2）、佟丽娅报道（D1）、"
        "甚至百川智能融资（U1）都判成了重复——根源正在于停用词与通用词在等权累加中主导了指纹，"
        "使不同主题的文档指纹趋于“均值化”，海明距离被人为压小。",
        "加权 SimHash 也有代价：查全率 0.476 低于等权的 0.714。原因有两方面："
        "① 同组中“完全不同主题”的 U1~U3 各仅 1 篇，本不构成重复对，不影响召回；"
        "② 真正漏判的是改写幅度较大的转载改写簇（如 D2/D3）：同义替换后高权重关键词被换掉，"
        "指纹跳变超过 3 位。这说明“只靠词形匹配”的 SimHash 对深度改写天然不敏感。",
        "阈值的影响（表 4-7、图 4-7 右）：加权方案的 P 在阈值 0~10 全程保持 1.000，"
        "说明其误报几乎为零，放宽阈值只增加召回、不引入噪声；"
        "F1 随阈值单调上升到 10 时达到 0.765。而等权方案的 F1 在阈值 0~4 区间几乎不动（0.303~0.345），"
        "因为其误报是“系统性”的而非“边界性”的——误报对的海明距离本就很小，提高阈值无法区分。"
        "这从另一角度印证了加权策略的有效性。",
        "工程启示：作业规定的 d ≤ 3 是一个偏保守的经典取值（对 64 位指纹而言）。"
        "本数据集上若把阈值放宽到 6~8，加权方案的 F1 可从 0.645 提升到 0.765 且不损失查准率。"
        "但阈值必须结合业务权衡：查重场景怕误伤（重准确率，取小阈值），"
        "内容聚合/爬虫去重场景怕漏抓（重查全率，可放宽阈值）。",
    ]:
        para(doc, s)

    # ===== 五、学习笔记 =====
    h(doc, "五、实验学习笔记", 1)
    notes = [
        ("关于“相似”的三种层次", "本实验串联起了三条技术路线：TF-IDF+余弦（词袋、只看词是否共现）、"
                              "MinHash+LSH（集合重叠、看 shingle 重合比例）、加权 SimHash（看指纹位差异）。"
                              "三者都基于“词形/词面”特征，共同的天花板是没有语义理解——"
                              "“特斯拉大跌”与“特斯拉股价重挫”字面无交集却语义相同，"
                              "只有词向量/预训练模型才能跨越。这也解释了为什么实验二(1) 要引入词向量。"),
        ("精确 vs 近似的权衡思维", "MinHash 用 128 维签名替代原始集合，LSH 用分桶替代全量比较，"
                            "两者都是“用可控的精度损失换数量级的效率提升”。"
                            "从表 3-8 看，500 篇文档时精确方法 91.87 ms、LSH 仅 30.52 ms，"
                            "而误差只有 0.0064——这种“工程上可接受的近似”是工业界处理海量文本的基本思路。"),
        ("工程实现里的“隐形陷阱”", "本次实验踩过几个很有代表性的坑："
                            "① numpy int64 溢出——MinHash 中 a_i·x 接近 2¹²²，向量化后静默溢出，"
                            "改用纯 Python 大整数才正确；"
                            "② 类比推理正负样本方向写反，结果看似合理（返回“是男人”）却完全错误；"
                            "③ 停用词降权分支失效——分词时已把停用词过滤掉，降权代码成了死代码，"
                            "表现为“加权与等权结果完全相同”；"
                            "④ 数据设计决定结论——最初用纯真实新闻做 SimHash，因改写幅度过大导致召回为 0，"
                            "无法区分两种方法，重新设计“真实源文+规则化改写”后才暴露出差距。"
                            "这四点说明：算法原理正确 ≠ 实验结果可信，必须校验中间量和数据分布。"),
        ("数据集设计的“控制变量”意识", "SimHash 实验中，如果 20 篇都是完全无关的新闻，"
                              "两种方法都会得到 P=R=F1=0（无差异）；如果都是原文照抄，两者都会满分。"
                              "只有构造出“同一事件的不同改写强度”这一连续谱，才能让评价指标真正具有区分力。"
                              "这是评估算法时的关键方法论。"),
        ("P/R/F1 的取舍", "查准率与查全率往往此消彼长。加权 SimHash 真实实验的结果是 P=1.000/R=0.476，"
                     "等权是 P=0.192/R=0.714——前者“宁可漏判不误判”，后者“宁可误判不漏判”。"
                     "单看某一个指标容易得出片面结论，F1 才能综合反映效果。"),
        ("词向量的可解释性与局限", "t-SNE 图上三类文档聚成清晰团簇、KMeans 纯度 0.94，"
                          "很有说服力地展示了“词向量的平均能代表文档语义”。"
                          "但同时 sim(苹果, 香蕉) > sim(苹果, 手机) 暴露了静态词向量无法处理一词多义的硬伤，"
                          "也让我理解了从 Word2Vec 到 BERT 的演进动机。"),
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
        ["语料", "data/titles.txt", "2579 条新闻标题"],
        ["语料", "data/{sports,tech,ent}/", "三类主题各 50 篇全文"],
        ["语料", "data/news20/ + manifest.json", "20 篇相似度实验新闻（含分组标注）"],
        ["语料", "data/short_texts.txt", "6 条去重测试用例"],
        ["结果", "out/*_results.txt", "四个实验的控制台结果落盘"],
        ["图片", "out/figures/*.png", "5 张可视化图"],
        ["图片", "out/screenshots/*.png", "8 张关键代码白底截图"],
        ["抓取脚本", "scripts/crawler/", "新闻抓取与数据集构造脚本"],
    ], cap="表 6-1 提交文件清单", widths=[1.1, 2.0, 2.9])

    h(doc, "6.2 复现步骤", 3)
    for i, s in enumerate([
        "安装依赖：pip install -r requirements.txt",
        "下载腾讯 AI Lab 中文词向量（Light 版），重命名为 light_Tencent_AILab_ChineseEmbedding.bin 并放入 model/ 目录；",
        "依次运行：python exp1_tfidf.py → python exp1_minhash.py → python exp2_wordvec.py → python exp2_simhash.py；",
        "结果文本输出到 out/*_results.txt，图像输出到 out/figures/；",
        "如需重新抓取语料，运行 scripts/crawler/ 下的脚本（需联网）。",
    ], 1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Pt(28)
        p.paragraph_format.space_after = Pt(2)
        set_run(p.add_run(f"（{i}）{s}"), size=10.5)

    name = "姓名+学号+第1次实验报告.docx"
    path = os.path.join(OUT, name)
    doc.save(path)
    print("报告已生成:", path)
    return path


if __name__ == "__main__":
    build()
