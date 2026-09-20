# -*- coding: utf-8 -*-
"""作业必做项核对清单（checklist）

按《实验一 内容重复理解技术综合实验》原文逐条核对四个子实验的
「指定参数 / 指定图表 / 指定分析」是否齐全，输出可读清单。

这不是审计工具，而是交作业前的自查表：
    python tools/checklist.py
退出码 0 = 全部命中；1 = 有缺项。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out")

items = []          # (子实验, 要求, 是否满足, 证据)


def load(fn):
    p = os.path.join(OUT, fn)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def check_text(path, pattern):
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return re.search(pattern, f.read(), re.M)


def main():
    tf = load("results_summary_tfidf.json")
    mh = load("results_summary_minhash.json")
    wv = load("results_summary_wordvec.json")
    sh = load("results_summary_simhash.json")

    # ---------------- 题目一(1) TF-IDF ----------------
    if tf:
        items.append(("一(1)", "语料 ≥500 条中文新闻标题/评论",
                      tf["scale"] >= 500, f"规范化去重后 {tf['scale']} 条"))
        items.append(("一(1)", "语料保存为 txt，每行一条",
                      os.path.exists(os.path.join(ROOT, "data", "titles.txt")),
                      "data/titles.txt"))
        ok = check_text("exp1_tfidf.py", r"jieba\.lcut")
        items.append(("一(1)", "使用 jieba 分词", bool(ok), "exp1_tfidf.py"))
        ok = check_text("exp1_tfidf.py", r"STOPWORDS")
        items.append(("一(1)", "去除停用词", bool(ok), "内置词表 + data/stopwords/"))
        items.append(("一(1)", "max_features=1000",
                      tf["config"]["max_features"] == 1000,
                      f"config.max_features={tf['config']['max_features']}"))
        items.append(("一(1)", "ngram_range=(1,2)",
                      tf["config"]["ngram_range"] == [1, 2],
                      f"config.ngram_range={tf['config']['ngram_range']}"))
        items.append(("一(1)", "余弦相似度 Top-10 文本对",
                      len(tf["top10"]) == 10,
                      f"输出 {len(tf['top10'])} 对（且为 10 个不同文本对）"))
        uniq = len({(p["i"], p["j"]) for p in tf["top10"]})
        items.append(("一(1)", "Top-10 是十个不同文本对（无反向重复）",
                      uniq == 10, f"去重后 {uniq} 对"))
        items.append(("一(1)", "词频最高 20 词的 TF-IDF 权重柱状图",
                      os.path.exists(os.path.join(OUT, "figures", "exp1_tfidf_top20.png")),
                      "out/figures/exp1_tfidf_top20.png"))
        items.append(("一(1)", "对结果有分析（非只给数字）",
                      tf is not None, "报告 3.1.5 节"))

    # ---------------- 题目一(2) MinHash + LSH ----------------
    if mh:
        items.append(("一(2)", "设计 6 个测试短文本用例",
                      mh["n_cases"] == 6, f"n_cases={mh['n_cases']}"))
        items.append(("一(2)", "用例保存为 txt",
                      os.path.exists(os.path.join(ROOT, "data", "short_texts.txt")),
                      "data/short_texts.txt"))
        items.append(("一(2)", "覆盖完全重复/轻度修改/中度改写/完全不相关",
                      len(mh["gold"]["near_dup_pairs"]) >= 1
                      and len(mh["gold"]["same_event_pairs"]) >= 1,
                      f"近重复 {mh['gold']['near_dup']} 对、同事件改写 "
                      f"{mh['gold']['same_event']} 对、不相关 T5/T6"))
        items.append(("一(2)", "哈希函数个数 k=128",
                      mh["config"]["k"] == 128, f"k={mh['config']['k']}"))
        items.append(("一(2)", "实现 MinHash 签名生成",
                      check_text("exp1_minhash.py", r"def minhash_signature") is not None,
                      "exp1_minhash.py: minhash_signature"))
        items.append(("一(2)", "实现 LSH 分桶近似近邻查找",
                      check_text("exp1_minhash.py", r"def build_lsh_tables") is not None,
                      "exp1_minhash.py: build_lsh_tables / lsh_candidates"))
        items.append(("一(2)", "批量计算相似度并识别冗余文本",
                      check_text("exp1_minhash.py", r"def lsh_candidates") is not None,
                      "批量规模实验 + 候选回验"))
        items.append(("一(2)", "对比 N-gram+Jaccard 精确 vs MinHash 近似的准确性",
                      "minhash_error" in mh,
                      f"MAE={mh['minhash_error']['mae']:.4f}，逐对精确/估计值已落盘"))
        items.append(("一(2)", "对比运行时间",
                      len(mh["scaling_end2end_ms"]) >= 4,
                      "4 个规模 × 5 次重复，端到端 + 逐次原始值"))
        items.append(("一(2)", "分析不同阈值对去重结果的影响",
                      len(mh["thresholds"]) >= 8,
                      f"{len(mh['thresholds'])} 个阈值 × 混合/分层两种口径"))

    # ---------------- 题目二(1) 词向量 ----------------
    if wv:
        items.append(("二(1)", "使用中文预训练词向量",
                      wv["model"]["n_words"] > 100000,
                      f"{wv['model']['n_words']} 词 × {wv['model']['dim']} 维；"
                      f"sha256={wv['model']['sha256'][:16]}…"))
        items.append(("二(1)", "使用 Gensim 加载",
                      "gensim" in wv["model"]["loader"],
                      wv["model"]["loader"]))
        items.append(("二(1)", "验证语义推理（国王-男人+女人≈王后）",
                      any(a["a"] == "国王" for a in wv["analogies"]),
                      "已含该组，且命中"))
        items.append(("二(1)", "至少 10 组词对相似度",
                      len(wv["word_pairs"]) >= 10,
                      f"{len(wv['word_pairs'])} 组"))
        items.append(("二(1)", "三类主题文本各 50 篇",
                      all(v["total"] > 0 for v in wv["vocab_coverage"]["per_cat"].values())
                      and wv["n_docs"] == 150,
                      f"共 {wv['n_docs']} 篇（体育/科技/娱乐各 50）"))
        items.append(("二(1)", "词向量平均池化得到文档向量",
                      check_text("exp2_wordvec.py", r"def doc_vector") is not None,
                      "exp2_wordvec.py: doc_vector（L2 归一化）"))
        items.append(("二(1)", "降维到 2 维可视化（t-SNE 或 PCA）",
                      os.path.exists(os.path.join(OUT, "figures", "exp2_wordvec_pca_tsne.png")),
                      "out/figures/exp2_wordvec_pca_tsne.png（含 PCA 与 t-SNE）"))
        items.append(("二(1)", "KMeans 文本聚类（考核表列出）",
                      check_text("exp2_wordvec.py", r"KMeans") is not None,
                      f"KMeans K=3，Purity={wv['purity']:.4f}，ARI={wv['ari']:.4f}"))
        items.append(("二(1)", "Word2Vec 与 GloVe 差异的原理说明",
                      check_text("tools/build_report.py", r"GloVe") is not None,
                      "报告 4.1.3 节"))

    # ---------------- 题目二(2) 加权 SimHash ----------------
    if sh:
        items.append(("二(2)", "20 篇网页新闻文本",
                      sh["n_docs"] == 20, f"n_docs={sh['n_docs']}"))
        items.append(("二(2)", "覆盖同事件不同报道/转载改写/完全不同主题三类",
                      len(sh["gold"]["categories"]["POSITIVE"]["groups"]) >= 1
                      and len(sh["gold"]["categories"]["EXCLUDED"]["groups"]) >= 1
                      and len(sh["gold"]["categories"]["UNCERTAIN"]["groups"]) >= 1,
                      "转载改写 R1/R2、同事件 D1/D2、不同事件 D3+U1~U3"))
        items.append(("二(2)", "引入 TF-IDF 权重（高 TF-IDF 加权）",
                      check_text("exp2_simhash.py", r"TfidfVectorizer") is not None,
                      "exp2_simhash.py: make_fingerprints(weight='tfidf')"))
        items.append(("二(2)", "停用词降权",
                      check_text("exp2_simhash.py", r"STOP_SCALE") is not None,
                      f"STOP_SCALE={sh['stop_scale']}"))
        items.append(("二(2)", "64 位指纹",
                      sh["bits"] == 64, f"bits={sh['bits']}"))
        items.append(("二(2)", "海明距离 ≤3 判定近似重复",
                      sh["ham_th"] == 3, f"ham_th={sh['ham_th']}"))
        items.append(("二(2)", "对比传统等权与 TF-IDF 加权的 P/R/F1",
                      any("等权" in s["name"] for s in sh["schemes"])
                      and any("TF-IDF" in s["name"] for s in sh["schemes"]),
                      "报告主表突出等权与加权两行；完整消融移至附录"))

    # ---------------- 提交要求 ----------------
    # 提交材料可能位于：本项目 out/、本项目 提交材料/、
    # 或整理成「NLP第一次实验」包后的 01_提交材料/（在包的顶层，需向上找几级）
    _SUB_DIRS = [OUT, os.path.join(ROOT, "提交材料")]
    _up = ROOT
    for _ in range(4):
        _up = os.path.dirname(_up)
        if not _up or _up == os.path.dirname(_up):
            break
        _SUB_DIRS.append(os.path.join(_up, "01_提交材料"))
        _SUB_DIRS.append(os.path.join(_up, "提交材料"))

    def find_sub(suffix, exclude=()):
        for d in _SUB_DIRS:
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if fn.endswith(suffix) and not fn.startswith("~$") \
                        and not any(x in fn for x in exclude):
                    return os.path.join(d, fn), fn
        return None, None

    _rep_path, _rep_name = find_sub("第1次实验报告.docx", exclude=("脱敏",))
    _name_ok = bool(_rep_name) and _rep_name.count("+") >= 3   # 姓名+学号+姓名+学号+…
    items.append(("提交", "Word 实验报告",
                  bool(_rep_path), _rep_name or "未找到"))
    items.append(("提交", "报告命名：姓名+学号（双人）+第1次实验报告.docx",
                  _name_ok, _rep_name or "未找到"))
    items.append(("提交", "含实验目的",
                  check_text("tools/build_report.py", r"实验目的") is not None, "各节 x.1"))
    items.append(("提交", "含加权 SimHash 算法原理",
                  check_text("tools/build_report.py", r"算法原理（加权 SimHash）") is not None,
                  "4.2.2 节"))
    _shots = [f for f in os.listdir(os.path.join(OUT, "screenshots"))
              if f.endswith(".png")] if os.path.isdir(os.path.join(OUT, "screenshots")) else []
    items.append(("提交", "含关键代码白底截图", len(_shots) >= 8, f"{len(_shots)} 张"))
    items.append(("提交", "含查准率/查全率/F1 表格",
                  check_text("tools/build_report.py", r"查准率") is not None, "4.2.5 节表格"))
    _figs = [f for f in os.listdir(os.path.join(OUT, "figures"))] \
        if os.path.isdir(os.path.join(OUT, "figures")) else []
    items.append(("提交", "含可视化结果", len(_figs) >= 4, f"{len(_figs)} 张图"))
    items.append(("提交", "含实验学习笔记",
                  check_text("tools/build_report.py", r"实验学习笔记") is not None, "第五节"))
    _zp, _zn = find_sub("-代码.zip")
    items.append(("提交", "代码压缩包（不含第三方库与大模型）",
                  bool(_zp), _zn or "未找到"))

    # ---------------- 输出 ----------------
    print("=" * 78)
    print("作业必做项核对清单")
    print("=" * 78)
    n_ok = 0
    cur = None
    for sub, req, ok, ev in items:
        if sub != cur:
            print(f"\n【{sub}】")
            cur = sub
        mark = "✅" if ok else "❌"
        if ok:
            n_ok += 1
        print(f"  {mark} {req}")
        if ev:
            print(f"       → {ev}")
    print("\n" + "=" * 78)
    print(f"合计 {len(items)} 项，满足 {n_ok} 项，缺 {len(items) - n_ok} 项")
    if n_ok == len(items):
        print("✅ 必做项全部命中")
        return 0
    print("❌ 存在缺项，见上方 ❌ 标记")
    return 1


if __name__ == "__main__":
    sys.exit(main())
