# -*- coding: utf-8 -*-
"""
实验题目二(2)：基于加权 SimHash 的网页新闻相似度计算
要求：
  - 20 篇网页新闻（同一事件不同报道 / 转载改写 / 完全不同主题，txt 保存）
  - 传统 SimHash 基础上引入 TF-IDF 权重：高 TF-IDF 词加权、停用词降权
  - 批量计算 64 位加权 SimHash 指纹，海明距离两两计算相似度，距离<=3 判定近似重复
  - 对比传统等权 SimHash 与 TF-IDF 加权 SimHash：查准率/查全率/F1
"""
import os
import re
import json
import hashlib
import itertools
import numpy as np
import jieba
from collections import Counter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.feature_extraction.text import TfidfVectorizer

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data", "news20")
OUT = os.path.join(BASE, "out")
FIG = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)

STOPWORDS = set("""的 了 和 是 就 都 而 及 与 着 或 一个 没有 我们 你们 他们 它们 这 那 之 在 上 下 中 有 我 你 他 她 它 也 还 又 被 让 把 对 从 向 为 以 于 到 出 过 很 更 最 不 没 谁 什么 怎么 为什么 如何 哪 哪些 因为 所以 但是 然而 虽然 如果 只要 已经 正在 将 会 能 可以 应该 必须 这个 那个 这些 那些 啊 吧 呢 嘛 啦 呀 吗 哈 好 哦 嗯 一 二 三 四 五 六 七 八 九 十 万 亿 百 千 个 条 篇 岁 年 月 日 时 分 秒 今天 昨天 明天 现在 时候 方面 进行 通过 随着 据悉 记者 报道 消息 表示 称 目前 日前 近日 已经 香港 台湾 中国 美国 日本 """.split())

BITS = 64          # 指纹长度 64 位
HAM_TH = 3         # 海明距离 <=3 判定为近似重复


# ------------------- 工具 -------------------
def load_news20():
    """读取 data/news20/*.txt + manifest.json 分组标签"""
    docs = []
    manifest = json.load(open(os.path.join(DATA, "manifest.json"), encoding="utf-8"))
    order = []
    for fn in sorted(os.listdir(DATA)):
        if not fn.endswith(".txt"):
            continue
        idx = int(fn[:3])
        order.append(idx)
        with open(os.path.join(DATA, fn), encoding="utf-8") as f:
            lines = f.read().split("\n", 3)
        title = lines[0].replace("title=", "", 1).strip()
        body = lines[3] if len(lines) > 3 else ""
        group = manifest["doc"][str(idx)]["group"]
        docs.append({"idx": idx, "title": title, "text": title + " " + body,
                     "group": group, "cat": manifest["doc"][str(idx)]["cat"]})
    docs.sort(key=lambda d: d["idx"])
    return docs


def tokenize(text):
    """jieba 分词：保留停用词（供下方"停用词降权"使用），仅去除纯标点/数字"""
    words = []
    for w in jieba.lcut(text):
        w = w.strip()
        if not w:
            continue
        if re.fullmatch(r"[\d\W_]+", w):
            continue
        words.append(w)
    return words


def term_hash_64(term):
    """词 -> 64 位确定性哈希（取 md5 前 16 个十六进制字符）"""
    return int(hashlib.md5(term.encode("utf-8")).hexdigest()[:16], 16)


def simhash_fingerprint(terms, weights):
    """SimHash 指纹：v[64] 按 term 哈希各位累加 ±weight，符号位生成指纹"""
    v = np.zeros(BITS, dtype=np.float64)
    for term, w in zip(terms, weights):
        h = term_hash_64(term)
        for i in range(BITS):
            v[i] += w if (h >> i) & 1 else -w
    fp = 0
    for i in range(BITS):
        if v[i] > 0:
            fp |= (1 << i)
    return fp


def hamming(a, b):
    return bin(a ^ b).count("1")


def prf(gold, pred):
    gold = set(gold)
    pred = set(pred)
    tp = len(gold & pred)
    p = tp / len(pred) if pred else 1.0
    r = tp / len(gold) if gold else 1.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def main():
    docs = load_news20()
    print(f"加载 {len(docs)} 篇新闻")

    # jieba 分词
    doc_terms = [tokenize(d["text"]) for d in docs]
    seg_docs = [" ".join(ts) for ts in doc_terms]

    # TF-IDF 权重矩阵（在 20 篇上训练）
    vectorizer = TfidfVectorizer(ngram_range=(1, 1), token_pattern=r"(?u)\b\w+\b")
    X = vectorizer.fit_transform(seg_docs).toarray()
    feats = vectorizer.get_feature_names_out()
    feat_index = {f: i for i, f in enumerate(feats)}

    # 停用词降权系数
    STOP_SCALE = 0.2
    # 词在文档内的 TF（传统等权 SimHash 使用）
    tf_lists = []
    for ts in doc_terms:
        c = Counter(ts)
        tf_lists.append(c)

    # ---------- 加权 SimHash（TF-IDF 权重 + 停用词降权） ----------
    fp_w = []
    for di, ts in enumerate(doc_terms):
        wlist = []
        for t in ts:
            w = float(X[di, feat_index[t]]) if t in feat_index else 0.0
            if t in STOPWORDS:
                w *= STOP_SCALE          # 停用词降权
            wlist.append(w)
        fp_w.append(simhash_fingerprint(ts, wlist))

    # ---------- 传统等权 SimHash（词频权重） ----------
    fp_e = []
    for di, ts in enumerate(doc_terms):
        wlist = [float(tf_lists[di].get(t, 1)) for t in ts]
        fp_e.append(simhash_fingerprint(ts, wlist))

    # ---------- Ground truth：同分组=同一事件=近似重复 ----------
    n = len(docs)
    gold = []
    for i in range(n):
        for j in range(i + 1, n):
            if docs[i]["group"] == docs[j]["group"]:
                gold.append((i, j))
    print(f"Ground truth 重复对: {len(gold)} 对（同组事件）")

    # ---------- 阈值扫描 + HAM_TH=3 判定 ----------
    res = {}
    for name, fps in [("TF-IDF加权", fp_w), ("等权(词频)", fp_e)]:
        dist = np.zeros((n, n), dtype=int)
        for i, j in itertools.combinations(range(n), 2):
            d = hamming(fps[i], fps[j])
            dist[i, j] = dist[j, i] = d
        pred = {(i, j) for i, j in itertools.combinations(range(n), 2) if dist[i, j] <= HAM_TH}
        p, r, f1 = prf(gold, pred)
        res[name] = {"pred": pred, "P": p, "R": r, "F1": f1, "dist": dist}
        print(f"\n【{name} SimHash】海明距离<= {HAM_TH} 判定近似重复")
        print(f"  查准率 P = {p:.3f}  查全率 R = {r:.3f}  F1 = {f1:.3f}")

    # 阈值扫描（0~10）展示距离阈值影响
    sweep = {}
    for name, fps in [("TF-IDF加权", fp_w), ("等权(词频)", fp_e)]:
        rows = []
        for th in range(0, 11):
            pred = {(i, j) for i, j in itertools.combinations(range(n), 2)
                    if hamming(fps[i], fps[j]) <= th}
            p, r, f1 = prf(gold, pred)
            rows.append((th, p, r, f1))
        sweep[name] = rows

    print("\n=== 海明距离阈值扫描（P/R/F1）===")
    print(" 阈值 | TF-IDF加权(P/R/F1)          | 等权(P/R/F1)")
    for k in range(11):
        a = sweep["TF-IDF加权"][k]; b = sweep["等权(词频)"][k]
        print(f"   {a[0]:2d}  | {a[1]:.3f}/{a[2]:.3f}/{a[3]:.3f}              | {b[1]:.3f}/{b[2]:.3f}/{b[3]:.3f}")

    # 各方法检出的重复对明细
    for name in ["TF-IDF加权", "等权(词频)"]:
        print(f"\n【{name} SimHash】判定为近似重复的文本对：")
        for i, j in sorted(res[name]["pred"]):
            hit = "★命中" if docs[i]["group"] == docs[j]["group"] else "误报"
            print(f"  {i+1:02d}-{j+1:02d} [{docs[i]['group']}vs{docs[j]['group']}] "
                  f"{docs[i]['title'][:16]}... | {docs[j]['title'][:16]}... {hit}")

    # ---------- 结果落盘 ----------
    lines = []
    lines.append(f"数据集: {n} 篇新闻（同事件不同报道/转载改写/完全不同主题）  Ground truth重复对={len(gold)}")
    lines.append(f"判定规则: 64 位指纹海明距离 <= {HAM_TH} 为近似重复\n")
    for name in ["TF-IDF加权", "等权(词频)"]:
        lines.append(f"{name} SimHash: P={res[name]['P']:.3f} R={res[name]['R']:.3f} F1={res[name]['F1']:.3f}")
    lines.append("\n=== 海明距离阈值扫描 ===")
    for k in range(11):
        a = sweep["TF-IDF加权"][k]; b = sweep["等权(词频)"][k]
        lines.append(f"阈值={a[0]:2d}: TF-IDF加权 P={a[1]:.3f} R={a[2]:.3f} F1={a[3]:.3f} | 等权 P={b[1]:.3f} R={b[2]:.3f} F1={b[3]:.3f}")
    for name in ["TF-IDF加权", "等权(词频)"]:
        lines.append(f"\n--- {name} 检出的重复对 ---")
        for i, j in sorted(res[name]["pred"]):
            hit = "★命中" if docs[i]["group"] == docs[j]["group"] else "误报"
            lines.append(f"  {i+1:02d}-{j+1:02d} [{docs[i]['group']}vs{docs[j]['group']}] {docs[i]['title'][:20]} <-> {docs[j]['title'][:20]} {hit}")
    with open(os.path.join(OUT, "exp2_simhash_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # ---------- 可视化 ----------
    # 图1：两种方法 P/R/F1 对比
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    names = ["TF-IDF加权", "等权(词频)"]
    mets = ["P", "R", "F1"]
    x = np.arange(len(mets))
    w = 0.32
    for k, name in enumerate(names):
        vals = [res[name][m] for m in mets]
        axes[0].bar(x + (k - 0.5) * w, vals, w, label=name,
                    color=["#4C72B0", "#C44E52"][k])
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(["查准率 P", "查全率 R", "F1"])
    axes[0].set_ylim(0, 1.05)
    axes[0].set_title("等权 vs TF-IDF 加权 SimHash 去重效果（距离<=3）")
    axes[0].legend()
    for k, name in enumerate(names):
        for xi, m in enumerate(mets):
            v = res[name][m]
            axes[0].text(xi + (k - 0.5) * w, v + 0.02, f"{v:.2f}", ha="center", fontsize=9)
    axes[0].grid(axis="y", alpha=0.3)

    # 图2：阈值扫描 F1 曲线
    ths = [r[0] for r in sweep["TF-IDF加权"]]
    axes[1].plot(ths, [r[3] for r in sweep["TF-IDF加权"]], "o-", label="TF-IDF 加权 SimHash")
    axes[1].plot(ths, [r[3] for r in sweep["等权(词频)"]], "s-", label="等权 SimHash")
    axes[1].axvline(HAM_TH, color="gray", ls="--", alpha=0.7, label=f"阈值={HAM_TH}")
    axes[1].set_xlabel("海明距离阈值")
    axes[1].set_ylabel("F1")
    axes[1].set_title("海明距离阈值对去重 F1 的影响")
    axes[1].legend()
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "exp2_simhash_prf.png"), dpi=150)
    print("\n已保存:", os.path.join(FIG, "exp2_simhash_prf.png"))


if __name__ == "__main__":
    main()