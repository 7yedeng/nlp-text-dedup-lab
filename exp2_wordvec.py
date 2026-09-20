# -*- coding: utf-8 -*-
"""
实验题目二(1)：预训练词向量文本表示与语义分析
要求：
  - 下载腾讯 AI Lab 中文词向量并用 Gensim 加载
  - 验证语义推理：国王-男人+女人 ≈ 王后（至少 10 组词对相似度）
  - 三类主题文本（体育/科技/娱乐 各50篇）词向量平均池化得到文档向量
  - t-SNE / PCA 降至 2 维可视化主题分布
"""
import os
import re
import hashlib
import json
import time
import numpy as np
import jieba
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from gensim.models import KeyedVectors
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
MODEL = os.path.join(BASE, "model", "light_Tencent_AILab_ChineseEmbedding.bin")
OUT = os.path.join(BASE, "out")
FIG = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)

STOPWORDS = set("""的 了 和 是 就 都 而 及 与 着 或 一个 没有 我们 你们 他们 它们 这 那 之 在 上 下 中 有 我 你 他 她 它 也 还 又 被 让 把 对 从 向 为 以 于 到 出 过 很 更 最 不 没 谁 什么 怎么 为什么 如何 哪 哪些 因为 所以 但是 然而 虽然 如果 只要 已经 正在 将 会 能 可以 应该 必须 这个 那个 这些 那些 啊 吧 呢 嘛 啦 呀 吗 哈 好 哦 嗯 一 二 三 四 五 六 七 八 九 十 万 亿 百 千 个 条 篇 岁 年 月 日 时 分 秒 今天 昨天 明天 现在 时候 方面 进行 通过 随着 据悉 记者 报道 消息 表示 称 目前 日前 近日 已经 香港 台湾 中国 美国 日本 """.split())

# 文档向量是否做 L2 归一化（见 doc_vector 的 M5 说明）。
# 归一化后 KMeans 的欧氏距离与余弦相似度排序等价，口径统一。
NORMALIZE_DOCVEC = True

# 模型身份：加载时计算完整 SHA-256 并记录字节数，
# 使"用了哪个模型"可被独立核验（审计 M3/§5 要求完整哈希，不接受省略形式）。
MODEL_SHA256 = None      # 由 main() 在加载后填充


def _sha256_of(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def parse_doc(raw):
    """解析统一的新闻文件格式，返回 (title, source, category, body)。

    文件格式：
        title=标题
        source=来源|URL
        category=类别
        [group=分组]        ← 仅 news20 才有
        [rewrite=改写类型]   ← 仅 news20 才有
        <空行>
        正文……

    【修正D】初版用 `raw.split("\\n", 3)[3]` 取正文，由于前 3 次切分只吃掉
    3 个换行符，且 metadata 与正文之间还有一个空行，第 4 段实际是
    “剩余元信息 + 空行 + 正文”（例如 "group=R1\\nrewrite=\\n\\n\\n智东西…"）。
    这会把 group=/rewrite= 当作正文词混入文档，虚增词表覆盖率。
    现改为按首个空行切分，严格取正文。
    """
    head, _, body = raw.partition("\n\n")
    meta = {}
    for ln in head.split("\n"):
        if "=" in ln:
            k, _, v = ln.partition("=")
            meta[k.strip()] = v.strip()
    return meta.get("title", ""), meta.get("source", ""), meta.get("category", ""), body.strip()


def load_docs(category):
    """读取 data/<category>/*.txt，返回 [(title, body tokens)]"""
    folder = os.path.join(DATA, category)
    docs = []
    for fn in sorted(os.listdir(folder)):
        if not fn.endswith(".txt"):
            continue
        with open(os.path.join(folder, fn), encoding="utf-8") as f:
            title, _src, _cat, body = parse_doc(f.read())
        text = title + " " + body
        words = []
        for w in jieba.lcut(text):
            w = w.strip()
            if not w or w in STOPWORDS:
                continue
            if re.fullmatch(r"[\d\W_]+", w):
                continue
            words.append(w)
        docs.append((title, words))
    return docs


def doc_vector(words, wv, normalize=True):
    """词向量平均池化（Doc2Vec 平均）：只累加词表中存在的词向量。

    返回 (向量, 命中词数, 总词数)；向量为 None 表示全部词都在词表外。

    【M5 说明】增加可选的 L2 归一化。归一化后「余弦相似度」与「欧氏距离」
    在排序上等价（KMeans 在单位球面上做欧氏聚类），
    这样"可视化用的余弦可分性"与"聚类用的距离"才是同一口径。
    报告中同时给出归一化开关的实际取值，避免口径混用。
    """
    vecs = []
    for w in words:
        if w in wv:
            vecs.append(wv[w])
    if not vecs:
        return None, 0, len(words)
    v = np.mean(vecs, axis=0)
    if normalize:
        n = np.linalg.norm(v)
        if n > 0:
            v = v / n
    return v, len(vecs), len(words)


def main():
    t0 = time.time()
    print("加载预训练词向量（腾讯 AI Lab 中文词向量 800万词轻量版，200 维）...")
    wv = KeyedVectors.load_word2vec_format(MODEL, binary=True, encoding="utf-8")
    print(f"加载完成: {len(wv)} 词, 维度 {wv.vector_size}, 耗时 {time.time()-t0:.2f}s")
    global MODEL_SHA256, MODEL_SIZE
    MODEL_SIZE = os.path.getsize(MODEL)
    MODEL_SHA256 = _sha256_of(MODEL)
    print(f"模型身份: size={MODEL_SIZE} bytes  sha256={MODEL_SHA256}")

    lines = [f"模型信息: {len(wv)} 词 x {wv.vector_size} 维 (腾讯 AI Lab 中文词向量 800万词轻量版)"]

    # ---------- 1) 语义推理：词向量运算 ----------
    print("\n=== 语义推理（类比推理）===")
    lines.append("\n=== 语义推理（类比推理）===")
    # 【M5 修正】类比方向必须与关系类型匹配。
    # 关系「男→女」对应「国王→王后」：国王 - 男人 + 女人 ≈ 王后  ✅
    # 但「父亲→儿子」是辈分关系、「母亲→女儿」也是辈分关系，正确写法是
    #   儿子 - 父亲 + 母亲 ≈ 女儿
    # 初版写成 父亲 - 儿子 + 母亲，方向反了（变成"辈分升 → 降"再"性别替换"），
    # 因此返回「父母亲」并不能作为"模型性别方向不稳定"的证据。
    # 同理「太阳-白天+月亮」应写成 白天 - 太阳 + 月亮。
    # 这里把每个类比的"关系类型"与"方向"显式标注出来，避免再次误读。
    analogies = [
        ("国王", "男人", "女人", "王后", "性别：男→女"),
        ("北京", "中国", "法国", "巴黎", "首都：国家→首都"),
        ("中国", "北京", "伦敦", "英国", "国家：首都→国家"),
        ("儿子", "父亲", "母亲", "女儿", "辈分+性别：男→女 同辈分"),
        ("医生", "医院", "学校", "老师", "场所↔角色"),
        ("白天", "太阳", "月亮", "夜晚", "时段：日→夜"),
    ]
    analogy_rows = []
    for a, b, c, expect, rel in analogies:
        try:
            # a - b + c ≈ expect  =>  positive=[a, c], negative=[b]
            r = wv.most_similar(positive=[a, c], negative=[b], topn=5)
            got = r[0][0]
            top = "、".join(f"{w}({s:.3f})" for w, s in r[:3])
            ok = "★命中" if got == expect else ""
            analogy_rows.append((a, b, c, expect, rel, top, bool(ok)))
            print(f"  {a}-{b}+{c} 期望≈{expect:4s} [{rel}] | 实际: {top} {ok}")
            lines.append(f"  {a}-{b}+{c} 期望≈{expect} [{rel}] | 实际: {top} {ok}")
        except Exception as e:
            print(f"  {a}-{b}+{c}: 词不在词表 {e}")
            lines.append(f"  {a}-{b}+{c}: 词不在词表 ({type(e).__name__})")

    # ---------- 2) 词对相似度（至少 10 组） ----------
    print("\n=== 词对相似度（12 组）===")
    lines.append("\n=== 词对相似度（12 组）===")
    pairs = [
        ("中国", "北京"), ("北京", "上海"), ("苹果", "手机"), ("苹果", "香蕉"),
        ("足球", "篮球"), ("医生", "护士"), ("汽车", "电动车"), ("电影", "电视剧"),
        ("老师", "学生"), ("手机", "电脑"), ("程序员", "编程"), ("冠军", "奥运"),
    ]
    sim_lines = []
    pair_rows = []
    for w1, w2 in pairs:
        if w1 in wv and w2 in wv:
            s = wv.similarity(w1, w2)
            pair_rows.append((w1, w2, float(s)))
            print(f"  sim({w1}, {w2}) = {s:.4f}")
            sim_lines.append(f"  sim({w1}, {w2}) = {s:.4f}")
        else:
            print(f"  sim({w1}, {w2}) = 词不在词表")
            sim_lines.append(f"  sim({w1}, {w2}) = 词不在词表")
    lines.extend(sim_lines)

    # ---------- 3) 三类主题文档向量（平均池化） ----------
    print("\n=== 三类主题文档向量（词向量平均池化）===")
    lines.append("\n=== 三类主题文档向量（词向量平均池化）===")
    categories = ["sports", "tech", "ent"]
    labels = {"sports": "体育", "tech": "科技", "ent": "娱乐"}
    vecs, meta = [], []
    cover_hit, cover_tot = 0, 0
    cat_coverage = {}
    for cat in categories:
        docs = load_docs(cat)
        n_doc = 0
        ch, ct = 0, 0
        for title, words in docs:
            v, hit, tot = doc_vector(words, wv, normalize=NORMALIZE_DOCVEC)
            ch += hit
            ct += tot
            if v is None:
                continue
            vecs.append(v)
            meta.append((cat, title))
            n_doc += 1
        cover_hit += ch
        cover_tot += ct
        cat_coverage[cat] = {"hit": ch, "total": ct, "ratio": (ch / ct if ct else 0.0)}
        print(f"  {labels[cat]}: {n_doc} 篇文档向量 OK；词表覆盖率 {ch/max(ct,1):.2%} ({ch}/{ct})")
        lines.append(f"  {labels[cat]}: {n_doc} 篇文档向量 OK；词表覆盖率 {ch/max(ct,1):.4%} ({ch}/{ct})")
    X = np.array(vecs)
    vocab_cover = cover_hit / max(cover_tot, 1)
    print(f"文档向量矩阵: {X.shape}；整体词表覆盖率 {vocab_cover:.2%}")
    lines.append(f"文档向量矩阵: {X.shape}")
    lines.append(f"整体词表覆盖率: {vocab_cover:.4%} ({cover_hit}/{cover_tot})")

    # 类内 / 类间平均余弦相似度（检验主题可分性）
    from sklearn.metrics.pairwise import cosine_similarity
    cmat = cosine_similarity(X)
    intra, inter = [], []
    for i in range(len(meta)):
        for j in range(i + 1, len(meta)):
            s = cmat[i, j]
            if meta[i][0] == meta[j][0]:
                intra.append(s)
            else:
                inter.append(s)
    print(f"  类内平均相似度: {np.mean(intra):.4f}   类间平均相似度: {np.mean(inter):.4f}")
    lines.append(f"  类内平均相似度: {np.mean(intra):.4f}   类间平均相似度: {np.mean(inter):.4f}")

    # ---------- 4) KMeans 文本聚类（验证文档向量的主题可分性） ----------
    cats = [m[0] for m in meta]
    cat2id = {"sports": 0, "tech": 1, "ent": 2}
    y_true = np.array([cat2id[c] for c in cats])
    km = KMeans(n_clusters=3, n_init=10, random_state=42).fit(X)
    y_pred = km.labels_
    ari = adjusted_rand_score(y_true, y_pred)

    # 聚类纯度：每个簇取真实类别中的多数类
    purity = 0
    for c in range(3):
        idx = y_pred == c
        if idx.sum() == 0:
            continue
        cnt = np.bincount(y_true[idx], minlength=3)
        purity += cnt.max()
    purity /= len(y_true)

    # 混淆矩阵（行=真实主题，列=聚类簇）
    conf = np.zeros((3, 3), dtype=int)
    for t, p in zip(y_true, y_pred):
        conf[t, p] += 1

    print("\n=== KMeans 文本聚类（K=3）===")
    print(f"  聚类纯度 Purity = {purity:.4f}   调整兰德指数 ARI = {ari:.4f}")
    print(f"  距离口径：文档向量 L2 归一化={NORMALIZE_DOCVEC}，"
          f"KMeans 使用欧氏距离；归一化后与余弦相似度排序等价")
    print("  混淆矩阵(行=真实:体育/科技/娱乐, 列=聚类簇):")
    for r, name in enumerate(["体育", "科技", "娱乐"]):
        print(f"    {name}: {conf[r].tolist()}")
    lines.append("\n=== KMeans 文本聚类（K=3）===")
    lines.append(f"  聚类纯度 Purity = {purity:.4f}   调整兰德指数 ARI = {ari:.4f}")
    lines.append(f"  距离口径: 文档向量 L2 归一化={NORMALIZE_DOCVEC}; KMeans 默认欧氏距离")
    lines.append("  说明: 归一化后 ||a-b||^2 = 2-2cos(a,b)，故欧氏聚类与余弦口径一致；")
    lines.append("        若不归一化，则聚类受文档向量模长（≈词向量平均长度）影响，两种口径不可混用。")
    lines.append("  混淆矩阵(行=真实:体育/科技/娱乐, 列=聚类簇):")
    for r, name in enumerate(["体育", "科技", "娱乐"]):
        lines.append(f"    {name}: {conf[r].tolist()}")

    # ---------- 5) PCA / t-SNE 降维可视化 ----------
    colors = {"sports": "#C44E52", "tech": "#55A868", "ent": "#4C72B0"}
    pca_xy = PCA(n_components=2, random_state=42).fit_transform(X)
    tsne_xy = TSNE(n_components=2, perplexity=30, init="pca", random_state=42).fit_transform(X)

    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    for ax, xy, name in [(axes[0], pca_xy, "PCA"), (axes[1], tsne_xy, "t-SNE")]:
        for cat in categories:
            mask = [meta[i][0] == cat for i in range(len(meta))]
            ax.scatter(xy[mask, 0], xy[mask, 1], s=18, alpha=0.75,
                       color=colors[cat], label=labels[cat])
        ax.set_title(f"文档向量 {name} 降维可视化（词向量平均池化）")
        ax.set_xlabel(f"{name} 维度 1")
        ax.set_ylabel(f"{name} 维度 2")
        ax.legend()
        ax.grid(alpha=0.3)

    # 第 3 幅：KMeans 聚类结果（形状=真实主题，颜色=聚类簇）
    markers = {"sports": "o", "tech": "^", "ent": "s"}
    cmap = ["#4C72B0", "#C44E52", "#55A868"]
    for cat in categories:
        for c in range(3):
            mask = np.array([meta[i][0] == cat and y_pred[i] == c for i in range(len(meta))])
            if mask.sum() == 0:
                continue
            axes[2].scatter(pca_xy[mask, 0], pca_xy[mask, 1], s=26, alpha=0.8,
                            marker=markers[cat], color=cmap[c])
    axes[2].set_title(f"KMeans 聚类结果（PCA 平面）\nPurity={purity:.3f}  ARI={ari:.3f}")
    axes[2].set_xlabel("PCA 维度 1")
    axes[2].set_ylabel("PCA 维度 2")
    axes[2].grid(alpha=0.3)
    from matplotlib.lines import Line2D
    legend_items = [Line2D([0], [0], marker=markers[c], color="gray", ls="", label=f"真实:{labels[c]}")
                    for c in categories] + \
                   [Line2D([0], [0], marker="o", color=cmap[c], ls="", label=f"簇 {c}")
                    for c in range(3)]
    axes[2].legend(handles=legend_items, fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "exp2_wordvec_pca_tsne.png"), dpi=150)
    print("\n已保存:", os.path.join(FIG, "exp2_wordvec_pca_tsne.png"))

    with open(os.path.join(OUT, "exp2_wordvec_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n\n已保存图: exp2_wordvec_pca_tsne.png")

    # ---- 消融对照：文档向量不归一化时的聚类指标（审计意见 M5）----
    # 归一化前后用同一套数据、同一 KMeans 设置重跑，两个指标都实测出来，
    # 使报告中的"归一化前/后"对照同样来自脚本计算，而不是手写常量。
    _docs_flat = [(t, ws) for cat in categories for t, ws in load_docs(cat)]
    _raw_vecs = []
    for _t, _ws in _docs_flat:
        _vr, _h, _tt = doc_vector(_ws, wv, normalize=False)
        if _vr is not None:
            _raw_vecs.append(_vr)
    X_raw = np.array(_raw_vecs)
    km_raw = KMeans(n_clusters=3, n_init=10, random_state=42).fit(X_raw)
    _pur_raw = 0.0
    for _c in range(3):
        _ic = km_raw.labels_ == _c
        if _ic.sum() == 0:
            continue
        _pur_raw += np.bincount(y_true[_ic], minlength=3).max()
    _pur_raw /= len(y_true)
    _ari_raw = adjusted_rand_score(y_true, km_raw.labels_)
    print(f"  消融对照（文档向量不归一化）: Purity={_pur_raw:.4f}  ARI={_ari_raw:.4f}")
    lines.append(f"  消融对照（文档向量不归一化）: Purity={_pur_raw:.4f}  ARI={_ari_raw:.4f}")

    # ---- 结构化汇总（供报告生成器读取，杜绝报告里硬编码数字）----
    # 混淆矩阵的行=真实主题，列=簇编号；这里额外记录「每个簇的多数真实主题」，
    # 使报告能用客观映射描述"哪个簇对应哪个主题"，而不是靠人工误读列号。
    cluster_majority = {}
    for c in range(3):
        idx = y_pred == c
        if idx.sum() == 0:
            continue
        cnt = np.bincount(y_true[idx], minlength=3)
        cluster_majority[str(c)] = {
            "majority_cat": ["sports", "tech", "ent"][int(cnt.argmax())],
            "majority_name": ["体育", "科技", "娱乐"][int(cnt.argmax())],
            "n": int(idx.sum()), "counts": cnt.tolist()}
    summary = {
        "model": {"n_words": int(len(wv)), "dim": int(wv.vector_size),
                  "path": os.path.relpath(MODEL, BASE),
                  # 模型身份锁定（审计要求：完整 SHA-256 + 字节数 + 头部 + 加载方式）
                  "sha256": MODEL_SHA256, "size_bytes": MODEL_SIZE,
                  "header": f"{len(wv)} {wv.vector_size}",
                  "loader": "gensim.models.KeyedVectors.load_word2vec_format(binary=True)"},
        "normalize_docvec": bool(NORMALIZE_DOCVEC),
        "cluster_distance": "euclidean (KMeans default)",
        "analogies": [{"a": a, "b": b, "c": c, "expect": e, "relation": rel,
                       "top": top, "hit": bool(hit)} for a, b, c, e, rel, top, hit in analogy_rows],
        "word_pairs": [{"w1": w1, "w2": w2, "sim": s} for w1, w2, s in pair_rows],
        "doc_vectors_shape": list(X.shape),
        "vocab_coverage": {"overall": vocab_cover, "hit": cover_hit, "total": cover_tot,
                           "per_cat": cat_coverage},
        "intra_mean": float(np.mean(intra)), "inter_mean": float(np.mean(inter)),
        "purity": float(purity), "ari": float(ari),
        "purity_no_norm": float(_pur_raw), "ari_no_norm": float(_ari_raw),
        "confusion": conf.tolist(),
        "cluster_majority": cluster_majority,
        "n_docs": int(len(y_true)),
    }
    with open(os.path.join(OUT, "results_summary_wordvec.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print("已落盘: out/results_summary_wordvec.json")


if __name__ == "__main__":
    main()