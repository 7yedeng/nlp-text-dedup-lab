# -*- coding: utf-8 -*-
"""
实验题目一(1)：基于 TF-IDF 的文本特征表示与相似度检索
要求：
  - 不少于500条中文新闻标题语料（每行一条）
  - jieba 分词 + 去停用词
  - TfidfVectorizer(max_features=1000, ngram_range=(1,2))
  - 余弦相似度找出 Top-10 相似文本对
  - 可视化词频最高20个词的 TF-IDF 权重柱状图
"""
import os
import re
from collections import Counter

import jieba
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "out")
FIG = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

# 常用中文停用词（截取常用集合，含标点）
STOPWORDS = set("""的 了 和 是 就 都 而 及 与 着 或 一个 没有 我们 你们 他们 它们 这 那 之 在 上 下 中 有 我 你 他 她 它 也 还 又 被 让 把 对 从 向 为 以 于 到 出 过 很 更 最 不 没 谁 什么 怎么 为什么 如何 哪 哪些 因为 所以 但是 然而 虽然 如果 只要 已经 正在 将 会 能 可以 应该 必须 这个 那个 这些 那些 这 那 的 地 得 啊 吧 呢 嘛 啦 呀 吗 哈 好 哦 嗯 一 二 三 四 五 六 七 八 九 十 万 亿 百 千 个 条 篇 岁 年 月 日 时 分 秒 今天 昨天 明天 现在 时候 方面 进行 通过 随着 据悉 记者 报道 消息 表示 称 称 目前 日前 近日 日前 已经 香港 台湾 中国 美国 日本 """.split())

def load_titles(path):
    with open(path, encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    return lines

def tokenize(text):
    """jieba 分词，去掉停用词与纯数字/单字符标点"""
    words = jieba.lcut(text)
    out = []
    for w in words:
        w = w.strip()
        if not w or w in STOPWORDS:
            continue
        if re.fullmatch(r"[\d\W_]+", w):
            continue
        out.append(w)
    return out

def main():
    titles = load_titles(os.path.join(DATA, "titles.txt"))
    print(f"语料规模: {len(titles)} 条新闻标题")

    # 1) 分词预处理：空格连接，供 TfidfVectorizer 进一步按词切分
    seg_docs = [" ".join(tokenize(t)) for t in titles]
    non_empty = [(t, s) for t, s in zip(titles, seg_docs) if s.strip()]
    titles = [t for t, _ in non_empty]
    seg_docs = [s for _, s in non_empty]
    print(f"去除空白后有效语料: {len(titles)} 条")

    # 2) TF-IDF 特征矩阵
    vectorizer = TfidfVectorizer(max_features=1000, ngram_range=(1, 2), token_pattern=r"(?u)\b\w+\b")
    X = vectorizer.fit_transform(seg_docs)
    print(f"TF-IDF 矩阵形状: {X.shape}  (文档数x特征数, max_features=1000, ngram_range=(1,2))")
    feats = vectorizer.get_feature_names_out()

    # 3) 余弦相似度 Top-10 文本对
    sim = cosine_similarity(X)
    np.fill_diagonal(sim, -1.0)
    idx = np.argsort(sim, axis=None)[::-1][:10]
    n = sim.shape[0]
    pairs = []
    for flat in idx:
        i, j = divmod(int(flat), n)
        pairs.append((sim[i, j], i, j))

    lines = ["=== Top-10 最相似文本对（余弦相似度）==="]
    for k, (s, i, j) in enumerate(pairs, 1):
        line = f"{k}. 相似度={s:.4f}\n    A[{i}]: {titles[i][:60]}\n    B[{j}]: {titles[j][:60]}"
        print(line)
        lines.append(line)
    for s, i, j in pairs:
        if s > 0.3:
            print(f"    (其中 A[{i}] <-> B[{j}] 相似度 {s:.3f} >= 0.3，可视为冗余/近似重复)")

    # 4) 词频统计 + Top-20 词的 TF-IDF 权重
    freq = Counter()
    for doc in seg_docs:
        freq.update(doc.split())
    top20_words = [w for w, _ in freq.most_common(20)]
    fdict = {feats[k]: k for k in range(len(feats))}
    data = X.toarray()
    tfidf_weights = []
    for w in top20_words:
        if w in fdict:
            col = data[:, fdict[w]]
            nz = col[col > 0]
            weight = nz.mean() if len(nz) else 0.0
        else:
            weight = 0.0
        tfidf_weights.append(weight)

    with open(os.path.join(OUT, "exp1_tfidf_results.txt"), "w", encoding="utf-8") as f:
        f.write(f"语料规模: {len(titles)}\n")
        f.write(f"TF-IDF 矩阵形状: {X.shape}\n\n")
        f.write("\n".join(lines) + "\n\n")
        f.write("=== 词频最高20词及其平均 TF-IDF 权重 ===\n")
        for w, fr, wgt in zip(top20_words, (freq[w] for w in top20_words), tfidf_weights):
            f.write(f"{w}\t词频={fr}\t平均TF-IDF={wgt:.4f}\n")

    # 5) 可视化：词频最高20个词的 TF-IDF 权重柱状图
    fig, ax = plt.subplots(figsize=(10, 7))
    order = np.argsort(tfidf_weights)
    words_plot = [top20_words[k] for k in order]
    w_plot = [tfidf_weights[k] for k in order]
    bars = ax.barh(words_plot, w_plot, color="#4C72B0")
    for b, v in zip(bars, w_plot):
        ax.text(v + 0.001, b.get_y() + b.get_height() / 2, f"{v:.4f}", va="center", fontsize=9)
    ax.set_xlabel("平均 TF-IDF 权重（出现文档中的均值）")
    ax.set_title("词频最高 20 个词的 TF-IDF 权重柱状图")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "exp1_tfidf_top20.png"), dpi=150)
    print("\n已保存:", os.path.join(FIG, "exp1_tfidf_top20.png"))

if __name__ == "__main__":
    main()