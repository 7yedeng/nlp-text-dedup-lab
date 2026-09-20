# 中文文本特征表示与内容重复理解（NLP 实验一）

围绕「文本特征表示 → 文本相似度 → 内容重复识别」这条主线，用**真实抓取的中文新闻语料**完成 4 组实验，
全部指标可复现、结论可验证：TF-IDF 特征表示与相似检索、MinHash + LSH 短文本去重、
预训练词向量（腾讯 AI Lab）文档表示与聚类、TF-IDF 加权 SimHash 网页新闻近似重复检测。

- 语料：**全部真实抓取**（网易滚动新闻接口 / 新浪滚动新闻 API），共 2 579 条标题 + 170 篇正文
- 结果：4 个实验脚本均输出 `out/*_results.txt` 指标 + `out/figures/*.png` 可视化
- 报告：`out/姓名+学号+第1次实验报告.docx`（含原理、白底代码截图、P/R/F1 表、可视化、学习笔记）
- 复现：所有随机过程固定随机种子（`seed=42`），同一环境下结果确定

---

## 一、实验内容与结果速览

| 实验 | 方法要点 | 关键结果 |
| --- | --- | --- |
| 一(1) TF-IDF 文本特征表示 | jieba 分词 + 停用词，`TfidfVectorizer(max_features=1000, ngram_range=(1,2))`，余弦相似度 Top-10 | 语料 2 579 条 → 矩阵 `(2579, 1000)`；Top-10 相似对中多对相似度 = 1.0000 |
| 一(2) MinHash + LSH 短文本去重 | 词级 1+2-gram shingle；MinHash 签名 k=128（`h_i(x)=(a_i·x+b_i) mod (2^61-1)`）；LSH band 分桶 | MinHash 估计 Jaccard 平均绝对误差 **0.0064**（最大 0.0239）；阈值 0.1 处精确 Jaccard F1 = 1.000，MinHash F1 = 0.909 |
| 二(1) 预训练词向量 | 腾讯 AI Lab 中文词向量（Gensim `KeyedVectors`）→ 语义推理 + 12 组词对相似度 + 词向量平均池化文档向量 + PCA/t-SNE + KMeans | 143 613 词 × 200 维；类比推理 6 组命中 3 组（王后 / 巴黎 / 英国）；150 篇文档向量 `(150, 200)`，类内相似度 0.9081 > 类间 0.7993；KMeans（K=3）**Purity 0.9400 / ARI 0.8319** |
| 二(2) 加权 SimHash | 20 篇网页新闻，64 位指纹，TF-IDF 加权 + 停用词降权，海明距离 ≤ 3 判重，与等权 SimHash 对比 | **加权：P=1.000 R=0.476 F1=0.645**；等权：P=0.192 R=0.714 F1=0.303（误报率显著更高） |

### 实验一(1)：TF-IDF 特征表示（[exp1_tfidf.py](exp1_tfidf.py)）

- 词频最高 20 词的平均 TF-IDF 权重柱状图：`out/figures/exp1_tfidf_top20.png`，权重最高的是「电影」（0.4614）
- 值得注意的现象：「AI」词频 84 却平均权重 0.0000 —— 该词**未进入 `max_features=1000` 的特征集**
  （在大量文档中均匀出现，TF-IDF 打分不足以进入前 1000 维），说明高频 ≠ 高区分度
- Top-10 相似对中出现相似度 = 1.0000 的「近重复标题」（如仅差一个空格/一个期号），为后续去重实验埋下伏笔

### 实验一(2)：MinHash + LSH（[exp1_minhash.py](exp1_minhash.py)）

6 条测试用例（`data/short_texts.txt`）：T1-T2 完全重复、T1-T3 轻度修改、T1-T4 中度改写、T5/T6 完全不相关。

| 文档数 | 精确 Jaccard | MinHash 全量对比 | LSH 建桶 + 候选 |
| --- | --- | --- | --- |
| 6 | 0.03 ms | 3.23 ms | 0.07 ms |
| 50 | 0.95 ms | 30.30 ms | 0.66 ms |
| 200 | 14.46 ms | 172.57 ms | 6.44 ms |
| 500 | 108.54 ms | 709.46 ms | 30.47 ms |

- 精确 Jaccard 与 MinHash 全量对比均为 **O(n²)**，文档数增大后 MinHash 因签名逐位比较开销更大
- LSH 通过分桶把候选对压到远小于全量，是最快的路径；但**分桶参数直接决定召回与误报**：
  `(b=16, r=8)` 只召回 1 对（漏检 T1-T3/T1-T4），`(b=64, r=2)` 召回 6 对（其中 3 对经 MinHash 回验为误报）
- 因此工程上通常「LSH 粗筛候选 → MinHash 相似度回验 → 阈值判定」三段式串联

### 实验二(1)：预训练词向量（[exp2_wordvec.py](exp2_wordvec.py)）

- 语义推理（类比）：`国王 − 男人 + 女人 ≈ 王后`(0.705)、`北京 − 中国 + 法国 ≈ 巴黎`(0.686)、`中国 − 北京 + 伦敦 ≈ 英国`(0.769) 命中；
  `父亲 − 儿子 + 母亲` 返回「父母亲」而非「女儿」，说明词向量对**反义/性别方向的组合并不稳定**
- 文档表示：体育 / 科技 / 娱乐各 50 篇，词向量平均池化（仅累加词表内词），类内平均相似度 0.9081 > 类间 0.7993
- PCA / t-SNE 降维可视化 + KMeans 聚类（形状=真实主题，颜色=聚类簇）：`out/figures/exp2_wordvec_pca_tsne.png`
- 聚类混淆矩阵显示误差集中在「体育」被拆到三个簇（41 / 7 / 2），科技、娱乐几乎完美分离

### 实验二(2)：TF-IDF 加权 SimHash（[exp2_simhash.py](exp2_simhash.py)）

- 数据集 `data/news20/`（含 `manifest.json` 分组标签）：21 个真重复对，含转载改写簇 R1/R2、同事件不同报道 D1/D2/D3、无关主题 U1/U2/U3
- 加权 vs 等权：等权 SimHash 把 4 篇「扎克伯格专访」判成与几乎所有其他文档重复（P=0.192），
  **TF-IDF 加权 + 停用词降权后查准率提升到 1.000**（无一处误报，F1 0.303 → 0.645）
- 阈值扫描：阈值取 3（作业要求）时加权 F1 = 0.645；阈值放宽到 6~10 时 F1 可达 0.765（召回换查准）

---

## 二、目录结构

```
.
├── exp1_tfidf.py             # 实验一(1) TF-IDF 特征表示与 Top-10 相似对
├── exp1_minhash.py           # 实验一(2) MinHash(k=128) + LSH 短文本去重
├── exp2_wordvec.py           # 实验二(1) 预训练词向量：类比/相似度/文档向量/PCA·t-SNE/KMeans
├── exp2_simhash.py           # 实验二(2) 64 位 TF-IDF 加权 SimHash 与海明距离判重
│
├── data/                     # 语料（均为真实抓取）
│   ├── titles.txt            #   2 579 条中文新闻标题（每行一条）
│   ├── short_texts.txt       #   6 条去重测试用例
│   ├── sports|tech|ent/      #   体育/科技/娱乐各 50 篇正文（含 title= / source= / category= 元信息）
│   └── news20/               #   20 篇网页新闻 + manifest.json（分组真值标签）
│
├── model/                    # 词向量模型目录（.gitignore 已忽略，需自行下载，见下）
├── out/                      # 全部产物
│   ├── *_results.txt         #   4 个实验的指标落盘结果
│   ├── figures/              #   5 张可视化图
│   ├── screenshots/          #   8 张白底关键代码截图（供报告使用）
│   └── 姓名+学号+第1次实验报告.docx
│
├── docs/
│   └── 实验一-内容重复理解技术综合实验(作业要求).docx
├── tools/                    # 数据获取与报告生成的辅助脚本
│   ├── scraper.py            #   真实新闻抓取（列表页/滚动接口 → 详情页正文解析 → 结构化落盘）
│   ├── fetch.py              #   urllib 直连抓取工具（编码修正、正文清洗）
│   ├── fetch_titles.py       #   批量补充新闻标题语料
│   ├── make_news20.py        #   构造 news20 数据集与分组真值（含同义词替换改写）
│   ├── make_screenshots.py   #   关键代码 → 白底截图
│   └── build_report.py       #   由结果文件 + 图片生成实验报告 Word
│
├── requirements.txt
└── LICENSE
```

## 三、环境与依赖

```bash
python -m pip install -r requirements.txt
```

- Python 3.8（已在 3.8.7 / Windows 验证），其余为纯 Python + 科学计算栈，无 GPU 需求
- 实验中文字体依赖 `Microsoft YaHei` / `SimHei`（Windows 自带；其它系统请自行指定可用中文字体）

## 四、如何运行

```bash
# 实验一(1)：TF-IDF（约数秒，无需模型）
python exp1_tfidf.py

# 实验一(2)：MinHash + LSH（含批量规模计时，秒级）
python exp1_minhash.py

# 实验二(1)：预训练词向量（需先准备 model/ 下的词向量文件，见下）
python exp2_wordvec.py

# 实验二(2)：加权 SimHash
python exp2_simhash.py
```

四个脚本各自读写 `data/` 与 `out/`，可独立运行；全部结果重新生成后，可再执行
`python tools/make_screenshots.py && python tools/build_report.py` 重建报告。

### 词向量模型准备

仓库**不包含**预训练词向量（体积过大）。实验二(1) 使用的模型为
**腾讯 AI Lab 中文词向量（轻量版，200 维）**，需自行下载后转换为 word2vec 二进制格式，
放置为 `model/light_Tencent_AILab_ChineseEmbedding.bin`（脚本用
`KeyedVectors.load_word2vec_format(..., binary=True)` 加载）。

下载入口：腾讯 AI Lab 中文词向量 <https://ai.tencent.com/ailab/nlp/en/download.html>

> 说明：本仓库结果基于 143 613 词 × 200 维的词向量子集得到，若替换为其它版本词向量，
> 词对相似度与聚类指标会随之变化，但脚本与评估流程不变。

## 五、数据说明

| 数据 | 规模 | 获取方式 |
| --- | --- | --- |
| `data/titles.txt` | 2 579 条标题 | 新浪滚动新闻 API（`feed.mix.sina.com.cn/api/roll/get`）多频道分页聚合 |
| `data/sports/` `tech/` `ent/` | 各 50 篇 | 网易滚动新闻接口（GBK JSON）+ 详情页正文解析（requests + BeautifulSoup/lxml） |
| `data/news20/` | 20 篇 + 真值 | 由上表真实文章按规则构造：源文 / 转载（换标题）/ 轻度改写 / 中度改写 / 同事件不同报道 / 无关主题 |
| `data/short_texts.txt` | 6 条 | 人工设计：完全重复 / 轻度修改 / 中度改写 / 完全不相关 |

正文文件格式（便于机器解析）：

```
title=标题
source=来源|URL
category=类别

正文……
```

抓取脚本仅使用公开接口与浏览器 UA 标识，未使用任何账号、Cookie 或密钥；
数据仅用于课程实验，版权归原媒体所有。

## 六、复现与验证要点

- **确定性**：MinHash 的 `a_i / b_i`、KMeans 初始化、采样等均固定 `random_state=42`；重跑得到的指标一致
- **可核对**：所有结论数字都能在 `out/*_results.txt` 中找到对应行，不存在只出现在报告里的「孤立数字」
- **评估口径**：实验一(2) 与实验二(2) 的 P/R/F1 都以数据集自带的真值标签（`manifest.json` / 用例设计）为准，
  正样本定义为「同簇的近似重复对」，负样本为跨簇对

## 七、已知限制与可改进方向

- 停用词表为内置的常用词表（非通用停用词文件），不同语料下可能需要调整
- 实验一(2) 的阈值分析仅基于 6 条人工用例，统计意义有限；生产环境应在更大标注集上标定阈值
- 词向量平均池化忽略词序与词重要性（可对比 TF-IDF 加权池化 / SIF 加权）
- 实验二(2) 的真值标签由构造规则生成，属于「规则真值」而非人工双盲标注
- SimHash 召回率偏低（0.476）主要来自中度改写样本：64 位指纹对长文改写不够敏感，可考虑分段 SimHash 或多指纹组合

## 八、许可

代码以 [MIT License](LICENSE) 开源；语料来自公开新闻网站，仅用于教学实验，请勿用于商业用途。
