# -*- coding: utf-8 -*-
import requests, re, json, os

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0'})

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(BASE, exist_ok=True)

# 已有标题
existing = []
fp = os.path.join(BASE, "titles.txt")
if os.path.exists(fp):
    with open(fp, encoding="utf-8") as f:
        existing = [ln.strip() for ln in f if ln.strip()]
seen = set(existing)

# 1) 新浪滚动 API：多种 lid 频道
lids = [2509, 2510, 2511, 2512, 2513, 2514, 2515, 2516, 2669, 2050]
for lid in lids:
    for page in range(1, 6):
        try:
            r = s.get(f"https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid={lid}&num=50&page={page}",
                      timeout=12)
            js = r.json()
            data = js.get("result", {}).get("data", [])
            for it in data:
                t = (it.get("title") or "").strip()
                if t and t not in seen:
                    seen.add(t)
        except Exception as e:
            print("ERR lid", lid, page, e)
            break
    print(f"sina lid {lid}: total seen = {len(seen)}")

# 2) 网易更多频道
channels = ["lady", "game", "digital", "fund", "house", "taiwan", "reg", "fashion", "woman", "feng", "qt", "rare", "data"]
for ch in channels:
    try:
        r = s.get(f"https://temp.163.com/special/00804KVA/cm_{ch}.js", timeout=12)
        raw = r.content.decode("gbk", errors="ignore")
        m = re.search(r"data_callback\((.*)\)", raw, re.S)
        if not m:
            print(f"netease {ch}: no data")
            continue
        data = json.loads(m.group(1))
        n = 0
        for it in data:
            t = (it.get("title") or "").strip()
            if t and t not in seen:
                seen.add(t); n += 1
        print(f"netease {ch}: +{n} (total {len(seen)})")
    except Exception as e:
        print(f"netease {ch}: ERR {e}")

with open(fp, "w", encoding="utf-8") as f:
    for t in seen:
        f.write(t + "\n")
print("FINAL titles:", len(seen))