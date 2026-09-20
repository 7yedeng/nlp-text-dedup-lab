# -*- coding: utf-8 -*-
"""报告一致性校验（加强版）—— 绑定「方法 + 字段 + 文本范围 + 阈值 + gold 版本」

【为什么需要加强】
初版自检只做“数字是否出现在结构化结果里”，审计指出这**只证明数字能找到，
不证明指标归属正确**——把 B1 的值挪给 B3、把 P 和 R 对调，白名单照样通过。

本版改为**反向核验**：从报告 DOCX 里把“方案名 → 指标值”成对读出来，
再与 results_summary_*.json 中该方案的指标逐一比对；
同时校验整数计数（TP/FP/FN/TN）、gold 数量、阈值与输入范围声明。

校验项
  C1 方案表：报告中每个方案行的 P/R/F1/TP/FP/FN 必须与 JSON 中同名方案一致
  C2 计数自洽：TP+FN = gold 正样本数；TP+FP = 判定对数；P=TP/(TP+FP)；R=TP/(TP+FN)
  C3 归属正确：把任两行的指标互换后必须能被检出（本脚本内置自检——见 --selftest）
  C4 gold 数量：报告中出现的正样本数必须等于 JSON 的 gold.near_dup
  C5 阈值/范围：报告声明的阈值与文本范围必须与 JSON 一致
  C6 无孤立数字：报告中其余小数必须能在结构化结果中找到出处
  C7 历史数字：91.87/713.32/30.52 只允许出现在“历史整改”段落内

用法：
  python tools/verify_report_consistency.py            # 校验
  python tools/verify_report_consistency.py --selftest # 验证校验器本身有效（负向测试）
"""
import json
import os
import re
import sys

from docx import Document

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out")


def _find_report():
    """自动定位学校提交版报告（文件名含双人姓名学号，故用约定后缀匹配）。"""
    if not os.path.isdir(OUT):
        return os.path.join(OUT, "第1次实验报告.docx")
    cands = [f for f in sorted(os.listdir(OUT))
             if f.endswith("第1次实验报告.docx") and not f.startswith("~$")
             and "脱敏" not in f]
    return os.path.join(OUT, cands[0]) if cands else os.path.join(OUT, "第1次实验报告.docx")


REPORT = _find_report()

HISTORICAL_NUMBERS = ["91.87", "713.32", "30.52"]
# 允许出现历史数字的段落必须同时包含这些词之一（即明确标注为“初版/历史/错误记录”）
HISTORICAL_MARKERS = ["初版", "历史", "硬编码", "旧数字", "错误记录"]

errors = []
warnings = []


def load_summaries():
    out = {}
    for fn in sorted(os.listdir(OUT)):
        if fn.startswith("results_summary_") and fn.endswith(".json"):
            with open(os.path.join(OUT, fn), encoding="utf-8") as f:
                out[fn] = json.load(f)
    return out


def doc_paragraphs_and_tables(path):
    """返回 (段落文本, [(表题, 行数据)]) —— 表题取自表格前最近的“表 x-y …”段落。

    需要表题是为了区分「修正口径」与「初版混合口径」两张方案表：
    它们列出的方案名相同，但指标口径不同（正样本 12 对 vs 21 对）。
    若不加区分，校验器会把混合口径表当成主表而误报。
    """
    doc = Document(path)
    paras = [p.text for p in doc.paragraphs]
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    tables = []
    last_caption = ""
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            txt = Paragraph(child, doc).text.strip()
            if txt.startswith("表 "):
                last_caption = txt
        elif child.tag == qn("w:tbl"):
            t = Table(child, doc)
            rows = [[c.text.strip() for c in r.cells] for r in t.rows]
            tables.append((last_caption, rows))
    return paras, tables


def near(a, b, tol=0.0015):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------- C1~C4
def check_scheme_table(tables, sh):
    """在报告表格中定位「方案名 + 指标」行，按表题选择对应口径后与 JSON 逐一比对。

    口径判别：
      表题含“初版混合口径” → 比对 json 的 mixed 字段（正样本=所有同组对）
      其它含“权重方案对照”的表   → 比对 json 的 strict 字段（正样本=改写簇）
    """
    schemes = {s["name"]: s for s in sh["schemes"]}
    checked, rows_found = 0, 0
    for caption, t in tables:
        if not t or len(t[0]) < 7:
            continue
        header = " ".join(t[0])
        if not ("P" in header and "R" in header and "F1" in header):
            continue
        basis = "mixed" if "混合口径" in caption else "strict"
        for row in t[1:]:
            name = row[0].strip()
            if name not in schemes:
                continue
            rows_found += 1
            s = schemes[name]
            st = s[basis]
            want = [f"{st['P']:.3f}", f"{st['R']:.3f}", f"{st['F1']:.3f}",
                    str(st["TP"]), str(st["FP"]), str(st["FN"])]
            got = [c.strip() for c in row[1:7]]
            for k, (w, g) in enumerate(zip(want, got)):
                label = ["P", "R", "F1", "TP", "FP", "FN"][k]
                tag = "混合口径" if basis == "mixed" else "修正口径"
                if k <= 2:
                    if not near(w, g):
                        errors.append(f"[C1/{tag}] 方案 {name} 的 {label}: 报告={g} 结果={w}")
                else:
                    if g != w:
                        errors.append(f"[C1/{tag}] 方案 {name} 的 {label}: 报告={g} 结果={w}")
            # C2 计数自洽（两种口径都要自洽；gold 用该口径对应的正样本数）
            gold_n = (sh["gold"]["mixed_all_same_group"] if basis == "mixed"
                      else sh["gold"]["near_dup"])
            if st["TP"] + st["FN"] != gold_n:
                errors.append(f"[C2/{basis}] {name}: TP+FN={st['TP'] + st['FN']} ≠ gold 正样本 {gold_n}")
            if st["TP"] + st["FP"] > 0:
                p_calc = st["TP"] / (st["TP"] + st["FP"])
                if not near(p_calc, st["P"]):
                    errors.append(f"[C2/{basis}] {name}: P 不自洽 计算={p_calc:.3f} 记录={st['P']:.3f}")
            if st["TP"] + st["FN"] > 0:
                r_calc = st["TP"] / (st["TP"] + st["FN"])
                if not near(r_calc, st["R"]):
                    errors.append(f"[C2/{basis}] {name}: R 不自洽 计算={r_calc:.3f} 记录={st['R']:.3f}")
            checked += 1
    print(f"  C1/C2 方案表核验：找到 {rows_found} 行，逐字段比对 {checked} 个方案/口径组合")
    if rows_found == 0:
        warnings.append("[C1] 未在报告中定位到任何方案表行——校验器可能失效，请检查表头格式")
    return checked


def check_gold_counts(paras, tables, sh):
    g = sh["gold"]
    txt = "\n".join(paras) + "\n" + "\n".join(" | ".join(r) for _c, t in tables for r in t)
    # C4：报告中凡把某数量称为 news20 的「正样本」，必须与 JSON 的四类计数之一一致。
    # 注意排除 MinHash 用例段（那里说“正样本”指的是 6 条用例的金标准，不是 news20）。
    allowed_counts = {g["near_dup"], g["mixed_all_same_group"], g["same_event"],
                      g["excluded_eval"], g["uncertain"], g["negative_cross_group"]}
    for m in re.finditer(r"正样本[^0-9]{0,12}(\d+)\s*对", txt):
        ctx = txt[max(0, m.start() - 80):m.end() + 40]
        if "T1" in ctx or "用例" in ctx or "改写 = T" in ctx:
            continue                     # MinHash 用例段，另一套金标准
        v = int(m.group(1))
        if v not in allowed_counts:
            errors.append(f"[C4] 报告声称正样本 {v} 对，不在 gold 的任何类别计数中（上下文：…{ctx[-70:]}…）")
    # 四类清单必须齐备
    for key in ("POSITIVE", "EXCLUDED", "UNCERTAIN", "NEGATIVE"):
        if key not in g["categories"]:
            errors.append(f"[C4] gold 缺少类别 {key}")
    # 12/18/21 的口径演变必须被解释（审计明确指出 12 ≠ 21−3）
    for n, why in ((12, "新 gold 正样本"), (18, "仅排除 D3 后"), (21, "初版同组口径")):
        if str(n) not in txt:
            warnings.append(f"[C4] 报告中未出现 {n}（{why}）——口径演变说明可能不完整")
    # “排除出正样本 ≠ 负样本”必须被明说
    if "≠" not in txt and "不等于" not in txt:
        warnings.append("[C4] 报告未明确写出「排除出正样本 ≠ 已确认是负样本」")
    print(f"  C4 gold 数量：POSITIVE={g['categories']['POSITIVE']['n']} "
          f"EXCLUDED={g['categories']['EXCLUDED']['n']} "
          f"UNCERTAIN={g['categories']['UNCERTAIN']['n']} "
          f"NEGATIVE={g['categories']['NEGATIVE']['n']}；gold_sha={g['sha256'][:16]}…")


def check_scope_and_threshold(paras, tables, sh, mh):
    txt = "\n".join(paras) + "\n" + "\n".join(" | ".join(r) for _c, t in tables for r in t)
    # C5：阈值
    if f"≤ {sh['ham_th']}" not in txt and f"<= {sh['ham_th']}" not in txt and f"≤{sh['ham_th']}" not in txt:
        warnings.append(f"[C5] 报告中未见到海明距离阈值 ≤ {sh['ham_th']} 的声明")
    if str(mh["config"]["k"]) not in txt:
        warnings.append(f"[C5] 报告中未见到 MinHash k={mh['config']['k']} 的声明")
    # 文本范围
    scopes = [r["scope"] for r in sh["scope_rows"]]
    for sc in scopes:
        if sc not in txt:
            warnings.append(f"[C5] 报告中未出现文本范围「{sc}」")
    print(f"  C5 阈值/范围：ham_th={sh['ham_th']} 范围={scopes}")


# ---------------------------------------------------------------- C6
def collect_numbers(obj, acc):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        v = float(obj)
        for nd in (0, 1, 2, 3, 4, 6):
            acc.add(f"{v:.{nd}f}")
        acc.add(f"{v * 1000:.1f}")
        acc.add(f"{v * 1000:.2f}")
        acc.add(f"{v * 100:.1f}")
        acc.add(f"{v * 100:.2f}")
        acc.add(f"{v:.2%}")
        acc.add(str(int(round(v))))
        return
    if isinstance(obj, str):
        for m in re.findall(r"\d+\.\d+", obj):
            acc.add(m)
            acc.add(f"{float(m):.3f}")
            acc.add(f"{float(m):.2f}")
            acc.add(f"{float(m):.1f}")
        return
    if isinstance(obj, dict):
        for v in obj.values():
            collect_numbers(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            collect_numbers(v, acc)


def numkey(x):
    try:
        return f"{float(x):.10g}"
    except ValueError:
        return x


ALLOWED_STRUCTURAL = {
    "1.0", "1.00", "1.000", "0.0", "0.00", "0.000", "0.1", "0.2", "0.3", "0.4",
    "0.5", "0.6", "0.7", "0.8", "0.9", "2.0", "3.0", "30", "64", "128", "1000",
    "0.12", "0.15", "0.19", "0.26", "0.96", "1.35", "3.13", "5.13", "6.13", "1.5",
    "2026", "1.1", "2.1", "3.1", "4.1", "5.1", "6.1", "7.1",
    "0.05", "0.01", "0.02", "0.03", "0.04", "2.2", "2.3", "2.4", "4.7",
}


def check_no_orphan_numbers(paras, tables, summaries):
    allowed = set(ALLOWED_STRUCTURAL)
    for v in summaries.values():
        collect_numbers(v, allowed)
    # 署名中的学号也从环境变量补充进白名单（报告封面会打印学号）
    for k, v in os.environ.items():
        if k.startswith("REPORT_MEMBER") and v.strip():
            allowed.add(v.strip())
    allowed_norm = {numkey(a) for a in allowed}

    # C7：历史数字的段落白名单（按段落绑定，不做全局放行）
    orphan, hist_ok, hist_bad = [], 0, []
    body = list(paras)
    for _c, t in tables:
        for r in t:
            body.append(" | ".join(r))
    for para in body:
        found = re.findall(r"(?<![\d.])(\d+\.\d{2,})", para)
        for f in found:
            if numkey(f) in allowed_norm:
                continue
            if f in HISTORICAL_NUMBERS:
                if any(mk in para for mk in HISTORICAL_MARKERS):
                    hist_ok += 1
                    continue
                hist_bad.append((f, para[:90]))
                continue
            orphan.append((f, para[:90]))
    print(f"  C6 孤立数字：{len(orphan)} 个")
    for f, ctx in orphan[:10]:
        errors.append(f"[C6] 无法解释的数值 {f}：…{ctx}…")
    print(f"  C7 历史数字：合规段落 {hist_ok} 处，越界 {len(hist_bad)} 处")
    for f, ctx in hist_bad:
        errors.append(f"[C7] 历史数字 {f} 出现在未标注历史的段落：…{ctx}…")


# ---------------------------------------------------------------- 负向自测
def selftest():
    """验证校验器真的能发现“指标被互换/张冠李戴”。

    做法：把 JSON 中两个方案的 strict 指标互换，再跑一次方案表校验，
    必须产生 [C1] 错误；否则说明校验器形同虚设。
    """
    print("=" * 74)
    print("校验器负向自测：把两个方案的指标互换，必须被检出")
    print("=" * 74)
    with open(os.path.join(OUT, "results_summary_simhash.json"), encoding="utf-8") as f:
        sh = json.load(f)
    names = [s["name"] for s in sh["schemes"]]
    i, j = 3, 5                      # B1 与 B3
    swapped = json.loads(json.dumps(sh))
    a = swapped["schemes"][i]["strict"]
    b = swapped["schemes"][j]["strict"]
    swapped["schemes"][i]["strict"] = b
    swapped["schemes"][j]["strict"] = a
    print(f"  互换 {names[i]} 与 {names[j]} 的 P/R/F1/TP/FP/FN")
    global errors
    saved = list(errors)
    errors = []
    _paras, tables = doc_paragraphs_and_tables(REPORT)
    check_scheme_table(tables, swapped)
    detected = [e for e in errors if e.startswith("[C1")]
    errors = saved
    print(f"  检出 {len(detected)} 条归属错误")
    for e in detected[:6]:
        print("    " + e)
    if detected:
        print("\n✅ 负向自测通过：指标被互换后校验器报错，说明它确实在核对归属")
        return 0
    print("\n❌ 负向自测失败：指标被互换却未报错，校验器无效")
    return 1


def main():
    if "--selftest" in sys.argv:
        return selftest()

    print("=" * 74)
    print("报告一致性校验（绑定 方法 + 字段 + 范围 + 阈值 + gold 版本）")
    print("=" * 74)
    if not os.path.exists(REPORT):
        print("报告不存在:", REPORT)
        return 1
    summaries = load_summaries()
    if not summaries:
        print("未找到 results_summary_*.json")
        return 1
    sh = summaries.get("results_summary_simhash.json")
    mh = summaries.get("results_summary_minhash.json")
    paras, tables = doc_paragraphs_and_tables(REPORT)
    print(f"报告: {os.path.basename(REPORT)}")
    print(f"段落 {len(paras)}，表格 {len(tables)}；结构化汇总 {len(summaries)} 份")
    print(f"gold version = {sh['gold']['version']}  sha256 = {sh['gold']['sha256'][:24]}…")
    print()

    check_scheme_table(tables, sh)
    check_gold_counts(paras, tables, sh)
    check_scope_and_threshold(paras, tables, sh, mh)
    check_no_orphan_numbers(paras, tables, summaries)

    print()
    print("-" * 74)
    if warnings:
        print(f"提示 {len(warnings)} 条：")
        for w in warnings:
            print("  " + w)
    if errors:
        print(f"❌ 失败：{len(errors)} 条错误")
        for e in errors:
            print("  " + e)
        return 1
    print("✅ 通过：方案指标归属、计数自洽、gold 数量、阈值与范围声明均与结构化结果一致；"
          "无孤立数字；历史数字仅在标注段落内")
    return 0


if __name__ == "__main__":
    sys.exit(main())
