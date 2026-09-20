# -*- coding: utf-8 -*-
"""
实验题目二(2)：基于加权 SimHash 的网页新闻相似度计算
要求：
  - 20 篇网页新闻（同一事件不同报道 / 转载改写 / 完全不同主题，txt 保存）
  - 传统 SimHash 基础上引入 TF-IDF 权重：高 TF-IDF 词加权、停用词降权
  - 批量计算 64 位加权 SimHash 指纹，海明距离两两计算相似度，距离<=3 判定近似重复
  - 对比传统等权 SimHash 与 TF-IDF 加权 SimHash：查准率/查全率/F1

【相对初版（commit 143c288）的修正】—— 逐条对应复现审计意见
  S2 权重对照不再混杂：初版两种实现的投票单位都不干净——
     等权分支 `w = Counter(ts)[t]` 且按词元出现逐次投票，一个出现 m 次的词总贡献是 m²；
     加权分支同样按词元逐次累加 `TF-IDF`（矩阵里已含 TF），也是 m²·IDF。
     现在把「投票单位」与「权重来源」拆成两个正交维度，给出 5 个可解释的方案：
       A 等权每词元        w=1        ，投票单位=词元出现
       B TF 每词元         w=count(t) ，投票单位=词元出现   → 总贡献 m²
       C TF 每唯一词       w=count(t) ，投票单位=唯一词     → 总贡献 m
       D TF-IDF 每唯一词   w=tfidf    ，投票单位=唯一词     → 标准做法
       E TF-IDF 每唯一词+停用词降权 = 本实验推荐方案
     并保留 F「TF-IDF 每词元+停用词降权」= 初版方案，作为消融对照。
     这样等权→TF→TF-IDF→停用词降权的每一步增量都能单独看出来。
  S2b 大小写：查询特征表时统一 `t.lower()`，与 TfidfVectorizer(lowercase=True) 对齐
     （初版用原始大小写查 `feat_index`，含英文的 token 会查不到而权重置 0）。
  S3 标题级 / 正文级分开评估：初版把 `title + " " + body` 拼成一个字符串，
     而转载改写簇是「换标题 + 正文基本不变」，导致近似重复对主要靠标题相似被检出。
     现在分别给出 标题、正文、标题+正文 三种文本范围的指标。
  S3b 元信息污染：`parse_doc` 按首个空行切分，`group=` / `rewrite=` 不再进入正文。
  M6 分析文字不再写死在报告里：把漏检组别分布、精度是否随阈值变化等结论所需的
     原始计数全部落盘到 out/results_summary.json，由报告生成器读取。
"""
import os
import re
import json
import hashlib
import itertools
import numpy as np
import jieba
from collections import Counter, defaultdict
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
STOP_SCALE = 0.2   # 停用词降权系数

# 三层金标准
NEAR_DUP_GROUPS = {"R1", "R2"}        # 转载改写簇 → 近似重复（正样本）
SAME_EVENT_GROUPS = {"D1", "D2"}      # 同一事件不同报道（事件相同、文本迥异）
UNRELATED_GROUPS = {"D3", "U1", "U2", "U3"}   # D3 经复核为标注错误，实为不同事件


# ------------------- 工具 -------------------
def parse_doc(raw):
    """按首个空行严格切分元信息与正文（修正元信息污染）。"""
    head, _, body = raw.partition("\n\n")
    meta = {}
    for ln in head.split("\n"):
        if "=" in ln:
            k, _, v = ln.partition("=")
            meta[k.strip()] = v.strip()
    return meta, body.strip()


def load_news20():
    """读取 data/news20/*.txt + manifest.json 分组标签。"""
    docs = []
    manifest = json.load(open(os.path.join(DATA, "manifest.json"), encoding="utf-8"))
    for fn in sorted(os.listdir(DATA)):
        if not fn.endswith(".txt"):
            continue
        idx = int(fn[:3])
        with open(os.path.join(DATA, fn), encoding="utf-8") as f:
            meta, body = parse_doc(f.read())
        docs.append({"idx": idx, "title": meta.get("title", ""), "body": body,
                     "group": manifest["doc"][str(idx)]["group"],
                     "cat": manifest["doc"][str(idx)]["cat"]})
    docs.sort(key=lambda d: d["idx"])
    return docs


def tokenize(text):
    """jieba 分词：保留停用词（供"停用词降权"使用），仅去除纯标点/数字。"""
    return [w.strip() for w in jieba.lcut(text)
            if w.strip() and not re.fullmatch(r"[\d\W_]+", w.strip())]


def term_hash_64(term):
    """词 -> 64 位确定性哈希（取 md5 前 16 个十六进制字符）。"""
    return int(hashlib.md5(term.encode("utf-8")).hexdigest()[:16], 16)


def simhash_fingerprint(terms, weights):
    """SimHash 指纹：v[64] 按 term 哈希各位累加 ±weight，符号位生成指纹。"""
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
    """返回 (P, R, F1, TP, FP, FN)。分母为空时取 0（无预测即无贡献）。"""
    gold, pred = set(gold), set(pred)
    tp = len(gold & pred)
    fp = len(pred - gold)
    fn = len(gold - pred)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1, tp, fp, fn


def group_pairs(docs, groups):
    out = []
    for g in sorted(groups):
        ids = [i for i, d in enumerate(docs) if d["group"] == g]
        out.extend(itertools.combinations(ids, 2))
    return out


# ------------------- 指纹构造：投票单位 × 权重来源 -------------------
def make_fingerprints(terms_per_doc, tfidf_rows, feat_index,
                      unit="unique", weight="tfidf", stop_scale=1.0):
    """
    unit:   "token"  = 按词元出现逐次投票；"unique" = 每个唯一词只投一次
    weight: "one"    = 等权 1；"tf" = 词频；"tfidf" = TF-IDF
    stop_scale: 命中停用词表时对权重乘的系数（1.0 表示不降权）

    把 term 小写后再查 feat_index，与 TfidfVectorizer(lowercase=True) 对齐。
    """
    fps = []
    for di, ts in enumerate(terms_per_doc):
        cnt = Counter(ts)
        if unit == "unique":
            seq = list(cnt.keys())
        else:
            seq = ts
        wl = []
        for t in seq:
            if weight == "one":
                w = 1.0
            elif weight == "tf":
                w = float(cnt[t])
            else:                                   # tfidf
                w = float(tfidf_rows[di][feat_index[t.lower()]]) \
                    if t.lower() in feat_index else 0.0
            if t in STOPWORDS:
                w *= stop_scale
            wl.append(w)
        fps.append(simhash_fingerprint(seq, wl))
    return fps


# 干净的 2×3 因子对照（单位 × 权重），外加停用词降权开关。
# 之前的“等权 vs TF-IDF”之所以看起来 TF-IDF 更好，是因为等权基线本身被写坏了
# （每词元投票 × 权重取该词总词频 ⇒ 总贡献 m²）。拆开之后结论完全反过来。
SCHEME_GRID = [
    ("A1 每词元 · 等权(1)", dict(unit="token", weight="one")),
    ("A2 每词元 · TF", dict(unit="token", weight="tf")),
    ("A3 每词元 · TF-IDF", dict(unit="token", weight="tfidf")),
    ("B1 每唯一词 · 等权(1)", dict(unit="unique", weight="one")),
    ("B2 每唯一词 · TF", dict(unit="unique", weight="tf")),
    ("B3 每唯一词 · TF-IDF", dict(unit="unique", weight="tfidf")),
]
SCHEMES = SCHEME_GRID + [
    ("B3s 每唯一词 · TF-IDF + 停用词降权", dict(unit="unique", weight="tfidf", stop_scale=STOP_SCALE)),
    ("A3s 每词元 · TF-IDF + 停用词降权(初版方案)", dict(unit="token", weight="tfidf", stop_scale=STOP_SCALE)),
]
RECOMMENDED = "B1 每唯一词 · 等权(1)"
BASELINE_V1 = "A3s 每词元 · TF-IDF + 停用词降权(初版方案)"


def main():
    docs = load_news20()
    n = len(docs)
    print(f"加载 {n} 篇新闻")

    # 三个文本范围（S3）
    scopes = {
        "标题": [d["title"] for d in docs],
        "正文": [d["body"] for d in docs],
        "标题+正文": [d["title"] + " " + d["body"] for d in docs],
    }
    terms_by_scope = {k: [tokenize(t) for t in v] for k, v in scopes.items()}

    # 金标准
    gold_near = group_pairs(docs, NEAR_DUP_GROUPS)
    gold_same_event = group_pairs(docs, SAME_EVENT_GROUPS)
    gold_all_same_group = [(i, j) for i in range(n) for j in range(i + 1, n)
                           if docs[i]["group"] == docs[j]["group"]]
    print(f"金标准：改写簇近似重复对={len(gold_near)}  同事件不同报道对={len(gold_same_event)}  "
          f"初版混合口径(所有同组对)={len(gold_all_same_group)}")

    # 组内相似度自检
    def jac(a, b, scope="标题+正文"):
        ta, tb = set(terms_by_scope[scope][a]), set(terms_by_scope[scope][b])
        return len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0

    group_stats = {}
    print("\n[分组内词级 Jaccard（分层依据）]")
    for g in ("R1", "R2", "D1", "D2", "D3"):
        ids = [i for i, d in enumerate(docs) if d["group"] == g]
        vals = [jac(a, b) for a, b in itertools.combinations(ids, 2)]
        group_stats[g] = {"n_docs": len(ids), "vals": vals,
                          "mean": float(np.mean(vals)) if vals else None}
        print(f"  {g}: " + " ".join(f"{v:.4f}" for v in vals))
    near_vals = [jac(a, b) for a, b in gold_near]
    se_vals = [jac(a, b) for a, b in gold_same_event]
    print(f"  改写簇 R1/R2 组内平均 {np.mean(near_vals):.4f} (min {min(near_vals):.4f})")
    print(f"  同事件簇 D1/D2 组内平均 {np.mean(se_vals):.4f} (max {max(se_vals):.4f})")
    separated = bool(min(near_vals) > max(se_vals))
    print(f"  -> 两簇{'完全分离' if separated else '存在重叠'}；"
          f"'近似重复'与'同事件不同报道'必须分层评估")
    print("  [D3 标注复核] 三条标题：")
    for d in docs:
        if d["group"] == "D3":
            print(f"    {d['idx']:02d}: {d['title']}")
    print("    -> 15 号为女子现代五项团体夺金，16/17 号为男子铁人三项摘银，属不同事件；")
    print("       故 D3 不计入近似重复正样本（原始 manifest 保留不动，仅在评估时排除）。")

    # ---------- 主实验：在「标题+正文」范围上跑 6 个方案 ----------
    scope = "标题+正文"
    tdoc = terms_by_scope[scope]
    vectorizer = TfidfVectorizer(ngram_range=(1, 1), token_pattern=r"(?u)\b\w+\b")
    X = vectorizer.fit_transform([" ".join(ts) for ts in tdoc]).toarray()
    feats = list(vectorizer.get_feature_names_out())
    feat_index = {f: i for i, f in enumerate(feats)}
    n_lower_mismatch = sum(1 for t in {t for ts in tdoc for t in ts} if t != t.lower())
    print(f"\nTF-IDF 矩阵 {X.shape}；含大写字符的唯一词 {n_lower_mismatch} 个"
          f"（查询时统一 lower() 对齐特征名）")

    res = {}
    for name, kw in SCHEMES:
        fps = make_fingerprints(tdoc, X, feat_index, **kw)
        dist = np.zeros((n, n), dtype=int)
        for i, j in itertools.combinations(range(n), 2):
            dist[i, j] = dist[j, i] = hamming(fps[i], fps[j])
        pred = {(i, j) for i, j in itertools.combinations(range(n), 2) if dist[i, j] <= HAM_TH}
        res[name] = {"pred": pred, "dist": dist,
                     "strict": prf(gold_near, pred),
                     "mixed": prf(gold_all_same_group, pred)}

    print(f"\n=== 权重方案对照（{scope}，海明距离<={HAM_TH}，正样本=改写簇 {len(gold_near)} 对）===")
    print(f"{'方案':<34}{'P':>8}{'R':>8}{'F1':>8}{'TP':>5}{'FP':>5}{'FN':>5}")
    for name, _ in SCHEMES:
        p, r, f1, tp, fp, fn = res[name]["strict"]
        print(f"{name:<34}{p:>8.3f}{r:>8.3f}{f1:>8.3f}{tp:>5}{fp:>5}{fn:>5}")

    # ---------- 文本范围对照（用推荐方案） ----------
    scope_rows = []
    _rec_kw = dict([kw for nm, kw in SCHEMES if nm == RECOMMENDED][0])
    print(f"\n=== 文本范围对照（推荐方案 {RECOMMENDED}）===")
    for sc in ("标题", "正文", "标题+正文"):
        td = terms_by_scope[sc]
        v = TfidfVectorizer(ngram_range=(1, 1), token_pattern=r"(?u)\b\w+\b")
        Xs = v.fit_transform([" ".join(ts) for ts in td]).toarray()
        fi = {f: i for i, f in enumerate(v.get_feature_names_out())}
        fps = make_fingerprints(td, Xs, fi,
                                unit=_rec_kw.get("unit", "unique"),
                                weight=_rec_kw.get("weight", "one"),
                                stop_scale=_rec_kw.get("stop_scale", 1.0))
        pred = {(i, j) for i, j in itertools.combinations(range(n), 2)
                if hamming(fps[i], fps[j]) <= HAM_TH}
        m = prf(gold_near, pred)
        # 标题语料特征数太少，指纹可能“全部撞在一起”或“一个都不撞”，
        # 此时 P/R 的分母为 0，必须如实标注为“无判定”，不能报成 0 分精度。
        note = "无任何判定(FP=FN=0)" if len(pred) == 0 else ("存在误报" if m[4] else "零误报")
        scope_rows.append({"scope": sc, "P": m[0], "R": m[1], "F1": m[2],
                           "TP": m[3], "FP": m[4], "FN": m[5],
                           "n_pred": len(pred), "note": note})
        print(f"  {sc:<8} P={m[0]:.3f} R={m[1]:.3f} F1={m[2]:.3f} "
              f"(TP={m[3]} FP={m[4]} FN={m[5]}) 预测对数={len(pred)} [{note}]")

    # ---------- 漏检组别分布（结论必须由数据决定）----------
    fn_groups = defaultdict(int)
    for i, j in gold_near:
        if (i, j) not in res[RECOMMENDED]["pred"]:
            fn_groups[docs[i]["group"]] += 1
    print(f"\n[推荐方案 {RECOMMENDED} 漏检对的分组分布] {dict(fn_groups) or '无漏检'}")
    for name, _ in SCHEMES:
        miss = defaultdict(int)
        for i, j in gold_all_same_group:
            if (i, j) not in res[name]["pred"]:
                miss[docs[i]["group"]] += 1
        print(f"  {name:<34} 按初版金标准的漏检组别: {dict(miss) or '无'}")

    # ---------- 阈值扫描 ----------
    sweep = {}
    for name, kw in SCHEMES:
        rows = []
        for th in range(0, 11):
            pred = {(i, j) for i, j in itertools.combinations(range(n), 2)
                    if res[name]["dist"][i, j] <= th}
            rows.append((th, prf(gold_near, pred), prf(gold_all_same_group, pred)))
        sweep[name] = rows

    print(f"\n=== 海明距离阈值扫描（正样本=改写簇）===")
    hdr = " 阈值 |" + "".join(f" {n.split()[0]:>9}" for n, _ in SCHEMES)
    print(hdr)
    for k in range(11):
        line = f"  {k:2d}  |" + "".join(f" {sweep[n][k][1][2]:>9.3f}" for n, _ in SCHEMES)
        print(line)
    # 精度是否随阈值变化（M6：不再凭印象写“召回换查准”）
    prec_by_th = {n: [round(sweep[n][k][1][0], 6) for k in range(11)] for n, _ in SCHEMES}
    prec_constant = {n: len(set(v)) == 1 for n, v in prec_by_th.items()}

    # ---------- 检出明细 ----------
    detail = {}
    for name, _ in SCHEMES:
        items = []
        for i, j in sorted(res[name]["pred"]):
            gi, gj = docs[i]["group"], docs[j]["group"]
            if gi == gj and gi in NEAR_DUP_GROUPS:
                tag = "命中(改写簇)"
            elif gi == gj and gi in SAME_EVENT_GROUPS:
                tag = "同组(同事件不同报道)"
            elif gi == gj:
                tag = "同组(D3标注待核)"
            else:
                tag = "误报(跨组)"
            items.append({"i": i + 1, "j": j + 1, "gi": gi, "gj": gj,
                          "dist": int(res[name]["dist"][i, j]), "tag": tag})
        detail[name] = items
    for name in (RECOMMENDED, BASELINE_V1):
        print(f"\n【{name}】判定为近似重复的文本对：")
        for it in detail[name][:12]:
            print(f"  {it['i']:02d}-{it['j']:02d} [{it['gi']}vs{it['gj']}] d={it['dist']} {it['tag']}")
        if len(detail[name]) > 12:
            print(f"  …（共 {len(detail[name])} 对）")

    # ---------- 落盘：文本结果 ----------
    lines = []
    lines.append(f"数据集: {n} 篇新闻（转载改写簇 R1/R2 + 同一事件不同报道 D1/D2 + 完全不同主题 U1~U3）")
    lines.append(f"金标准: 改写簇近似重复对={len(gold_near)}  同事件不同报道对={len(gold_same_event)}  "
                 f"初版混合口径(所有同组对)={len(gold_all_same_group)}")
    lines.append(f"判定规则: 64 位指纹海明距离 <= {HAM_TH}")
    lines.append("")
    lines.append("注 1: D3 组经人工复核为标注错误——15 号=女子现代五项团体夺金，")
    lines.append("      16/17 号=男子铁人三项摘银，分属不同事件，故不计入近似重复正样本。")
    lines.append("注 2: 初版实现存在两处口径问题，本版已修正并在下方给出对照：")
    lines.append("      (a) 投票单位不干净：按词元出现逐次投票，且等权分支权重仍取该词总词频，")
    lines.append("          使一个出现 m 次的词总贡献为 m^2；现已拆成 方案A~F 单独观察每一步增量。")
    lines.append("      (b) 特征表查询未统一大小写：含英文的 token 会查不到而权重置 0；现统一 lower()。")
    lines.append("")
    lines.append("=== 分组内词级 Jaccard（分层依据）===")
    for g, st in group_stats.items():
        vals = " ".join(f"{v:.4f}" for v in st["vals"])
        mean = f"{st['mean']:.4f}" if st["mean"] is not None else "-"
        lines.append(f"  {g} (n={st['n_docs']}): {vals} | 平均 {mean}")
    lines.append(f"  改写簇平均 {np.mean(near_vals):.4f} (min {min(near_vals):.4f})")
    lines.append(f"  同事件簇平均 {np.mean(se_vals):.4f} (max {max(se_vals):.4f})")
    lines.append(f"  两簇是否完全分离: {separated}")
    lines.append("")
    lines.append(f"=== 权重方案对照（文本范围={scope}，距离<={HAM_TH}，正样本=改写簇 {len(gold_near)} 对）===")
    lines.append(f"{'方案':<34}{'P':>8}{'R':>8}{'F1':>8}{'TP':>5}{'FP':>5}{'FN':>5}")
    for name, _ in SCHEMES:
        p, r, f1, tp, fp, fn = res[name]["strict"]
        lines.append(f"{name:<34}{p:>8.3f}{r:>8.3f}{f1:>8.3f}{tp:>5}{fp:>5}{fn:>5}")
    lines.append("")
    lines.append("（初版混合口径：正样本=所有同组对，仅列对照）")
    for name, _ in SCHEMES:
        p, r, f1, tp, fp, fn = res[name]["mixed"]
        lines.append(f"{name:<34}P={p:.3f} R={r:.3f} F1={f1:.3f} TP={tp} FP={fp} FN={fn}")
    lines.append("")
    lines.append(f"=== 文本范围对照（推荐方案：{RECOMMENDED}）===")
    for sr in scope_rows:
        lines.append(f"  {sr['scope']:<8} P={sr['P']:.3f} R={sr['R']:.3f} F1={sr['F1']:.3f} "
                     f"TP={sr['TP']} FP={sr['FP']} FN={sr['FN']} "
                     f"预测对数={sr['n_pred']} [{sr['note']}]")
    lines.append("")
    lines.append("=== 漏检组别分布 ===")
    lines.append(f"  推荐方案 {RECOMMENDED} 相对改写簇正样本的漏检: {dict(fn_groups) or '无漏检'}")

    def miss_by_group(scheme, gold_pairs):
        m = defaultdict(int)
        for i, j in gold_pairs:
            if (i, j) not in res[scheme]["pred"]:
                m[docs[i]["group"]] += 1
        return m

    lines.append(f"  初版方案 {BASELINE_V1} 相对改写簇正样本的漏检: "
                 f"{dict(miss_by_group(BASELINE_V1, gold_near)) or '无漏检'}")
    for name, _ in SCHEMES:
        miss = defaultdict(int)
        for i, j in gold_all_same_group:
            if (i, j) not in res[name]["pred"]:
                miss[docs[i]["group"]] += 1
        lines.append(f"  {name:<34} 按初版金标准漏检组别: {dict(miss) or '无'}")
    lines.append("")
    lines.append("=== 海明距离阈值扫描（正样本=改写簇，列=各方案 F1）===")
    lines.append(hdr)
    for k in range(11):
        lines.append(f"  {k:2d}  |" + "".join(f" {sweep[nm][k][1][2]:>9.3f}" for nm, _ in SCHEMES))
    lines.append("")
    lines.append("=== 阈值扫描：查准率 P（用于判断是否存在“召回换查准”）===")
    for name, _ in SCHEMES:
        lines.append(f"  {name:<34} P(阈值0..10) = " +
                     " ".join(f"{v:.3f}" for v in prec_by_th[name]) +
                     f"  | 是否恒定={prec_constant[name]}")
    lines.append("")
    for name, _ in SCHEMES:
        lines.append(f"--- {name} 检出的重复对（共 {len(detail[name])} 对）---")
        for it in detail[name]:
            lines.append(f"  {it['i']:02d}-{it['j']:02d} [{it['gi']}vs{it['gj']}] "
                         f"d={it['dist']} {it['tag']}")
    with open(os.path.join(OUT, "exp2_simhash_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # ---------- 落盘：结构化汇总（供报告生成器读取，杜绝报告硬编码）----------
    summary = {
        "n_docs": n,
        "bits": BITS,
        "ham_th": HAM_TH,
        "stop_scale": STOP_SCALE,
        "n_pairs_total": n * (n - 1) // 2,
        "gold": {"near_dup": len(gold_near), "same_event": len(gold_same_event),
                 "mixed_all_same_group": len(gold_all_same_group),
                 "near_dup_groups": sorted(NEAR_DUP_GROUPS),
                 "same_event_groups": sorted(SAME_EVENT_GROUPS),
                 "unrelated_groups": sorted(UNRELATED_GROUPS)},
        "group_stats": group_stats,
        "separated": separated,
        "scope": scope,
        "n_lower_mismatch_tokens": n_lower_mismatch,
        "schemes": [{"name": nm, "config": kw,
                     "strict": dict(zip(["P", "R", "F1", "TP", "FP", "FN"], res[nm]["strict"])),
                     "mixed": dict(zip(["P", "R", "F1", "TP", "FP", "FN"], res[nm]["mixed"])),
                     "n_pred": len(res[nm]["pred"]),
                     "n_fp_cross_group": sum(1 for i, j in res[nm]["pred"]
                                             if docs[i]["group"] != docs[j]["group"])}
                    for nm, kw in SCHEMES],
        "scope_rows": scope_rows,
        "fn_groups_recommended": dict(fn_groups),
        "precision_by_threshold": prec_by_th,
        "precision_constant": prec_constant,
        "sweep_f1": {nm: [round(sweep[nm][k][1][2], 6) for k in range(11)] for nm, _ in SCHEMES},
        "recommended": RECOMMENDED,
        "baseline_v1": BASELINE_V1,
    }
    with open(os.path.join(OUT, "results_summary_simhash.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print("\n已落盘: out/exp2_simhash_results.txt, out/results_summary_simhash.json")

    # ---------- 可视化 ----------
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4))
    show = [nm for nm, _ in SCHEME_GRID] + [RECOMMENDED]
    x = np.arange(len(show))
    wd = 0.26
    for k, (m, lbl) in enumerate(zip(["P", "R", "F1"], ["查准率 P", "查全率 R", "F1"])):
        vals = [res[nm]["strict"][k] for nm in show]
        bars = axes[0].bar(x + (k - 1) * wd, vals, wd, label=lbl)
        for b, v in zip(bars, vals):
            axes[0].text(b.get_x() + b.get_width() / 2, v + 0.015, f"{v:.2f}",
                         ha="center", fontsize=7.5)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([nm.split()[0] + "\n" + nm.split("·")[1][:8] for nm in show], fontsize=8)
    axes[0].set_ylim(0, 1.15)
    axes[0].set_title(f"权重方案的增量效果（距离≤{HAM_TH}，正样本=改写簇 {len(gold_near)} 对）")
    axes[0].legend(fontsize=8)
    axes[0].grid(axis="y", alpha=0.3)

    for nm in show:
        axes[1].plot(range(11), [sweep[nm][k][1][2] for k in range(11)],
                     "o-", ms=3.5, label=nm.split()[0])
    axes[1].axvline(HAM_TH, color="gray", ls="--", alpha=0.7, label=f"作业规定阈值={HAM_TH}")
    axes[1].set_xlabel("海明距离阈值")
    axes[1].set_ylabel("F1")
    axes[1].set_title("阈值对 F1 的影响（各方案）")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "exp2_simhash_prf.png"), dpi=150)
    print("已保存:", os.path.join(FIG, "exp2_simhash_prf.png"))


if __name__ == "__main__":
    main()
