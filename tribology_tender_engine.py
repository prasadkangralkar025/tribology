#!/usr/bin/env python3
"""
Tribology Tender Engine (India)
================================
Finds active India-based tenders related to tribology: friction & wear
testing, tribometers, surface roughness / surface measurement equipment.
"""

import argparse
import csv
import datetime as dt
import re
import sys
import time
from urllib.parse import quote_plus

try:
    import feedparser
except ImportError:
    sys.exit("Missing dependency. Run: pip install requests feedparser")

import requests

KEYWORDS = [
    "tribology tender",
    "tribometer tender",
    "friction and wear tester tender",
    "wear testing machine tender",
    "surface roughness tester tender",
    "surface roughness measurement tender",
    "profilometer tender",
    "friction wear testing equipment tender",
    "pin on disc tribometer tender",
    "four ball tester tender",
]

INDIA_TENDER_SITES = [
    "gem.gov.in",
    "eprocure.gov.in",
    "etenders.gov.in",
    "tendersbazaar.com",
    "tendersinfo.com",
    "biddetail.com",
    "mstcecommerce.com",
    "tenderdetail.com",
    "bidassist.com",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

HEADERS = {"User-Agent": USER_AGENT}


def fetch_google_news_rss(query, days=14):
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"
    results = []
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"  [!] RSS fetch failed for '{query}': {e}")
        return results

    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    for entry in feed.entries:
        published = None
        if getattr(entry, "published_parsed", None):
            published = dt.datetime(*entry.published_parsed[:6], tzinfo=dt.timezone.utc)
        if published and published < cutoff:
            continue
        results.append({
            "title": entry.get("title", "").strip(),
            "link": entry.get("link", "").strip(),
            "source": entry.get("source", {}).get("title", "") if hasattr(entry, "source") else "",
            "published": published.strftime("%Y-%m-%d") if published else "",
            "matched_keyword": query,
            "origin": "google_news_rss",
        })
    return results


def fetch_all_india_sources(days=14):
    all_hits = []
    for kw in KEYWORDS:
        site_filter = " OR ".join(f"site:{s}" for s in INDIA_TENDER_SITES)
        query = f'{kw} ({site_filter})'
        print(f"  Searching: {kw} ...")
        hits = fetch_google_news_rss(query, days=days)
        all_hits.extend(hits)
        time.sleep(1)

        broad_hits = fetch_google_news_rss(f"{kw} India", days=days)
        all_hits.extend(broad_hits)
        time.sleep(1)
    return all_hits


def fetch_gem_bidplus(keyword):
    hits = []
    try:
        resp = requests.get(
            "https://bidplus.gem.gov.in/all-bids",
            params={"searchBid": keyword},
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code != 200:
            return hits
        bid_links = re.findall(r'href="(/showbidDocument/\d+)"', resp.text)
        for link in bid_links[:20]:
            hits.append({
                "title": f"GeM bid matching '{keyword}'",
                "link": f"https://bidplus.gem.gov.in{link}",
                "source": "GeM",
                "published": "",
                "matched_keyword": keyword,
                "origin": "gem_bidplus_best_effort",
            })
    except Exception as e:
        print(f"  [!] GeM bidplus fetch skipped ({e})")
    return hits


def dedupe(hits):
    seen = set()
    deduped = []
    for h in hits:
        key = h["link"].split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(h)
    return deduped


def save_csv(hits, path):
    fields = ["title", "published", "source", "matched_keyword", "origin", "link"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for h in hits:
            writer.writerow({k: h.get(k, "") for k in fields})


def main():
    parser = argparse.ArgumentParser(description="India tribology tender finder")
    parser.add_argument("--days", type=int, default=14, help="Only include results from the last N days")
    parser.add_argument("--out", type=str, default="tribology_tenders_india.csv", help="Output CSV path")
    parser.add_argument("--try-gem", action="store_true", help="Also attempt best-effort GeM bidplus scrape")
    args = parser.parse_args()

    print(f"Scanning India tender sources for tribology/friction/wear/surface-measurement keywords "
          f"(last {args.days} days)...\n")

    all_hits = fetch_all_india_sources(days=args.days)

    if args.try_gem:
        for kw in ["tribometer", "friction wear tester", "surface roughness tester"]:
            all_hits.extend(fetch_gem_bidplus(kw))

    all_hits = dedupe(all_hits)
    all_hits.sort(key=lambda h: h.get("published", ""), reverse=True)

    save_csv(all_hits, args.out)

    print(f"\nFound {len(all_hits)} unique results. Saved to: {args.out}\n")
    for h in all_hits[:15]:
        print(f"- [{h['published'] or 'n/a'}] {h['title']}")
        print(f"  {h['link']}")
    if len(all_hits) > 15:
        print(f"... and {len(all_hits) - 15} more in the CSV.")


if __name__ == "__main__":
    main()
