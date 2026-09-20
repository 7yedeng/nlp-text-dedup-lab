# -*- coding: utf-8 -*-
"""urllib 直连抓取工具（绕过不稳定代理）"""
import urllib.request, urllib.parse, time, re, json
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"

def get(url, timeout=15, tries=3, headers=None):
    hdr = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
    if headers:
        hdr.update(headers)
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=hdr)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))
    return None

def netease_roll(cat):
    raw = get(f"https://temp.163.com/special/00804KVA/cm_{cat}.js")
    if not raw:
        return []
    try:
        txt = raw.decode("gbk", errors="ignore")
    except Exception:
        txt = raw.decode("utf-8", errors="ignore")
    m = re.search(r"data_callback\((.*)\)", txt, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []
    return [( (it.get("title") or "").strip(), it.get("docurl") or "") for it in data if it.get("title") and it.get("docurl")]

def parse_article(url, html):
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else None
    content = ""
    for sel in ["div.post_body", "div.post_text", "div#artibody", "div.article_content", "div.article"]:
        div = soup.select_one(sel)
        if div:
            content = div.get_text("\n", strip=True)
            if len(content) > 100:
                break
    if not content or len(content) < 100:
        lines = []
        for p in soup.find_all("p"):
            t = p.get_text(strip=True)
            if len(t) > 10:
                lines.append(t)
        content = "\n".join(lines)
    if title is None:
        t = soup.find("title")
        title = t.get_text(strip=True) if t else url
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in content.split("\n")]
    content = "\n".join([ln for ln in lines if ln])
    content = re.sub(r"^(来源|责任编辑|编辑)[:：].*$", "", content, flags=re.M)
    return title, content

def save(category, title, url, content, idx, base=None):
    import os
    if base is None:
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    folder = os.path.join(base, category)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, f"{idx:03d}.txt"), "w", encoding="utf-8") as f:
        f.write(f"title={title}\nsource={url}\ncategory={category}\n\n{content}")