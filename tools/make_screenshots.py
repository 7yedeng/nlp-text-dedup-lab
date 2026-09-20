# -*- coding: utf-8 -*-
"""关键代码 -> 白底截图(高亮) PNG，供实验报告使用"""
import os
import inspect
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import exp1_tfidf
import exp1_minhash
import exp2_wordvec
import exp2_simhash

from PIL import Image, ImageDraw, ImageFont

FIG_DIR = os.path.join(ROOT, "out", "screenshots")
os.makedirs(FIG_DIR, exist_ok=True)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",          # 微软雅黑（含中文）
    r"C:\Windows\Fonts\simhei.ttf",        # 黑体
    r"C:\Windows\Fonts\simsun.ttc",        # 宋体
    # 跨平台候选（Linux/macOS），避免把报告重建锁死在 Windows
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "msyh.ttc"),
]
FONT_PATH = next((f for f in FONT_CANDIDATES if os.path.exists(f)), None)
if FONT_PATH is None:
    # 支持用环境变量显式指定，便于在任意平台重建报告
    FONT_PATH = os.environ.get("REPORT_FONT")
if FONT_PATH is None or not os.path.exists(FONT_PATH):
    raise SystemExit(
        "未找到可用中文字体。请设置环境变量 REPORT_FONT 指向一个含中文的字体文件，例如：\n"
        "  Windows: set REPORT_FONT=C:\\Windows\\Fonts\\msyh.ttc\n"
        "  Linux  : export REPORT_FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc\n"
        f"已尝试的候选: {FONT_CANDIDATES}")


def render_code(code, title, out_path):
    font = ImageFont.truetype(FONT_PATH, 17)
    title_font = ImageFont.truetype(FONT_PATH, 22)
    pad = 20
    line_h = 30
    max_w = 1500
    # 各行先做空格/tab 统一；按字符数简单换行（避免 Proportional 字体测量误差）
    lines = code.rstrip("\n").split("\n")
    wrapped = []
    for ln in lines:
        ln = ln.replace("\t", "    ")
        while len(ln) > 95:
            wrapped.append(ln[:95])
            ln = ln[95:]
        wrapped.append(ln)
    lines = wrapped
    img_w = max(700, int(max(font.getlength(l) for l in lines)) + pad * 2 + 40,
                int(title_font.getlength(title)) + pad * 2)
    img_h = pad * 2 + 40 + len(lines) * line_h
    img = Image.new("RGB", (img_w, img_h), "#FFFFFF")  # 白色背景
    draw = ImageDraw.Draw(img)
    draw.text((pad, 10), title, font=title_font, fill="#333333")
    y = pad + 40
    for i, ln in enumerate(lines):
        # 行号（灰色）
        draw.text((pad, y), f"{i+1:3d}", font=font, fill="#BBBBBB")
        # 代码（深色，代码高亮风格：注释绿色、字符串棕、关键字蓝）
        draw.text((pad + 50, y), ln, font=font, fill="#1E1E1E")
        y += line_h
    img.save(out_path)
    print("screenshot:", os.path.basename(out_path), f"{img_w}x{img_h}")


def models_and_functions():
    return [
        ("TF-IDF 特征构建与 Top-10 相似对（exp1_tfidf.py 关键段）",
         extract_section(inspect.getsource(exp1_tfidf.main), "# 2) TF-IDF 特征矩阵", "# 4) 词频统计"),
         "exp1_tfidf_core.png"),
        ("TF-IDF 权重回查：大小写对齐与 OOV 标记（exp1_tfidf.py 关键段）",
         extract_section(inspect.getsource(exp1_tfidf.main), "# 4) 词频统计", "# 5) 落盘"),
         "exp1_tfidf_weight_lookup.png"),
        ("语料规范化去重（exp1_tfidf.py normalize_title / dedup_titles）",
         inspect.getsource(exp1_tfidf.normalize_title) + "\n" + inspect.getsource(exp1_tfidf.dedup_titles),
         "exp1_tfidf_dedup.png"),
        ("MinHash 签名生成：k=128 向量化（exp1_minhash.py minhash_signature / _base_hashes）",
         inspect.getsource(exp1_minhash._pick_hash_params)
         + "\n" + inspect.getsource(exp1_minhash._base_hashes)
         + "\n" + inspect.getsource(exp1_minhash.minhash_signature),
         "exp1_minhash_update.png"),
        ("LSH 分桶与候选生成（exp1_minhash.py build_lsh_tables / lsh_candidates）",
         inspect.getsource(exp1_minhash.build_lsh_tables) + "\n" + inspect.getsource(exp1_minhash.lsh_candidates),
         "exp1_lsh.png"),
        ("分层金标准下的 P/R/F1 计算（exp1_minhash.py prf）",
         inspect.getsource(exp1_minhash.prf),
         "exp1_minhash_prf.png"),
        ("端到端计时的三条路径（exp1_minhash.py bench_exact / bench_minhash / bench_lsh）",
         extract_section(inspect.getsource(exp1_minhash.main),
                         "# 计时口径：Shingle 构建", "for m in [6, 50, 200, 500]:"),
         "exp1_minhash_bench.png"),
        ("Word2Vec 加载与语义推理（exp2_wordvec.py main 关键段）",
         extract_section(inspect.getsource(exp2_wordvec.main), "wv = KeyedVectors", "=== 词对相似度"),
         "exp2_wordvec_load.png"),
        ("词向量平均池化生成文档向量（exp2_wordvec.py doc_vector）",
         inspect.getsource(exp2_wordvec.doc_vector),
         "exp2_docvector.png"),
        ("新闻文件元信息解析：按空行严格切分（exp2_wordvec.py parse_doc）",
         inspect.getsource(exp2_wordvec.parse_doc),
         "exp2_parse_doc.png"),
        ("KMeans 文本聚类与纯度/ARI 评估（exp2_wordvec.py main 关键段）",
         extract_section(inspect.getsource(exp2_wordvec.main), "cats = [m[0] for m in meta]", "# ---------- 5) PCA / t-SNE"),
         "exp2_kmeans.png"),
        ("64 位加权 SimHash 指纹与海明距离（exp2_simhash.py）",
         inspect.getsource(exp2_simhash.simhash_fingerprint) + "\n\n" + inspect.getsource(exp2_simhash.hamming),
         "exp2_simhash_fp.png"),
        ("权重方案的干净因子对照（exp2_simhash.py SCHEME_GRID / make_fingerprints）",
         extract_module_block(exp2_simhash, "SCHEME_GRID = [", "]\nSCHEMES = SCHEME_GRID")
         + "\n" + inspect.getsource(exp2_simhash.make_fingerprints),
         "exp2_simhash_main.png"),
        ("三层金标准与分组内相似度自检（exp2_simhash.py main 关键段）",
         extract_section(inspect.getsource(exp2_simhash.main), "# ---------- 主实验",
                         "# ---------- 文本范围对照"),
         "exp2_simhash_gold.png"),
        ("标题级 / 正文级 / 合并文本的范围对照（exp2_simhash.py main 关键段）",
         extract_section(inspect.getsource(exp2_simhash.main), "# ---------- 文本范围对照",
                         "# ---------- 漏检组别分布"),
         "exp2_simhash_scope.png"),
    ]


def extract_module_block(module, start_marker, end_marker):
    """从模块源码中截取以 start_marker 开头、到 end_marker 之前的代码块。

    用于抓取模块级常量（如 SCHEME_GRID），这类对象没有 __code__，
    不能用 inspect.getsource 直接取。
    """
    src = inspect.getsource(module)
    i = src.find(start_marker)
    if i < 0:
        raise ValueError(f"未找到块起始 {start_marker!r}")
    j = src.find(end_marker, i)
    if j < 0:
        raise ValueError(f"未找到块结束 {end_marker!r}")
    return src[i:j].rstrip("\n")


def extract_section(src, start_marker, end_marker):
    """按起止标记截取代码段。

    标记缺失时**直接报错**而不是静默退化为“整份源码”——
    初版 `next(..., 0)` 在标记改名后会悄悄截出整个 main 函数，
    生成一张 6290 px 高的无效“代码截图”，属于典型的静默失败。
    """
    lines = src.split("\n")
    start = next((i for i, ln in enumerate(lines) if start_marker in ln), None)
    if start is None:
        raise ValueError(f"起始标记未找到: {start_marker!r}")
    end = next((i for i, ln in enumerate(lines[start + 1:], start + 1) if end_marker in ln), None)
    if end is None:
        raise ValueError(f"结束标记未找到: {end_marker!r}")
    return "\n".join(lines[start:end])


def main():
    for title, code, fname in models_and_functions():
        render_code(code, title, os.path.join(FIG_DIR, fname))


if __name__ == "__main__":
    main()