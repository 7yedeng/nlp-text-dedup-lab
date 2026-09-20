# -*- coding: utf-8 -*-
"""真实新闻抓取器：列表页/RSS 收集链接，详情页解析正文，结构化落盘 data/<类别>/编号.txt
格式: 第一行 title=标题 | 第二行 source=来源|url | 第三行 category=类别 | 空行后正文
"""
import requests, re, os, time, json, random, sys
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "data")
os.makedirs(BASE, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

session = requests.Session()
session.headers.update(HEADERS)

def get(url, timeout=15, tries=3):
    for i in range(tries):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 200:
                # 修正编码
                if r.encoding is None or r.encoding.lower() in ("iso-8859-1", "ascii"):
                    r.encoding = "utf-8"
                return r
        except Exception as e:
            pass
        time.sleep(1.5 + i)
    return None

# ---------------- 列表源 ----------------
def sina_rss_titles():
    """新浪 RSS 各频道抓标题, 返回 [(title, url)]"""
    feeds = [
        "http://rss.sina.com.cn/news/marquee/ddt.xml",
        "http://rss.sina.com.cn/news/china/focus15.xml",
    ]
    out = []
    for f in feeds:
        r = get(f)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "lxml")
        for item in soup.find_all("item"):
            t = item.find("title")
            l = item.find("link")
            if t and l and t.text.strip():
                out.append((t.text.strip(), l.text.strip()))
    return out

def netease_news_roll(cat="ent"):
    """网易滚动新闻 JSON(GBK 编码): https://temp.163.com/special/00804KVA/cm_${cat}.js"""
    js_url = f"https://temp.163.com/special/00804KVA/cm_{cat}.js"
    r = get(js_url)
    if not r:
        return []
    raw = r.content
    try:
        txt = raw.decode("gbk", errors="ignore")
    except Exception:
        txt = r.text
    m = re.search(r"data_callback\((.*)\)", txt, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []
    out = []
    for item in data:
        title = (item.get("title") or "").strip()
        url = item.get("docurl") or item.get("url") or ""
        if title and url:
            out.append((title, url))
    return out

def cnbeta_rss():
    """cnBeta RSS -> [(title,url)]"""
    r = get("https://www.cnbeta.com.tw/backend.php")
    if not r:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    out = []
    for item in soup.find_all("item"):
        t = item.find("title"); l = item.find("link")
        if t and l:
            out.append((t.text.strip(), l.text.strip()))
    return out

def netease_channel_links(url, dom_filter):
    """网易频道页抓取新闻链接 [(title,url)]"""
    r = get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 8:
            continue
        if dom_filter in href and re.match(r"https?://", href):
            out.append((title, href))
    # 去重保持顺序
    seen, res = set(), []
    for t, u in out:
        if u not in seen:
            seen.add(u); res.append((t, u))
    return res

# ---------------- 详情解析 ----------------
def parse_article(url, html, domain):
    soup = BeautifulSoup(html, "lxml")
    title = None
    content = ""
    if "cnbeta" in domain:
        t = soup.find("h1")
        title = t.get_text(strip=True) if t else None
        div = soup.find("div", class_=re.compile(r"article_content|article_Content"))
        if div:
            content = div.get_text("\n", strip=True)
    elif "sina" in domain:
        t = soup.find("h1", class_="main-title") or soup.find("title")
        title = t.get_text(strip=True) if t else None
        div = soup.find("div", id="artibody")
        if div:
            content = div.get_text("\n", strip=True)
    elif "163" in domain:
        t = soup.find("h1") or soup.find("title")
        title = t.get_text(strip=True) if t else None
        div = soup.find("div", class_="post_body") or soup.find("div", class_="post_text") or soup.find("div", id="content")
        if div:
            content = div.get_text("\n", strip=True)
    elif "ifeng" in domain:
        t = soup.find("h1")
        title = t.get_text(strip=True) if t else None
        div = soup.find("div", id="artical_real") or soup.find("div", class_="main_content")
        if div:
            content = div.get_text("\n", strip=True)
    # 兜底：<p> 拼接
    if not content:
        ps = soup.find_all("p")
        content = "\n".join(p.get_text(strip=True) for p in ps if len(p.get_text(strip=True)) > 10)
    if title is None:
        t = soup.find("title")
        title = t.get_text(strip=True) if t else url
    # 清洗
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in content.split("\n")]
    lines = [ln for ln in lines if ln and "function" not in ln and "javascript" not in ln.lower()]
    content = "\n".join(lines)
    # 去掉来源/责任编辑尾注
    content = re.sub(r"^(来源|责任编辑|编辑|记者)[:：].*$", "", content, flags=re.M)
    return title, content

def fetch_article(url):
    r = get(url)
    if not r:
        return None
    domain = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    title, content = parse_article(url, r.text, domain)
    return title, content

# ---------------- 落盘 ----------------
def save(category, title, url, content, idx):
    folder = os.path.join(BASE, category)
    os.makedirs(folder, exist_ok=True)
    fn = os.path.join(folder, f"{idx:03d}.txt")
    with open(fn, "w", encoding="utf-8") as f:
        f.write(f"title={title}\n")
        f.write(f"source={url}\n")
        f.write(f"category={category}\n")
        f.write("\n")
        f.write(content)
    return fn

def collect(category, url_title_pairs, target, min_len=100):
    """抓取 target 篇正文"""
    got = 0
    seen = set()
    for idx, (title, url) in enumerate(url_title_pairs):
        if got >= target:
            break
        if url in seen:
            continue
        seen.add(url)
        res = fetch_article(url)
        if not res:
            continue
        t, c = res
        if len(c) < min_len:
            continue
        got += 1
        save(category, t, url, c, got)
        print(f"  [{category}] {got}/{target} {t[:30]}... len={len(c)}", flush=True)
        time.sleep(random.uniform(0.4, 1.0))
    return got

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "tech"
    if mode == "sina_titles":
        items = sina_rss_titles()
        print("sina titles:", len(items))
    elif mode == "titles":
        # 收集全频道标题语料 -> data/titles.txt
        channels = ["whole", "society", "ent", "sports", "tech", "auto", "money", "health", "mil", "edu", "travel"]
        all_items = []
        for ch in channels:
            items = netease_news_roll(ch)
            print(f"  channel {ch}: {len(items)}")
            all_items.extend(items)
        seen, titles, urls = set(), [], []
        for t, u in all_items:
            if t not in seen:
                seen.add(t)
                titles.append(t); urls.append(u)
        with open(os.path.join(BASE, "titles.txt"), "w", encoding="utf-8") as f:
            for t in titles:
                f.write(t + "\n")
        print("total titles saved:", len(titles))
    elif mode in ("ent", "sports", "tech"):
        items = netease_news_roll(mode)
        print(f"{mode}: {len(items)} items")
        got = collect(mode, items, 50)
        print(f"{mode} collected: {got}")
    elif mode == "cnbeta":
        items = cnbeta_rss()
        print("cnbeta:", len(items))
        for t, u in items[:5]:
            print("  ", t, u)
    else:
        print("unknown")