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
    r"C:\Windows\Fonts\msyh.ttc",      # 微软雅黑（含中文）
    r"C:\Windows\Fonts\simhei.ttf",    # 黑体
    r"C:\Windows\Fonts\simsun.ttc",    # 宋体
]
FONT_PATH = next((f for f in FONT_CANDIDATES if os.path.exists(f)), None)
if FONT_PATH is None:
    raise SystemExit("未找到可用中文字体")


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
        ("MinHash 签名生成 k=128（exp1_minhash.py MinHash.update）",
         inspect.getsource(exp1_minhash.MinHash.update),
         "exp1_minhash_update.png"),
        ("LSH 分桶与候选生成（exp1_minhash.py build_lsh_tables / lsh_candidates）",
         inspect.getsource(exp1_minhash.build_lsh_tables) + "\n" + inspect.getsource(exp1_minhash.lsh_candidates),
         "exp1_lsh.png"),
        ("Word2Vec 加载与语义推理（exp2_wordvec.py main 关键段）",
         extract_section(inspect.getsource(exp2_wordvec.main), "wv = KeyedVectors", "=== 词对相似度"),
         "exp2_wordvec_load.png"),
        ("词向量平均池化生成文档向量（exp2_wordvec.py doc_vector）",
         inspect.getsource(exp2_wordvec.doc_vector),
         "exp2_docvector.png"),
        ("KMeans 文本聚类与纯度/ARI 评估（exp2_wordvec.py main 关键段）",
         extract_section(inspect.getsource(exp2_wordvec.main), "cats = [m[0] for m in meta]", "# ---------- 5) PCA / t-SNE"),
         "exp2_kmeans.png"),
        ("64 位加权 SimHash 指纹与海明距离（exp2_simhash.py）",
         inspect.getsource(exp2_simhash.simhash_fingerprint) + "\n\n" + inspect.getsource(exp2_simhash.hamming),
         "exp2_simhash_fp.png"),
        ("TF-IDF 加权 SimHash 实验主体（exp2_simhash.py main 关键段）",
         extract_section(inspect.getsource(exp2_simhash.main), "fp_w = []", "# ---------- Ground truth"),
         "exp2_simhash_main.png"),
    ]


def extract_section(src, start_marker, end_marker):
    lines = src.split("\n")
    start = next((i for i, ln in enumerate(lines) if start_marker in ln), 0)
    end = next((i for i, ln in enumerate(lines[start + 1:], start + 1) if end_marker in ln), None)
    if end is None:
        end = len(lines)
    return "\n".join(lines[start:end])


def main():
    for title, code, fname in models_and_functions():
        render_code(code, title, os.path.join(FIG_DIR, fname))


if __name__ == "__main__":
    main()