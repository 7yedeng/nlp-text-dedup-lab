# -*- coding: utf-8 -*-
"""
实验题目一(2)：基于 MinHash+LSH 的短文本近似去重
要求：
  - 6 个测试短文本用例（完全重复/轻度修改/中度改写/完全不相关，txt 保存）
  - MinHash 签名生成，哈希函数个数 k=128
  - LSH 分桶策略的近似近邻查找，批量计算相似度并识别冗余文本
  - 对比 N-gram+Jaccard 精确计算与 MinHash 近似计算（准确率、运行时间），
    分析不同阈值对去重结果的影响

【相对初版的修正】（详见 out/AUDIT_NOTES.md）
  修正A 三档金标准：初版把 T1~T4 两两全部视为“重复”（共 6 对），但 T1-T4/T2-T4
       的精确 Jaccard 只有 0.19/0.16，属“同一事件的中度改写”，与完全重复/轻改
       （1.00/0.31）不在同一量级。混在一起统计会让 P/R/F1 随阈值剧烈跳变、
       掩盖方法差异。现拆成三档：近重复(T1-T2)、同事件改写(T1~T4 其余对)、不相关(T5/T6)，
       并同时给出“混合口径”与“分层口径”两套 P/R/F1 以便对照。
  修正B 批量计时实验可控化：初版用 `cases[i % 6] + f" {i}"` 拼接造文档，实际生成的
       “文档”彼此几乎相同，LSH 候选对数虚高，时间对比失去意义。现改为在真实标题语料上
       做规模扩展，并报告真实候选对数与剪枝率。
  修正C 计时口径统一：把“签名生成”与“签名比对/建桶”分开计时，避免把一次性开销
       摊进每次查询。
"""
import os
import re
import gc
import json
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
M32 = 2**31 - 1         # 梅森素数 2^31-1：作为哈希模数，保证 numpy int64 乘法不溢出
P = M32                 # 兼容旧名（概率计算等处使用）
SEED = 42
REPS = 5                # 计时重复次数（报告 中位数±标准差；M1 修正：单次计时不可信）

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

    def __init__(self, k=K, seed=SEED):
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


def _pick_hash_params(k, seed=SEED):
    """
    生成 k 组 (a, b)：h_i(x) = (a_i * x + b_i) mod M32

    向量化实现的前提是乘法不溢出 int64：
        a_i < 2^31，x < 2^31  ⇒  a_i * x < 2^62 < 2^63  ✅
    因此这里把模数取为梅森素数 2^31 - 1（M32），使 numpy int64 可以安全地
    一次性算出全部 k 个哈希值。模数的大小不影响 MinHash 的无偏性——
    只要 h 在集合元素上近似均匀，签名相等概率就等于 Jaccard。
    """
    rng = np.random.RandomState(seed)
    a = rng.randint(1, M32, size=k, dtype=np.int64)
    b = rng.randint(0, M32, size=k, dtype=np.int64)
    return a, b


_HASH_A, _HASH_B = _pick_hash_params(K)


def _base_hashes(shingle_set):
    """shingle 集合 -> int64 数组（每项 < M32），作为 h 的输入 x。"""
    return np.array([int(hashlib.md5(s.encode("utf-8")).hexdigest()[:8], 16) % M32
                     for s in shingle_set], dtype=np.int64)


def minhash_signature(shingle_set, k=K, seed=SEED):
    """生成 MinHash 签名（长度 k 的整数向量）。

    向量化：v = (A * x + B) mod M32 对全部 x 与全部 k 一次性算出，再按列取最小值。
    初版用「纯 Python 双重循环」逐 shingle 逐哈希函数计算，500 篇时签名生成
    就要约 1.2 秒，反而比精确 Jaccard 更慢，使"近似更高效"的结论失去意义。

    空集合返回全 0 签名（哨兵值），配合 jaccard_minhash 的空集判定，
    与精确 Jaccard「空集合返回 0」的约定保持一致。
    """
    if not shingle_set:
        return np.zeros(k, dtype=np.int64)
    a, b = (_HASH_A, _HASH_B) if k == K else _pick_hash_params(k, seed)
    x = _base_hashes(shingle_set)                      # (n,)
    # (k, n) = a[:,None] * x[None,:] + b[:,None]，int64 安全
    vals = (a[:k, None] * x[None, :] + b[:k, None]) % M32
    return vals.min(axis=1)


def jaccard_exact(s1, s2):
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)


def jaccard_minhash(sig1, sig2):
    # 空集合的签名是全 0 哨兵；若两者都为空则显式返回 0，与 jaccard_exact 保持一致
    if not np.any(sig1) or not np.any(sig2):
        return 0.0
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
    """查准率/查全率/F1（同时返回 TP/FP/FN，避免“无预测却 F1=1.0”的误读）。"""
    gold = set(gold_pairs)
    pred = set(pred_pairs)
    tp = len(gold & pred)
    fp = len(pred - gold)
    fn = len(gold - pred)
    p = tp / len(pred) if pred else 1.0
    r = tp / len(gold) if gold else 1.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1, tp, fp, fn


# 三档金标准（修正A）
GOLD_NEAR_DUP = [(0, 1)]                                       # T1-T2 完全重复
GOLD_SAME_EVENT = [(0, 2), (1, 2), (0, 3), (1, 3), (2, 3)]     # T1/T2/T3 与 T4 的中度改写
GOLD_RELATED = GOLD_NEAR_DUP + GOLD_SAME_EVENT                 # 初版口径：T1~T4 两两


def main():
    cases = load_cases(os.path.join(DATA, "short_texts.txt"))
    print(f"测试用例数: {len(cases)}")
    for i, c in enumerate(cases, 1):
        print(f"  T{i}: {c}")

    # 1) N-gram 集合 + 精确 Jaccard
    sets = [shingles(c) for c in cases]
    n = len(cases)

    t0 = time.perf_counter()
    exact = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            exact[i, j] = exact[j, i] = jaccard_exact(sets[i], sets[j])
    t_exact = time.perf_counter() - t0

    # 金标准自检：三档相似度量级是否确实分离
    jac_near = [exact[i, j] for i, j in GOLD_NEAR_DUP]
    jac_same = [exact[i, j] for i, j in GOLD_SAME_EVENT]
    print(f"\n[金标准自检] 近重复对 Jaccard={['%.4f' % v for v in jac_near]}  "
          f"同事件改写对 Jaccard={['%.4f' % v for v in jac_same]}")
    print("  -> 两档量级明显分离，说明“重复”应分层定义，而非全部混入同一条 P/R/F1")
    print("  [用例设计复核] T1/T2/T3 为亚运首金同一表述的不同改法；T4 虽同事件但句子结构完全重写；")
    print("                 T5（特斯拉/xAI 投资）与 T6（佟丽娅离婚）为不同领域事件，与 T1~T4 无交集。")

    # 2) MinHash 签名 + 近似 Jaccard
    t0 = time.perf_counter()
    sigs = [minhash_signature(s) for s in sets]
    t_sig = time.perf_counter() - t0

    t0 = time.perf_counter()
    approx = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            approx[i, j] = approx[j, i] = jaccard_minhash(sigs[i], sigs[j])
    t_mh = time.perf_counter() - t0

    # 3) LSH 分桶候选：对比两种分桶参数 (b=bands, r=rows/band)
    lsh_configs = [(16, 8), (64, 2)]
    lsh_cands = {}
    lsh_time = {}
    for b, r in lsh_configs:
        t0 = time.perf_counter()
        tables = build_lsh_tables(sigs, b=b, r=r)
        lsh_cands[(b, r)] = lsh_candidates(tables)
        lsh_time[(b, r)] = time.perf_counter() - t0
        print(f"  LSH(b={b}, r={r}) 建桶耗时={lsh_time[(b,r)]*1000:.2f}ms, 候选对={len(lsh_cands[(b,r)])}")

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
    res_lines.append(f"计时: 精确Jaccard矩阵={t_exact*1000:.3f}ms  MinHash签名={t_sig*1000:.3f}ms  "
                     f"MinHash比对={t_mh*1000:.3f}ms  "
                     f"LSH(b=16,r=8)建桶={lsh_time[(16,8)]*1000:.3f}ms  "
                     f"LSH(b=64,r=2)建桶={lsh_time[(64,2)]*1000:.3f}ms")

    # 4) 阈值扫描：混合口径（初版）与分层口径（修正后）对照
    thresholds = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    rows = []
    for t in thresholds:
        pred_exact = {(i, j) for i in range(n) for j in range(i + 1, n) if exact[i, j] >= t}
        pred_min = {(i, j) for i in range(n) for j in range(i + 1, n) if approx[i, j] >= t}
        rows.append(dict(
            t=t,
            mixed_exact=prf(GOLD_RELATED, pred_exact),
            mixed_min=prf(GOLD_RELATED, pred_min),
            strict_exact=prf(GOLD_NEAR_DUP, pred_exact),
            strict_min=prf(GOLD_NEAR_DUP, pred_min),
            n_pred_exact=len(pred_exact), n_pred_min=len(pred_min),
            same_event_hit=len(pred_exact & set(GOLD_SAME_EVENT)),
        ))

    print("\n=== 阈值对去重结果的影响（初版混合口径: gold = T1~T4 两两 = 6 对）===")
    print("阈值 | 精确Jaccard(P/R/F1)      | MinHash(P/R/F1)")
    res_lines.append("\n=== 阈值对去重结果的影响（混合口径: gold = T1~T4 两两）===")
    res_lines.append("阈值 | 精确Jaccard(P/R/F1) | MinHash(P/R/F1)")
    for r in rows:
        p1, r1, f1 = r["mixed_exact"][:3]
        p2, r2, f2 = r["mixed_min"][:3]
        print(f" {r['t']:.1f} | {p1:.3f}/{r1:.3f}/{f1:.3f}        | {p2:.3f}/{r2:.3f}/{f2:.3f}")
        res_lines.append(f" {r['t']:.1f} | {p1:.3f}/{r1:.3f}/{f1:.3f} | {p2:.3f}/{r2:.3f}/{f2:.3f}")

    print("\n=== 阈值对去重结果的影响（修正后分层口径: gold = 近重复对 T1-T2）===")
    print("阈值 | 精确Jaccard(P/R/F1)      | MinHash(P/R/F1)")
    res_lines.append("\n=== 分层口径（修正后）: gold = 近重复对 T1-T2（同事件改写对不计入 gold）===")
    res_lines.append("阈值 | 精确Jaccard(P/R/F1) | MinHash(P/R/F1)")
    for r in rows:
        p1, r1, f1 = r["strict_exact"][:3]
        p2, r2, f2 = r["strict_min"][:3]
        print(f" {r['t']:.1f} | {p1:.3f}/{r1:.3f}/{f1:.3f}        | {p2:.3f}/{r2:.3f}/{f2:.3f}")
        res_lines.append(f" {r['t']:.1f} | {p1:.3f}/{r1:.3f}/{f1:.3f} | {p2:.3f}/{r2:.3f}/{f2:.3f}")

    # LSH 去重识别：两种分桶参数对比 + 阈值回验
    print("\n=== LSH 分桶识别出的冗余候选（再用 MinHash 相似度回验）===")
    res_lines.append("\n=== LSH 分桶识别出的冗余候选 ===")
    for (b, r), cset in lsh_cands.items():
        print(f"--- LSH(b={b}, r={r}) 候选 {len(cset)} 对 ---")
        res_lines.append(f"--- LSH(b={b}, r={r}) 候选 {len(cset)} 对 ---")
        for i, j in sorted(cset):
            if approx[i, j] >= 0.2:
                status = "近重复"
            elif (i, j) in GOLD_SAME_EVENT or (j, i) in GOLD_SAME_EVENT:
                status = "候选但被阈值滤除(同事件改写，<0.2)"
            else:
                status = "误报(<0.2)"
            print(f"  T{i+1}-T{j+1}: MinHash 相似度={approx[i, j]:.4f} -> {status}")
            res_lines.append(f"  T{i+1}-T{j+1}: MinHash 相似度={approx[i,j]:.4f} -> {status}")

    # 5) 批量规模对运行时间的影响
    #    【M1 修正】初版计时口径不公平：LSH 列复用了前一阶段已生成的签名，
    #    既不含签名生成、也不含候选回验，而精确列是完整任务；且只跑一次、无波动信息。
    #    现在：
    #      - 分别报告「分阶段耗时」与「端到端耗时」
    #      - 端到端 = 从原始文本出发到给出重复判定对，三条路径都算全（含签名/索引构建与回验）
    #      - 每个规模重复 REPS 次，报告均值与标准差
    #      - 明确标注签名/索引是否计入
    print("\n=== 批量处理规模对运行时间的影响（真实标题语料，端到端口径）===")
    res_lines.append("\n=== 批量处理规模对运行时间的影响（真实标题语料）===")
    res_lines.append("口径说明：")
    res_lines.append("  精确端到端 = shingle 构建 + 全量两两精确 Jaccard + 阈值判定")
    res_lines.append("  MinHash端到端 = shingle 构建 + k=128 签名生成 + 全量两两签名比对 + 阈值判定")
    res_lines.append("  LSH端到端 = shingle 构建 + 签名生成 + 建桶 + 候选生成 + 候选回验 + 阈值判定")
    res_lines.append("  每个规模重复 %d 次，报告 中位数±标准差(ms)；shingle 构建为公共成本单列" % REPS)
    res_lines.append("规模 | shingle构建 | 精确(全量两两) | MinHash(签名+全量) | LSH(b16r8) | LSH(b64r2) | "
                     "全量对数 | b16r8候选 | b64r2候选 | LSH(b64r2)加速比")

    times = []
    corpus = []
    try:
        with open(os.path.join(DATA, "titles.txt"), encoding="utf-8") as f:
            corpus = [ln.strip() for ln in f if ln.strip()]
    except FileNotFoundError:
        pass
    if len(corpus) < 500:
        corpus = [c for c in cases] * 100

    VERIFY_TH = 0.2   # 候选回验阈值（与上面 LSH 明细一致）

    # 计时口径：Shingle 构建对三条路径是公共成本，单独计时、不计入"比较阶段"，
    # 避免用"谁多做了一次 shingle"来制造速度差异。
    # 三条路径都必须是「能给出最终重复判定对」的完整流程。
    def bench_exact(sh, m):
        """精确：全量两两 Jaccard + 阈值判定。"""
        pred = set()
        for i in range(m):
            si = sh[i]
            for j in range(i + 1, m):
                if jaccard_exact(si, sh[j]) >= VERIFY_TH:
                    pred.add((i, j))
        return pred, m * (m - 1) // 2

    def bench_minhash(sh, m):
        """MinHash：签名生成 + 全量两两签名比对 + 阈值判定。"""
        ss = [minhash_signature(x) for x in sh]
        np_ = m * (m - 1) // 2
        pred = set()
        for i in range(m):
            si = ss[i]
            for j in range(i + 1, m):
                if jaccard_minhash(si, ss[j]) >= VERIFY_TH:
                    pred.add((i, j))
        return pred, np_

    def bench_lsh(sh, m, b, r):
        """LSH：签名生成 + 建桶 + 候选生成 + 候选回验 + 阈值判定。"""
        ss = [minhash_signature(x) for x in sh]
        tables = build_lsh_tables(ss, b=b, r=r)
        cand = lsh_candidates(tables)
        pred = {(i, j) for (i, j) in cand if jaccard_minhash(ss[i], ss[j]) >= VERIFY_TH}
        return pred, len(cand)

    for m in [6, 50, 200, 500]:
        docs = corpus[:m]
        total_pairs = m * (m - 1) // 2
        # shingle 构建：公共成本，单独计时
        t0 = time.perf_counter()
        sh = [shingles(d) for d in docs]
        t_shingle = time.perf_counter() - t0

        te_l, tm_l, tl1_l, tl2_l = [], [], [], []
        n_exact_pairs = n_mh_pairs = 0
        c1 = c2 = 0
        # 计时期间关闭 GC，避免垃圾回收抖动污染小样本计时（n=500 时尤为明显）
        _gc_was = gc.isenabled()
        gc.disable()
        try:
            # 预热一次，排除首次调用的解释器/JIT 冷启动影响
            bench_exact(sh, m); bench_minhash(sh, m)
            bench_lsh(sh, m, 16, 8); bench_lsh(sh, m, 64, 2)
            for _ in range(REPS):
                t0 = time.perf_counter(); _, n_exact_pairs = bench_exact(sh, m); te_l.append(time.perf_counter() - t0)
                t0 = time.perf_counter(); _, n_mh_pairs = bench_minhash(sh, m); tm_l.append(time.perf_counter() - t0)
                t0 = time.perf_counter(); _, c1 = bench_lsh(sh, m, 16, 8); tl1_l.append(time.perf_counter() - t0)
                t0 = time.perf_counter(); _, c2 = bench_lsh(sh, m, 64, 2); tl2_l.append(time.perf_counter() - t0)
        finally:
            if _gc_was:
                gc.enable()
        # 取中位数作为主报值（比均值更抗离群），同时给出标准差
        te, tm = float(np.median(te_l)), float(np.median(tm_l))
        tl1, tl2 = float(np.median(tl1_l)), float(np.median(tl2_l))
        se, sm = float(np.std(te_l)), float(np.std(tm_l))
        s1, s2_ = float(np.std(tl1_l)), float(np.std(tl2_l))
        speedup_exact = te / tl2 if tl2 else float("inf")
        prune = 1 - c1 / total_pairs if total_pairs else 0.0
        times.append(dict(n=m, shingle_ms=t_shingle * 1000,
                          exact=te, exact_std=se, minhash=tm, minhash_std=sm,
                          lsh_16_8=tl1, lsh_16_8_std=s1, lsh_64_2=tl2, lsh_64_2_std=s2_,
                          # 原始逐次值（审计要求：只有 5 次时应公开每次原始值，而不只给中位数）
                          raw_exact_s=[float(x) for x in te_l],
                          raw_minhash_s=[float(x) for x in tm_l],
                          raw_lsh_16_8_s=[float(x) for x in tl1_l],
                          raw_lsh_64_2_s=[float(x) for x in tl2_l],
                          stat_note=("主报值 = 5 次重复的中位数；std = 总体标准差(np.std, ddof=0)；"
                                     "raw_*_s = 逐次原始秒数；计时期间 GC 关闭；"
                                     "shingle 构建为三条路径的公共成本，单独列出、不计入比较阶段"),
                          total_pairs=total_pairs, cand_16_8=c1, cand_64_2=c2,
                          prune_16_8=prune, speedup_lsh64_vs_exact=float(speedup_exact)))
        print(f"  文档数={m:4d} (shingle {t_shingle*1000:7.2f}ms): "
              f"精确 {te*1000:9.2f}±{se*1000:7.2f}ms/{n_exact_pairs}对 | "
              f"MinHash {tm*1000:9.2f}±{sm*1000:7.2f}ms | "
              f"LSHb64r2 {tl2*1000:9.2f}±{s2_*1000:7.2f}ms/{c2}候选 | "
              f"LSH加速 {speedup_exact:5.2f}x")
        res_lines.append(
            f"  {m:4d} | {t_shingle*1000:8.2f} | {te*1000:9.2f}±{se*1000:7.2f} | "
            f"{tm*1000:9.2f}±{sm*1000:7.2f} | {tl1*1000:9.2f}±{s1*1000:7.2f} | "
            f"{tl2*1000:9.2f}±{s2_*1000:7.2f} | {total_pairs} | {c1} | {c2} | {speedup_exact:.2f}")

    # 分阶段耗时（同一批签名，供拆解瓶颈；明确标注不含哪些部分）
    res_lines.append("\n=== 分阶段耗时拆解（n=500，同一批签名；用于定位瓶颈）===")
    docs500 = corpus[:500]
    s500 = [shingles(d) for d in docs500]
    t0 = time.perf_counter(); ss500 = [minhash_signature(x) for x in s500]
    t_sig500 = time.perf_counter() - t0
    t0 = time.perf_counter(); tb500 = build_lsh_tables(ss500, b=64, r=2)
    cand500 = lsh_candidates(tb500); t_build500 = time.perf_counter() - t0
    t0 = time.perf_counter()
    _ = [(i, j) for (i, j) in cand500 if jaccard_minhash(ss500[i], ss500[j]) >= VERIFY_TH]
    t_verify500 = time.perf_counter() - t0
    res_lines.append(f"  shingle 构建 + k=128 签名生成 = {t_sig500*1000:.2f} ms（一次性成本）")
    res_lines.append(f"  LSH(b=64,r=2) 建桶 + 候选生成 = {t_build500*1000:.2f} ms（不含签名生成）")
    res_lines.append(f"  候选回验（{len(cand500)} 对） = {t_verify500*1000:.2f} ms")
    print(f"  分阶段(n=500): 签名生成={t_sig500*1000:.2f}ms 建桶+候选={t_build500*1000:.2f}ms "
          f"回验({len(cand500)}对)={t_verify500*1000:.2f}ms")

    with open(os.path.join(OUT, "exp1_minhash_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(res_lines))

    # 6) 可视化
    # 图1：精确 vs MinHash 估计相似度散点 + 阈值-F1 曲线（两种口径）
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    xs = exact[np.triu_indices(n, 1)]
    ys = approx[np.triu_indices(n, 1)]
    ax[0].scatter(xs, ys, s=60, color="#C44E52")
    ax[0].plot([0, 1], [0, 1], "k--", alpha=0.6, label="y=x")
    for (i, j) in GOLD_SAME_EVENT:
        ax[0].annotate(f"T{i+1}-T{j+1}", (exact[i, j], approx[i, j]),
                       textcoords="offset points", xytext=(6, -10), fontsize=8, color="#555555")
    ax[0].set_xlabel("精确 Jaccard 相似度")
    ax[0].set_ylabel("MinHash 估计相似度")
    ax[0].set_title(f"MinHash 近似 vs 精确 N-gram Jaccard（k={K}）")
    ax[0].legend()
    ax[0].set_xlim(-0.02, 1.02)
    ax[0].set_ylim(-0.02, 1.02)
    ax[0].grid(alpha=0.3)

    ts = [r["t"] for r in rows]
    ax[1].plot(ts, [r["strict_exact"][2] for r in rows], "o-", label="精确 Jaccard（近重复金标准）")
    ax[1].plot(ts, [r["strict_min"][2] for r in rows], "s-", label="MinHash（近重复金标准）")
    ax[1].plot(ts, [r["mixed_exact"][2] for r in rows], "o--", alpha=0.55,
               label="精确 Jaccard（混合金标准）")
    ax[1].plot(ts, [r["mixed_min"][2] for r in rows], "s--", alpha=0.55,
               label="MinHash（混合金标准）")
    ax[1].set_xlabel("阈值")
    ax[1].set_ylabel("F1")
    ax[1].set_title("不同阈值与金标准口径下的去重 F1")
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "exp1_minhash_sim.png"), dpi=150)
    print("\n已保存:", os.path.join(FIG, "exp1_minhash_sim.png"))

    # 图2：批量规模端到端耗时（对数 y 轴，带标准差误差棒）
    fig2, ax2 = plt.subplots(figsize=(8.5, 5.2))
    m = [x["n"] for x in times]
    series = [("exact", "exact_std", "o-", "精确 Jaccard（端到端）"),
              ("minhash", "minhash_std", "s-", "MinHash（端到端）"),
              ("lsh_16_8", "lsh_16_8_std", "^-", "LSH b=16,r=8（端到端）"),
              ("lsh_64_2", "lsh_64_2_std", "v-", "LSH b=64,r=2（端到端）")]
    for key, skey, style, label in series:
        ax2.errorbar(m, [x[key] * 1000 for x in times],
                     yerr=[x[skey] * 1000 for x in times],
                     fmt=style, capsize=3, label=label)
    ax2.set_yscale("log")
    ax2.set_xlabel("文档数")
    ax2.set_ylabel("端到端耗时 (ms, 对数刻度)")
    ax2.set_title(f"批量规模对端到端耗时的影响（{REPS} 次重复，误差棒=标准差）")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3, which="both")
    fig2.tight_layout()
    fig2.savefig(os.path.join(FIG, "exp1_minhash_scaling.png"), dpi=150)
    print("已保存:", os.path.join(FIG, "exp1_minhash_scaling.png"))

    # ---- 结构化汇总（供报告生成器读取，杜绝报告里硬编码数字）----
    summary = {
        "config": {"k": K, "prime": P, "seed": SEED, "reps": REPS,
                   "shingle": "词级 1-gram ∪ 2-gram", "verify_threshold": VERIFY_TH,
                   "lsh_configs": [[16, 8], [64, 2]]},
        "gold": {"near_dup": len(GOLD_NEAR_DUP), "same_event": len(GOLD_SAME_EVENT),
                 "mixed_related": len(GOLD_RELATED),
                 "near_dup_pairs": [f"T{i+1}-T{j+1}" for i, j in GOLD_NEAR_DUP],
                 "same_event_pairs": [f"T{i+1}-T{j+1}" for i, j in GOLD_SAME_EVENT]},
        "n_cases": n,
        "exact_matrix": [[round(float(exact[i, j]), 6) for j in range(n)] for i in range(n)],
        "minhash_matrix": [[round(float(approx[i, j]), 6) for j in range(n)] for i in range(n)],
        "case_pairs": [{"pair": f"T{i+1}-T{j+1}", "jaccard": round(float(exact[i, j]), 6),
                        "minhash": round(float(approx[i, j]), 6),
                        "abs_err": round(abs(float(approx[i, j]) - float(exact[i, j])), 6),
                        "in_lsh_candidate": bool((i, j) in lsh_cands[(64, 2)])}
                       for i in range(n) for j in range(i + 1, n)],
        "minhash_error": {"mae": float(err.mean()), "max": float(err.max()),
                          "std": float(err.std())},
        "thresholds": [{"t": r["t"],
                        "mixed_exact": list(r["mixed_exact"]), "mixed_min": list(r["mixed_min"]),
                        "strict_exact": list(r["strict_exact"]), "strict_min": list(r["strict_min"]),
                        "n_pred_exact": r["n_pred_exact"], "n_pred_min": r["n_pred_min"]}
                       for r in rows],
        "single_run_timing_ms": {"exact_jaccard_matrix": t_exact * 1000,
                                 "minhash_sig": t_sig * 1000,
                                 "minhash_compare": t_mh * 1000,
                                 "lsh_16_8_build": lsh_time[(16, 8)] * 1000,
                                 "lsh_64_2_build": lsh_time[(64, 2)] * 1000},
        "lsh_candidates": {f"b{b}_r{r}": {"n": len(cset),
                                          "pairs": [f"T{i+1}-T{j+1}" for i, j in sorted(cset)]}
                           for (b, r), cset in lsh_cands.items()},
        "scaling_end2end_ms": times,
        "stage_breakdown_500_ms": {"shingle_and_signature": t_sig500 * 1000,
                                   "lsh_build_and_candidates": t_build500 * 1000,
                                   "candidate_verify": t_verify500 * 1000,
                                   "n_candidates": len(cand500)},
    }
    with open(os.path.join(OUT, "results_summary_minhash.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print("已落盘: out/results_summary_minhash.json")


if __name__ == "__main__":
    main()
