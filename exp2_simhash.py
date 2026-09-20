# -*- coding: utf-8 -*-
"""
实验题目二(2)：基于加权 SimHash 的网页新闻相似度计算
要求：
  - 20 篇网页新闻（同一事件不同报道 / 转载改写 / 完全不同主题，txt 保存）
  - 传统 SimHash 基础上引入 TF-IDF 权重：高 TF-IDF 词加权、停用词降权
  - 批量计算 64 位加权 SimHash 指纹，海明距离两两计算相似度，距离<=3 判定近似重复
  - 对比传统等权 SimHash 与 TF-IDF 加权 SimHash：查准率/查全率/F1

【相对初版的修正】（详见 out/AUDIT_NOTES.md）
  修正D 元信息泄漏进正文：初版 `raw.split("\\n", 3)[3]` 取正文，会把 news20 才有的
       `group=` / `rewrite=` 两行当成正文词参与分词与指纹计算。现改为按首个空行严格切分。
  修正E 金标准分层：初版把所有同组文档对都当“近似重复”。但实测组内词级 Jaccard 明显分两档——
       改写簇 R1/R2 为 0.96~0.99（真·近似重复），同事件不同报道 D1/D2 仅 0.11~0.23（事件相同、
       文本迥异）；而 D3 组的 15 号（女子现代五项团体夺金）与 16/17 号（男子铁人三项摘银）
       其实是**不同事件**，原本的 D3 标注有误。
       因此本脚本把金标准拆成三层，并同时输出“初版口径”与“修正口径”两套指标，
       以免单一数字掩盖标注问题。
  说明F 权重口径：加权 SimHash 按“词元出现次数”累加 TF-IDF 权重（与经典 SimHash 的 TF 加权
       递增一致），其隐含效果是权重随词频近似二次增长。本脚本额外给出“按唯一词加权”的
       消融对照（唯一词版），用于说明该设计选择对指标的影响。
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
STOP_SCALE = 0.2   # 停用词降权系数

# 三层金标准（修正E）
#   NEAR_DUP_GROUPS  改写簇：同簇内两两视为“近似重复”= 金标准正样本
#   SAME_EVENT_GROUPS 同事件不同报道：事件相同但文本迥异，不计入正样本（另计“事件级召回”）
#   UNRELATED_GROUPS 完全不同主题（含标注有误、实为不同事件的 D3）
NEAR_DUP_GROUPS = {"R1", "R2"}
SAME_EVENT_GROUPS = {"D1", "D2"}
UNRELATED_GROUPS = {"D3", "U1", "U2", "U3"}


# ------------------- 工具 -------------------
def parse_doc(raw):
    """按首个空行严格切分元信息与正文（修正D）。"""
    head, _, body = raw.partition("\n\n")
    meta = {}
    for ln in head.split("\n"):
        if "=" in ln:
            k, _, v = ln.partition("=")
            meta[k.strip()] = v.strip()
    return meta, body.strip()


def load_news20():
    """读取 data/news20/*.txt + manifest.json 分组标签"""
    docs = []
    manifest = json.load(open(os.path.join(DATA, "manifest.json"), encoding="utf-8"))
    for fn in sorted(os.listdir(DATA)):
        if not fn.endswith(".txt"):
            continue
        idx = int(fn[:3])
        with open(os.path.join(DATA, fn), encoding="utf-8") as f:
            meta, body = parse_doc(f.read())
        title = meta.get("title", "")
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
    """返回 (P, R, F1, TP, FP, FN)。分母为空时该指标定义为 0（无预测即无贡献）。"""
    gold, pred = set(gold), set(pred)
    tp = len(gold & pred)
    fp = len(pred - gold)
    fn = len(gold - pred)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1, tp, fp, fn


def group_pairs(docs, groups):
    """组内两两组合（组大小 1 的自动跳过）。"""
    out = []
    for g in sorted(groups):
        ids = [i for i, d in enumerate(docs) if d["group"] == g]
        out.extend(itertools.combinations(ids, 2))
    return out


def main():
    docs = load_news20()
    n = len(docs)
    print(f"加载 {len(docs)} 篇新闻")

    # jieba 分词
    doc_terms = [tokenize(d["text"]) for d in docs]
    seg_docs = [" ".join(ts) for ts in doc_terms]

    # TF-IDF 权重矩阵（在 20 篇上训练）
    vectorizer = TfidfVectorizer(ngram_range=(1, 1), token_pattern=r"(?u)\b\w+\b")
    X = vectorizer.fit_transform(seg_docs).toarray()
    feats = vectorizer.get_feature_names_out()
    feat_index = {f: i for i, f in enumerate(feats)}

    # 词在文档内的 TF（传统等权 SimHash 使用）
    tf_lists = [Counter(ts) for ts in doc_terms]

    # ---------- 三种权重方案 ----------
    # (a) TF-IDF 加权（按词元出现次数，停用词降权）—— 初版方案
    fp_w = []
    for di, ts in enumerate(doc_terms):
        wlist = []
        for t in ts:
            w = float(X[di, feat_index[t.lower()]]) if t.lower() in feat_index else 0.0
            if t in STOPWORDS:
                w *= STOP_SCALE          # 停用词降权
            wlist.append(w)
        fp_w.append(simhash_fingerprint(ts, wlist))

    # (b) 传统等权 SimHash（词频权重）
    fp_e = []
    for di, ts in enumerate(doc_terms):
        wlist = [float(tf_lists[di].get(t, 1)) for t in ts]
        fp_e.append(simhash_fingerprint(ts, wlist))

    # (c) 消融对照：按唯一词取 TF-IDF 权重（不做词频放大，说明F）
    fp_u = []
    for di, ts in enumerate(doc_terms):
        uniq = list(dict.fromkeys(ts))
        wlist = []
        for t in uniq:
            w = float(X[di, feat_index[t.lower()]]) if t.lower() in feat_index else 0.0
            if t in STOPWORDS:
                w *= STOP_SCALE
            wlist.append(w)
        fp_u.append(simhash_fingerprint(uniq, wlist))

    # ---------- 三层金标准（修正E）----------
    gold_near = group_pairs(docs, NEAR_DUP_GROUPS)        # 近似重复（正样本）
    gold_same_event = group_pairs(docs, SAME_EVENT_GROUPS)  # 同事件不同报道
    gold_all_same_group = [(i, j) for i in range(n) for j in range(i + 1, n)
                           if docs[i]["group"] == docs[j]["group"]]  # 初版口径

    print(f"金标准：改写簇近似重复对={len(gold_near)}  同事件不同报道对={len(gold_same_event)}  "
          f"初版混合口径（所有同组对）={len(gold_all_same_group)}")

    # 组内相似度分布，作为分层依据的证据
    import numpy as _np
    def jac(a, b):
        sa, sb = set(doc_terms[a]), set(doc_terms[b])
        return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0
    print("\n[分组内词级 Jaccard（分层依据）]")
    for g in ("R1", "R2", "D1", "D2", "D3"):
        ids = [i for i, d in enumerate(docs) if d["group"] == g]
        vals = [f"{jac(a,b):.4f}" for a, b in itertools.combinations(ids, 2)]
        print(f"  {g}: {vals}")
    # 金标准自检：改写簇与同事件簇的相似度量级必须可分离
    near_vals = [jac(a, b) for a, b in gold_near]
    se_vals = [jac(a, b) for a, b in gold_same_event]
    print(f"  改写簇 R1/R2 组内平均 Jaccard = {_np.mean(near_vals):.4f}（min {min(near_vals):.4f}）")
    print(f"  同事件簇 D1/D2 组内平均 Jaccard = {_np.mean(se_vals):.4f}（max {max(se_vals):.4f}）")
    if min(near_vals) > max(se_vals):
        print("  -> 两簇完全分离，'近似重复'与'同事件不同报道'必须分层评估")
    # D3 标注复核：内容层面而非仅相似度层面
    d3 = [d for d in docs if d["group"] == "D3"]
    print("  [D3 标注复核] 三篇标题：")
    for d in d3:
        print(f"    {d['idx']:02d}: {d['title']}")
    print("    -> 15 号为女子现代五项团体夺金，16/17 号为男子铁人三项摘银，属**不同事件**，")
    print("       故 D3 不计入近似重复正样本（原 manifest 的 group=D3 标注有误，保留原数据不动）。")

    # ---------- 阈值扫描 + HAM_TH=3 判定 ----------
    schemes = [("TF-IDF加权", fp_w), ("等权(词频)", fp_e), ("TF-IDF唯一词(消融)", fp_u)]
    res = {}
    for name, fps in schemes:
        dist = np.zeros((n, n), dtype=int)
        for i, j in itertools.combinations(range(n), 2):
            d = hamming(fps[i], fps[j])
            dist[i, j] = dist[j, i] = d
        pred = {(i, j) for i, j in itertools.combinations(range(n), 2) if dist[i, j] <= HAM_TH}
        res[name] = {
            "pred": pred, "dist": dist,
            # 修正口径：正样本 = 改写簇近似重复对
            "strict": prf(gold_near, pred),
            # 初版口径：正样本 = 所有同组对
            "mixed": prf(gold_all_same_group, pred),
            # 事件级召回：金标准扩展到“所有同组对”但只看加权的召回能力
            "event_recall": (len(set(gold_all_same_group) & pred) / len(gold_all_same_group)
                             if gold_all_same_group else 0.0),
        }
        sp = res[name]["strict"]
        mp = res[name]["mixed"]
        print(f"\n【{name} SimHash】海明距离<= {HAM_TH} 判定近似重复")
        print(f"  修正口径(正样本=改写簇 {len(gold_near)} 对): P={sp[0]:.3f} R={sp[1]:.3f} F1={sp[2]:.3f} "
              f"(TP={sp[3]} FP={sp[4]} FN={sp[5]})")
        print(f"  初版口径(正样本=所有同组 {len(gold_all_same_group)} 对): "
              f"P={mp[0]:.3f} R={mp[1]:.3f} F1={mp[2]:.3f} (TP={mp[3]} FP={mp[4]} FN={mp[5]})")

    # 阈值扫描（0~10）展示距离阈值影响
    sweep = {}
    for name, fps in schemes:
        rows = []
        for th in range(0, 11):
            pred = {(i, j) for i, j in itertools.combinations(range(n), 2)
                    if hamming(fps[i], fps[j]) <= th}
            rows.append((th, prf(gold_near, pred), prf(gold_all_same_group, pred)))
        sweep[name] = rows

    print("\n=== 海明距离阈值扫描（修正口径 P/R/F1，正样本=改写簇）===")
    print(" 阈值 | TF-IDF加权            | 等权(词频)            | 唯一词(消融)")
    for k in range(11):
        a, b, c = sweep["TF-IDF加权"][k], sweep["等权(词频)"][k], sweep["TF-IDF唯一词(消融)"][k]
        print(f"  {k:2d}  | {a[1][0]:.3f}/{a[1][1]:.3f}/{a[1][2]:.3f}       | "
              f"{b[1][0]:.3f}/{b[1][1]:.3f}/{b[1][2]:.3f}       | {c[1][0]:.3f}/{c[1][1]:.3f}/{c[1][2]:.3f}")

    # 各方法检出的重复对明细
    for name in ["TF-IDF加权", "等权(词频)"]:
        print(f"\n【{name} SimHash】判定为近似重复的文本对：")
        for i, j in sorted(res[name]["pred"]):
            gi, gj = docs[i]["group"], docs[j]["group"]
            if gi == gj and gi in NEAR_DUP_GROUPS:
                tag = "★命中(改写簇)"
            elif gi == gj:
                tag = "同组(同事件/标注待核)"
            else:
                tag = "误报"
            print(f"  {i+1:02d}-{j+1:02d} [{gi}vs{gj}] "
                  f"{docs[i]['title'][:16]}... | {docs[j]['title'][:16]}... {tag}")

    # ---------- 结果落盘 ----------
    lines = []
    lines.append(f"数据集: {n} 篇新闻（同事件不同报道/转载改写/完全不同主题）")
    lines.append(f"金标准三层: 改写簇近似重复对={len(gold_near)}  "
                 f"同事件不同报道对={len(gold_same_event)}  初版混合口径(所有同组对)={len(gold_all_same_group)}")
    lines.append(f"判定规则: 64 位指纹海明距离 <= {HAM_TH} 为近似重复\n")
    lines.append("注: D3 组经人工复核为标注错误（15 号=女子现代五项团体夺金；16/17 号=男子铁人三项摘银），")
    lines.append("    三者并非同一事件，故不计入“近似重复”正样本。\n")
    for name in ["TF-IDF加权", "等权(词频)", "TF-IDF唯一词(消融)"]:
        sp, mp = res[name]["strict"], res[name]["mixed"]
        lines.append(f"{name} SimHash:")
        lines.append(f"  修正口径(正样本=改写簇{len(gold_near)}对): P={sp[0]:.3f} R={sp[1]:.3f} F1={sp[2]:.3f} "
                     f"TP={sp[3]} FP={sp[4]} FN={sp[5]}")
        lines.append(f"  初版口径(正样本=所有同组{len(gold_all_same_group)}对): P={mp[0]:.3f} R={mp[1]:.3f} "
                     f"F1={mp[2]:.3f} TP={mp[3]} FP={mp[4]} FN={mp[5]}")
    lines.append("\n=== 海明距离阈值扫描（修正口径；正样本=改写簇）===")
    for k in range(11):
        a, b, c = sweep["TF-IDF加权"][k], sweep["等权(词频)"][k], sweep["TF-IDF唯一词(消融)"][k]
        lines.append(f"阈值={a[0]:2d}: TF-IDF加权 P={a[1][0]:.3f} R={a[1][1]:.3f} F1={a[1][2]:.3f} | "
                     f"等权 P={b[1][0]:.3f} R={b[1][1]:.3f} F1={b[1][2]:.3f} | "
                     f"唯一词 P={c[1][0]:.3f} R={c[1][1]:.3f} F1={c[1][2]:.3f}")
    lines.append("\n=== 海明距离阈值扫描（初版口径；正样本=所有同组对）===")
    for k in range(11):
        a, b = sweep["TF-IDF加权"][k], sweep["等权(词频)"][k]
        lines.append(f"阈值={a[0]:2d}: TF-IDF加权 P={a[2][0]:.3f} R={a[2][1]:.3f} F1={a[2][2]:.3f} | "
                     f"等权 P={b[2][0]:.3f} R={b[2][1]:.3f} F1={b[2][2]:.3f}")
    for name in ["TF-IDF加权", "等权(词频)"]:
        lines.append(f"\n--- {name} 检出的重复对 ---")
        for i, j in sorted(res[name]["pred"]):
            gi, gj = docs[i]["group"], docs[j]["group"]
            if gi == gj and gi in NEAR_DUP_GROUPS:
                tag = "★命中(改写簇)"
            elif gi == gj:
                tag = "同组(同事件/标注待核)"
            else:
                tag = "误报"
            lines.append(f"  {i+1:02d}-{j+1:02d} [{gi}vs{gj}] {docs[i]['title'][:20]} <-> "
                         f"{docs[j]['title'][:20]} {tag}")
    with open(os.path.join(OUT, "exp2_simhash_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # ---------- 可视化 ----------
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    names = ["TF-IDF加权", "等权(词频)"]
    mets = ["P", "R", "F1"]
    idx_map = {m: i for i, m in enumerate(mets)}
    x = np.arange(len(mets))
    w = 0.32
    for k, name in enumerate(names):
        vals = [res[name]["strict"][idx_map[m]] for m in mets]
        bars = axes[0].bar(x + (k - 0.5) * w, vals, w, label=f"{name}（修正口径）",
                           color=["#4C72B0", "#C44E52"][k])
        for b, v in zip(bars, vals):
            axes[0].text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.2f}",
                         ha="center", fontsize=9)
    # 叠加初版口径（空心）
    for k, name in enumerate(names):
        vals = [res[name]["mixed"][idx_map[m]] for m in mets]
        axes[0].bar(x + (k - 0.5) * w, vals, w, facecolor="none",
                    edgecolor=["#4C72B0", "#C44E52"][k], linestyle="--", linewidth=1.4,
                    label=f"{name}（初版口径）" if k == 0 else None)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(["查准率 P", "查全率 R", "F1"])
    axes[0].set_ylim(0, 1.12)
    axes[0].set_title(f"等权 vs TF-IDF 加权 SimHash（距离≤{HAM_TH}）\n实心=修正口径，虚线框=初版口径")
    axes[0].legend(fontsize=8)
    axes[0].grid(axis="y", alpha=0.3)

    ths = [r[0] for r in sweep["TF-IDF加权"]]
    axes[1].plot(ths, [r[1][2] for r in sweep["TF-IDF加权"]], "o-", label="TF-IDF 加权（修正口径）")
    axes[1].plot(ths, [r[1][2] for r in sweep["等权(词频)"]], "s-", label="等权（修正口径）")
    axes[1].plot(ths, [r[1][2] for r in sweep["TF-IDF唯一词(消融)"]], "d--", label="唯一词消融（修正口径）")
    axes[1].axvline(HAM_TH, color="gray", ls="--", alpha=0.7, label=f"作业规定阈值={HAM_TH}")
    axes[1].set_xlabel("海明距离阈值")
    axes[1].set_ylabel("F1")
    axes[1].set_title("海明距离阈值对去重 F1 的影响")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "exp2_simhash_prf.png"), dpi=150)
    print("\n已保存:", os.path.join(FIG, "exp2_simhash_prf.png"))


if __name__ == "__main__":
    main()
