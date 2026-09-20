# -*- coding: utf-8 -*-
"""
实验题目一(2)：基于 MinHash+LSH 的短文本近似去重
要求：
  - 6 个测试短文本用例（完全重复/轻度修改/中度改写/完全不相关，txt 保存）
  - MinHash 签名生成，哈希函数个数 k=128
  - LSH 分桶策略的近似近邻查找，批量计算相似度并识别冗余文本
  - 对比 N-gram+Jaccard 精确计算与 MinHash 近似计算（准确率、运行时间），
    分析不同阈值对去重结果的影响
"""
import os
import re
import time
import hashlib
import itertools
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import jieba

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "out")
FIG = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)

K = 128                 # MinHash 签名长度
P = 2**61 - 1           # 大素数（梅森素数），保证随机哈希均匀

# 常用中文停用词（与实验一(1)保持一致）
STOPWORDS = set("""的 了 和 是 就 都 而 及 与 着 或 一个 没有 我们 你们 他们 它们 这 那 之 在 上 下 中 有 我 你 他 她 它 也 还 又 被 让 把 对 从 向 为 以 于 到 出 过 很 更 最 不 没 谁 什么 怎么 为什么 如何 哪 哪些 因为 所以 但是 然而 虽然 如果 只要 已经 正在 将 会 能 可以 应该 必须 这个 那个 这些 那些 啊 吧 呢 嘛 啦 呀 吗 哈 好 哦 嗯 一 二 三 四 五 六 七 八 九 十 万 亿 百 千 个 条 篇 岁 年 月 日 时 分 秒 今天 昨天 明天 现在 时候 方面 进行 通过 随着 据悉 记者 报道 消息 表示 称 目前 日前 近日 已经 香港 台湾 中国 美国 日本 """.split())


# ------------------- 工具函数 -------------------
def tokenize(text):
    """jieba 分词，去停用词与纯标点/数字"""
    out = []
    for w in jieba.lcut(text):
        w = w.strip()
        if not w or w in STOPWORDS:
            continue
        if re.fullmatch(r"[\d\W_]+", w):
            continue
        out.append(w)
    return out


def shingles(text):
    """N-gram shingle 集合：词 1-gram 与相邻词 2-gram 的并集
    （中度改写文本在字面顺序上变化大，词级 1+2-gram 能在字面重叠与
     语义容忍之间取得平衡，是中文短文本去重的常用做法）"""
    words = tokenize(text)
    grams = set(words)
    for i in range(len(words) - 1):
        grams.add(words[i] + "|" + words[i + 1])
    return grams


def int_hash(s):
    """字符串 -> 确定性 64 位整数（避免 Python 内置 hash 的随机化）"""
    return int(hashlib.md5(s.encode("utf-8")).hexdigest()[:16], 16)


class MinHash:
    """MinHash 签名器：k 个随机哈希函数 h_i(x) = (a_i * x + b_i) mod P"""

    def __init__(self, k=K, seed=42):
        rng = np.random.RandomState(seed)
        self.k = k
        self.a = rng.randint(1, P // 2, size=k, dtype=np.int64)
        self.b = rng.randint(0, P // 2, size=k, dtype=np.int64)
        # 每篇文档签名按列存储：shape = (k,)
        self._sig = np.full(k, P, dtype=np.int64)

    def update(self, shingle_set):
        # 纯 Python 大整数计算，避免 numpy int64 相乘溢出
        a, b, sig = self.a.tolist(), self.b.tolist(), self._sig.tolist()
        for x in shingle_set:
            v = int_hash(x) % P
            for i in range(self.k):
                h = (a[i] * v + b[i]) % P
                if h < sig[i]:
                    sig[i] = h
        self._sig[:] = sig

    def signature(self):
        return self._sig.copy()


def minhash_signature(shingle_set, k=K, seed=42):
    mh = MinHash(k, seed)
    mh.update(shingle_set)
    return mh.signature()


def jaccard_exact(s1, s2):
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)


def jaccard_minhash(sig1, sig2):
    return float(np.mean(sig1 == sig2))


def hamming(a, b):
    return int(np.sum(a != b))


# ------------------- 主体 -------------------
def load_cases(path):
    with open(path, encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    return lines


def build_lsh_tables(sigs, b=16, r=8):
    """返回: {band_i: {bucket_key: set(doc_idx)}}"""
    tables = [defaultdict(set) for _ in range(b)]
    for di, sig in enumerate(sigs):
        for bi in range(b):
            key = tuple(sig[bi * r:(bi + 1) * r].tolist())
            tables[bi][key].add(di)
    return tables


def lsh_candidates(tables):
    """从每个桶中提取候选对（桶内 >1 个元素两两组合）"""
    cand = set()
    for t in tables:
        for bucket in t.values():
            bucket = sorted(bucket)
            for i, j in itertools.combinations(bucket, 2):
                cand.add((i, j))
    return cand


def prf(gold_pairs, pred_pairs):
    """查准率/查全率/F1"""
    gold = set(gold_pairs)
    pred = set(pred_pairs)
    tp = len(gold & pred)
    p = tp / len(pred) if pred else 1.0
    r = tp / len(gold) if gold else 1.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def main():
    cases = load_cases(os.path.join(DATA, "short_texts.txt"))
    print(f"测试用例数: {len(cases)}")
    for i, c in enumerate(cases, 1):
        print(f"  T{i}: {c}")

    # 1) N-gram 集合 + 精确 Jaccard
    sets = [shingles(c) for c in cases]
    n = len(cases)
    # ground truth：T1~T4 为同一事件的不同改写版本，任意两两均视为"重复"
    gold_pairs = [(i, j) for i in range(4) for j in range(i + 1, 4)]

    t0 = time.perf_counter()
    exact = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            exact[i, j] = exact[j, i] = jaccard_exact(sets[i], sets[j])
    t_exact = time.perf_counter() - t0

    # 2) MinHash 签名 + 近似 Jaccard
    t0 = time.perf_counter()
    sigs = [minhash_signature(s) for s in sets]
    approx = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            approx[i, j] = approx[j, i] = jaccard_minhash(sigs[i], sigs[j])
    t_minhash = time.perf_counter() - t0

    # 3) LSH 分桶候选：对比两种分桶参数 (b=bands, r=rows/band)
    lsh_configs = [(16, 8), (64, 2)]
    lsh_cands = {}
    for b, r in lsh_configs:
        t0 = time.perf_counter()
        tables = build_lsh_tables(sigs, b=b, r=r)
        lsh_cands[(b, r)] = lsh_candidates(tables)
        print(f"  LSH(b={b}, r={r}) 建桶耗时={(time.perf_counter()-t0)*1000:.2f}ms, 候选对={len(lsh_cands[(b,r)])}")

    print("\n=== 各测试文本对相似度（精确 Jaccard / MinHash 估计 / LSH候选?）===")
    res_lines = ["=== 词级 N-gram(1+2-gram) Jaccard ==="]
    cand = lsh_cands[(64, 2)]           # 宽松分桶配置的候选用于标注
    for i in range(n):
        for j in range(i + 1, n):
            mark = "候选" if (i, j) in cand else "    "
            print(f"  T{i+1}-T{j+1}: Jaccard={exact[i,j]:.4f}  MinHash={approx[i,j]:.4f}  {mark}")
            res_lines.append(f"  T{i+1}-T{j+1}: Jaccard={exact[i,j]:.4f}  MinHash={approx[i,j]:.4f}  LSH候选={mark}")

    # MinHash 估计误差
    err = np.abs(exact - approx)[np.triu_indices(n, 1)]
    print(f"\nMinHash 估计平均绝对误差: {err.mean():.4f}  最大: {err.max():.4f}")
    res_lines.append(f"\nMinHash 估计平均绝对误差: {err.mean():.4f}  最大: {err.max():.4f}")

    # 4) 阈值扫描：不同阈值下去重判定 P/R/F1
    thresholds = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    rows = []
    for t in thresholds:
        pred_exact = {(i, j) for i in range(n) for j in range(i + 1, n) if exact[i, j] >= t}
        pred_min = {(i, j) for i in range(n) for j in range(i + 1, n) if approx[i, j] >= t}
        p1, r1, f1 = prf(gold_pairs, pred_exact)
        p2, r2, f2 = prf(gold_pairs, pred_min)
        rows.append((t, p1, r1, f1, p2, r2, f2))

    print("\n=== 阈值对去重结果的影响（ground truth: T1~T4 属同一事件）===")
    print("阈值 | 精确Jaccard(P/R/F1)      | MinHash(P/R/F1)")
    res_lines.append("\n=== 阈值对去重结果的影响 ===")
    res_lines.append("阈值 | 精确Jaccard(P/R/F1) | MinHash(P/R/F1)")
    for t, p1, r1, f1, p2, r2, f2 in rows:
        print(f" {t:.1f} | {p1:.3f}/{r1:.3f}/{f1:.3f}        | {p2:.3f}/{r2:.3f}/{f2:.3f}")
        res_lines.append(f" {t:.1f} | {p1:.3f}/{r1:.3f}/{f1:.3f} | {p2:.3f}/{r2:.3f}/{f2:.3f}")

    # LSH 去重识别：两种分桶参数对比 + 阈值回验
    print("\n=== LSH 分桶识别出的冗余候选（再用 MinHash 相似度回验）===")
    res_lines.append("\n=== LSH 分桶识别出的冗余候选 ===")
    for (b, r), cset in lsh_cands.items():
        print(f"--- LSH(b={b}, r={r}) 候选 {len(cset)} 对 ---")
        res_lines.append(f"--- LSH(b={b}, r={r}) 候选 {len(cset)} 对 ---")
        for i, j in sorted(cset):
            status = "重复" if approx[i, j] >= 0.2 else "误报(<0.2)"
            print(f"  T{i+1}-T{j+1}: MinHash 相似度={approx[i, j]:.4f} -> {status}")
            res_lines.append(f"  T{i+1}-T{j+1}: MinHash 相似度={approx[i, j]:.4f} -> {status}")

    # 5) 批量规模对运行时间的影响（精确 vs MinHash vs LSH）
    print("\n=== 批量处理规模对运行时间的影响 ===")
    res_lines.append("\n=== 批量处理规模对运行时间的影响 ===")
    times = []
    for m in [6, 50, 200, 500]:
        docs = [cases[i % len(cases)] + f" {i}" for i in range(m)]
        s = [shingles(d) for d in docs]
        t0 = time.perf_counter()
        cnt = 0
        for i in range(m):
            for j in range(i + 1, m):
                jaccard_exact(s[i], s[j]); cnt += 1
        te = time.perf_counter() - t0
        t0 = time.perf_counter()
        ss = [minhash_signature(x) for x in s]
        for i in range(m):
            for j in range(i + 1, m):
                jaccard_minhash(ss[i], ss[j])
        tm = time.perf_counter() - t0
        t0 = time.perf_counter()
        tb = build_lsh_tables(ss, b=16, r=8)
        cand2 = lsh_candidates(tb)
        tl = time.perf_counter() - t0
        times.append((m, te, tm, tl))
        print(f"  文档数={m:4d}: 精确Jaccard={te*1000:.2f}ms  MinHash全对比={tm*1000:.2f}ms  LSH建桶+候选={tl*1000:.2f}ms (候选{len(cand2)}对)")
        res_lines.append(f"  文档数={m:4d}: 精确Jaccard={te*1000:.2f}ms  MinHash全对比={tm*1000:.2f}ms  LSH建桶+候选={tl*1000:.2f}ms (候选{len(cand2)}对)")

    with open(os.path.join(OUT, "exp1_minhash_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(res_lines))

    # 6) 可视化
    # 图1：精确 vs MinHash 估计相似度散点
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    xs = exact[np.triu_indices(n, 1)]
    ys = approx[np.triu_indices(n, 1)]
    ax[0].scatter(xs, ys, s=60, color="#C44E52")
    lim = [0, 1]
    ax[0].plot(lim, lim, "k--", alpha=0.6, label="y=x")
    ax[0].set_xlabel("精确 Jaccard 相似度")
    ax[0].set_ylabel("MinHash 估计相似度")
    ax[0].set_title("MinHash 近似 vs 精确 N-gram Jaccard")
    ax[0].legend()
    ax[0].set_xlim(0, 1); ax[0].set_ylim(0, 1)

    ts = [r[0] for r in rows]
    f_exact = [r[3] for r in rows]
    f_min = [r[6] for r in rows]
    ax[1].plot(ts, f_exact, "o-", label="精确 Jaccard F1")
    ax[1].plot(ts, f_min, "s-", label="MinHash F1")
    ax[1].set_xlabel("阈值")
    ax[1].set_ylabel("F1")
    ax[1].set_title("不同阈值下的去重 F1")
    ax[1].legend()
    ax[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "exp1_minhash_sim.png"), dpi=150)
    print("\n已保存:", os.path.join(FIG, "exp1_minhash_sim.png"))

    # 图2：批量规模运行时间（对数 y 轴）
    fig2, ax2 = plt.subplots(figsize=(8, 5))
    m = [x[0] for x in times]
    ax2.plot(m, [x[1] * 1000 for x in times], "o-", label="精确 Jaccard")
    ax2.plot(m, [x[2] * 1000 for x in times], "s-", label="MinHash 全量对比")
    ax2.plot(m, [x[3] * 1000 for x in times], "^-", label="LSH 建桶+候选生成")
    ax2.set_yscale("log")
    ax2.set_xlabel("文档数")
    ax2.set_ylabel("耗时 (ms, 对数刻度)")
    ax2.set_title("批量规模对计算耗时的影响")
    ax2.legend()
    ax2.grid(alpha=0.3, which="both")
    fig2.tight_layout()
    fig2.savefig(os.path.join(FIG, "exp1_minhash_scaling.png"), dpi=150)
    print("已保存:", os.path.join(FIG, "exp1_minhash_scaling.png"))


if __name__ == "__main__":
    main()