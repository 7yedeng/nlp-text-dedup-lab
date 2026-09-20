# -*- coding: utf-8 -*-
"""验证审计提出的两条关键断言（数学等价 + 空集边界）。

断言 1（审计 2）：A1「每词元×等权1」≡ B2「每唯一词×TF」
  单词出现 m 次时：
    A1：投 m 次票，每次权重 1        => 总贡献 m
    B2：投 1 次票，权重 = 词频 m      => 总贡献 m
  两者应产生完全相同的指纹（前提：同一分词、大小写处理、哈希与零点规则）。
  本脚本直接比对两种实现产出的指纹向量，而不是只看最终的 P/R/F1。

断言 2（审计 L3）：空集合签名"统一为 0"是否真的解决了问题？
  两个全 0 签名的相同位比例是 100%，若无显式空集判定，仍会被判为相似度 1.0。
  本脚本直接测试 minhash_signature / jaccard_minhash 的空输入行为。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 项目根目录（脚本在 tools/ 下）
sys.path.insert(0, ROOT)

import numpy as np
import exp2_simhash as S
import exp1_minhash as M

print("=" * 74)
print("断言 1：A1 每词元×等权  ≡  B2 每唯一词×TF ？")
print("=" * 74)

docs = S.load_news20()
from sklearn.feature_extraction.text import TfidfVectorizer

texts = [d["title"] + " " + d["body"] for d in docs]
terms = [S.tokenize(t) for t in texts]
v = TfidfVectorizer(ngram_range=(1, 1), token_pattern=r"(?u)\b\w+\b")
X = v.fit_transform([" ".join(t) for t in terms]).toarray()
fi = {f: i for i, f in enumerate(v.get_feature_names_out())}

fp_a1 = S.make_fingerprints(terms, X, fi, unit="token", weight="one")
fp_b2 = S.make_fingerprints(terms, X, fi, unit="unique", weight="tf")

same = [a == b for a, b in zip(fp_a1, fp_b2)]
n_diff = sum(1 for s in same if not s)
print(f"逐篇比对指纹：{len(same)} 篇文档，完全相同 {same.count(True)} 篇，不同 {n_diff} 篇")

if n_diff:
    print("不同的文档（索引从 1 开始）：", [i + 1 for i, s in enumerate(same) if not s])
    for i, s in enumerate(same):
        if not s:
            d = bin(fp_a1[i] ^ fp_b2[i]).count("1")
            print(f"  doc{i+1}: 海明距离 = {d}")
else:
    print("=> 两种实现产生完全相同的 64 位指纹，审计的数学等价关系成立。")

# 顺带检查等价类是否体现在指标上
def prf_of(fps, gold):
    pred = {(i, j) for i, j in __import__("itertools").combinations(range(len(fps)), 2)
            if S.hamming(fps[i], fps[j]) <= S.HAM_TH}
    return S.prf(gold, pred)

gold = S.group_pairs(docs, S.NEAR_DUP_GROUPS)
print(f"\n指标层面（正样本=改写簇 {len(gold)} 对）：")
for nm, fps in (("A1 每词元·等权", fp_a1), ("B2 每唯一词·TF", fp_b2)):
    p, r, f1, tp, fp_, fn = prf_of(fps, gold)
    print(f"  {nm:<18} P={p:.3f} R={r:.3f} F1={f1:.3f} TP={tp} FP={fp_} FN={fn}")

print()
print("=" * 74)
print("断言 2：空集合边界行为")
print("=" * 74)

empty_sig = M.minhash_signature(set(), M.K)
print(f"空集合签名: shape={empty_sig.shape}, 全零={not np.any(empty_sig)}, 取值集合={set(empty_sig.tolist())}")
print(f"两个空集合的 jaccard_minhash = {M.jaccard_minhash(empty_sig, empty_sig)}")
print(f"两个空集合的 jaccard_exact   = {M.jaccard_exact(set(), set())}")
ok = (M.jaccard_minhash(empty_sig, empty_sig) == M.jaccard_exact(set(), set()))
print(f"=> 两种口径一致: {ok}")

# 非空 vs 空
nonempty = M.shingles("测试文本用于生成非空集合")
sig_ne = M.minhash_signature(nonempty, M.K)
print(f"\n空 vs 非空: minhash={M.jaccard_minhash(empty_sig, sig_ne)} "
      f"exact={M.jaccard_exact(set(), nonempty)}")
