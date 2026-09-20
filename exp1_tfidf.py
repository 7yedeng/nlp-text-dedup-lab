# -*- coding: utf-8 -*-
"""
实验题目一(1)：基于 TF-IDF 的文本特征表示与相似度检索
要求：
  - 不少于500条中文新闻标题语料（每行一条）
  - jieba 分词 + 去停用词
  - TfidfVectorizer(max_features=1000, ngram_range=(1,2))
  - 余弦相似度找出 Top-10 相似文本对
  - 可视化词频最高20个词的 TF-IDF 权重柱状图

【相对初版修正的三处缺陷】（均由复现审计发现，详见 out/AUDIT_NOTES.md）
  修正1 语料规范化：原始 titles.txt 存在仅空格差异的重复条目（如“腾势 D9”/“腾势D9”），
       分词后词序列完全一致、余弦相似度恒为 1.0000，会独占 Top-10 名额。现按
       “去空白 + 统一小写” 规范化后去重，并统计移除条数。
  修正2 Top-10 取对：初版对全矩阵 argsort 后取前 10，会同时取到 (i,j) 与 (j,i)，
       使 Top-10 实际只有约 5 个不同的文本对。现改为只在上三角（i<j）中排序。
  修正3 大小写一致性：分词阶段统一转小写，与 TfidfVectorizer(lowercase=True) 的
       特征名对齐。初版分词保留 “AI” 原形，而特征名是 “ai”，导致按特征名回查权重时
       必然落空，把 “AI” 误报成“权重为 0.0000 / 未进入特征集”。
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


def normalize_title(text):
    """标题规范化：压缩全部空白并统一小写，用于判重。"""
    return re.sub(r"\s+", "", text).strip().lower()


def dedup_titles(titles):
    """按规范化标题去重（保留首次出现顺序）。返回 (保留列表, 被移除条数)。"""
    seen, kept = set(), []
    for t in titles:
        k = normalize_title(t)
        if not k or k in seen:
            continue
        seen.add(k)
        kept.append(t)
    return kept, len(titles) - len(kept)


def tokenize(text):
    """jieba 分词，去掉停用词与纯数字/单字符标点。

    英文统一转小写：与 TfidfVectorizer(lowercase=True) 的特征名保持一致，
    保证后续按特征名回查权重时能命中（修正3）。
    """
    words = jieba.lcut(text)
    out = []
    for w in words:
        w = w.strip().lower()
        if not w or w in STOPWORDS:
            continue
        if re.fullmatch(r"[\d\W_]+", w):
            continue
        out.append(w)
    return out


def top_pairs_upper_triangle(sim, k=10):
    """只在上三角（i<j）中取相似度最高的 k 个文本对（修正2）。"""
    iu = np.triu_indices(sim.shape[0], k=1)
    vals = sim[iu]
    k = min(k, len(vals))
    order = np.argsort(-vals, kind="stable")[:k]
    return [(float(vals[o]), int(iu[0][o]), int(iu[1][o])) for o in order]


def main():
    raw_titles = load_titles(os.path.join(DATA, "titles.txt"))
    print(f"语料规模(原始): {len(raw_titles)} 条新闻标题")

    # 0) 语料规范化去重（修正1）
    titles, n_removed = dedup_titles(raw_titles)
    print(f"规范化去重后: {len(titles)} 条（移除仅空白/大小写差异的重复标题 {n_removed} 条）")
    dup_ratio = n_removed / len(raw_titles) if raw_titles else 0.0

    # 1) 分词预处理：空格连接，供 TfidfVectorizer 进一步按词切分
    seg_docs = [" ".join(tokenize(t)) for t in titles]
    non_empty = [(t, s) for t, s in zip(titles, seg_docs) if s.strip()]
    n_empty = len(titles) - len(non_empty)
    titles = [t for t, _ in non_empty]
    seg_docs = [s for _, s in non_empty]
    print(f"去除空白后有效语料: {len(titles)} 条（分词后为空被丢弃 {n_empty} 条）")

    # 2) TF-IDF 特征矩阵
    vectorizer = TfidfVectorizer(max_features=1000, ngram_range=(1, 2), token_pattern=r"(?u)\b\w+\b")
    X = vectorizer.fit_transform(seg_docs)
    print(f"TF-IDF 矩阵形状: {X.shape}  (文档数x特征数, max_features=1000, ngram_range=(1,2))")
    feats = vectorizer.get_feature_names_out()

    # 3) 余弦相似度 Top-10 文本对（修正2：只取上三角）
    sim = cosine_similarity(X)
    pairs = top_pairs_upper_triangle(sim, 10)

    lines = ["=== Top-10 最相似文本对（余弦相似度）==="]
    for k, (s, i, j) in enumerate(pairs, 1):
        line = f"{k}. 相似度={s:.4f}\n    A[{i}]: {titles[i][:60]}\n    B[{j}]: {titles[j][:60]}"
        print(line)
        lines.append(line)
    n_redundant = sum(1 for s, _, _ in pairs if s >= 0.3)
    print(f"    （Top-10 中有 {n_redundant} 对相似度 >= 0.3，可视为冗余/近似重复）")

    # 3b) 相似度分布统计
    iu = np.triu_indices(sim.shape[0], k=1)
    all_sims = sim[iu]
    dist = {
        "n_pairs": int(len(all_sims)),
        "mean": float(all_sims.mean()),
        "p50": float(np.percentile(all_sims, 50)),
        "p99": float(np.percentile(all_sims, 99)),
        "max": float(all_sims.max()),
        "n_ge_0.9": int((all_sims >= 0.9).sum()),
        "n_ge_0.5": int((all_sims >= 0.5).sum()),
        "n_ge_0.3": int((all_sims >= 0.3).sum()),
    }
    print(f"    全部 {dist['n_pairs']} 个文本对：均值 {dist['mean']:.4f}，"
          f"P99 {dist['p99']:.4f}，最大 {dist['max']:.4f}")
    print(f"    相似度>=0.9 的文本对: {dist['n_ge_0.9']}；>=0.5: {dist['n_ge_0.5']}；>=0.3: {dist['n_ge_0.3']}")

    # 4) 词频统计 + Top-20 词的 TF-IDF 权重（修正3：key 小写对齐）
    freq = Counter()
    for doc in seg_docs:
        freq.update(doc.split())
    top20_words = [w for w, _ in freq.most_common(20)]
    fdict = {str(feats[k]): k for k in range(len(feats))}
    data = X.toarray()
    tfidf_weights, in_vocab = [], []
    for w in top20_words:
        key = w.lower()                      # 修正3：与 lowercase=True 的特征名对齐
        if key in fdict:
            col = data[:, fdict[key]]
            nz = col[col > 0]
            weight = float(nz.mean()) if len(nz) else 0.0
            in_vocab.append(True)
        else:
            weight = 0.0
            in_vocab.append(False)
        tfidf_weights.append(weight)

    n_oov = sum(1 for v in in_vocab if not v)
    print(f"    Top-20 词中未进入特征集（max_features=1000 截断）的有 {n_oov} 个")

    # 5) 落盘
    with open(os.path.join(OUT, "exp1_tfidf_results.txt"), "w", encoding="utf-8") as f:
        f.write(f"语料规模(原始): {len(raw_titles)}\n")
        f.write(f"规范化去重后语料规模: {len(titles)}\n")
        f.write(f"移除的空白/大小写重复标题数: {n_removed} ({dup_ratio:.2%})\n")
        f.write(f"TF-IDF 矩阵形状: {X.shape}\n")
        f.write(f"相似度统计: 文本对总数={dist['n_pairs']} 均值={dist['mean']:.6f} "
                f"P50={dist['p50']:.6f} P99={dist['p99']:.6f} 最大={dist['max']:.6f}\n")
        f.write(f"相似度>=0.9 文本对={dist['n_ge_0.9']}  >=0.5={dist['n_ge_0.5']}  >=0.3={dist['n_ge_0.3']}\n\n")
        f.write("\n".join(lines) + "\n\n")
        f.write(f"Top-10 中相似度>=0.3 的文本对数: {n_redundant}\n\n")
        f.write("=== 词频最高20词及其平均 TF-IDF 权重 ===\n")
        for w, fr, wgt, ok in zip(top20_words, (freq[w] for w in top20_words), tfidf_weights, in_vocab):
            f.write(f"{w}\t词频={fr}\t平均TF-IDF={wgt:.4f}\t进入特征集={'是' if ok else '否'}\n")

    # 6) 可视化：词频最高20个词的 TF-IDF 权重柱状图
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
