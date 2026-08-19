#!/usr/bin/env python3
"""Nimmt einen Metrik-Snapshot aller Distributionskanäle und hängt ihn an metrics.csv an.

Nutzt nur öffentliche/authentifizierte Read-APIs, kostet nichts, läuft in ~10 s.
    python3 growth/analytics/snapshot.py
"""
import csv
import json
import os
import subprocess
import urllib.request
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "metrics", "metrics.csv")
ACTORS = ["kalshi-weather-markets", "prediction-spread-scanner", "pdf-text-extractor-rag"]
REPO = "nanare-sudo/kalshi-polymarket-spreads"
PR = ("aarora4/Awesome-Prediction-Market-Tools", 180)


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "growth-snapshot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def gh(path):
    """GitHub via authentifizierte CLI (Token im Keyring)."""
    try:
        out = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=30)
        return json.loads(out.stdout) if out.returncode == 0 else None
    except Exception:
        return None


def actor_stats(slug):
    """Öffentliche Store-Stats (users/runs/reviews) je Actor."""
    data = get_json(f"https://api.apify.com/v2/store?search={slug}&limit=10")
    for it in data["data"]["items"]:
        if it["username"] == "nanare-sudo" and it["name"] == slug:
            st = it.get("stats", {}) or {}
            runs = st.get("publicActorRunStats30Days") or {}
            return {
                "users_total": st.get("totalUsers", 0),
                "users30": st.get("totalUsers30Days", 0),
                "users7": st.get("totalUsers7Days", 0),
                "runs30": runs.get("TOTAL", 0),
                "runs30_ok": runs.get("SUCCEEDED", 0),
                "runs30_failed": runs.get("FAILED", 0),
                "reviews": st.get("actorReviewCount", 0) or 0,
                "rating": round(st.get("actorReviewRating") or 0, 2),
                "bookmarks": st.get("bookmarkCount", 0) or 0,
            }
    return {}


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    rows = []

    for slug in ACTORS:
        s = actor_stats(slug)
        if s:
            rows.append({"ts": ts, "kind": "actor", "name": slug, **s})

    repo = gh(f"repos/{REPO}") or {}
    views = gh(f"repos/{REPO}/traffic/views") or {}
    clones = gh(f"repos/{REPO}/traffic/clones") or {}
    refs = gh(f"repos/{REPO}/traffic/popular/referrers") or []
    rows.append({
        "ts": ts, "kind": "github", "name": REPO,
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "views14": views.get("count", 0),
        "uniques14": views.get("uniques", 0),
        "clones14": clones.get("count", 0),
        "referrers": ";".join(f"{r['referrer']}:{r['count']}" for r in refs[:5]),
    })

    pr = gh(f"repos/{PR[0]}/pulls/{PR[1]}") or {}
    rows.append({
        "ts": ts, "kind": "pr", "name": f"{PR[0]}#{PR[1]}",
        "state": pr.get("state"), "merged": pr.get("merged"),
        "comments": pr.get("comments", 0),
    })

    fields = ["ts", "kind", "name", "users_total", "users30", "users7", "runs30", "runs30_ok",
              "runs30_failed", "reviews", "rating", "bookmarks", "stars", "forks", "views14",
              "uniques14", "clones14", "referrers", "state", "merged", "comments"]
    exists = os.path.exists(OUT)
    with open(OUT, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if not exists:
            w.writeheader()
        w.writerows(rows)

    for r in rows:
        if r["kind"] == "actor":
            print(f"  {r['name']:<28} users30={r['users30']:<4} runs30={r['runs30']:<4} "
                  f"reviews={r['reviews']} bookmarks={r['bookmarks']}")
        elif r["kind"] == "github":
            print(f"  {r['name']:<28} stars={r['stars']} views14={r['views14']} "
                  f"uniques14={r['uniques14']} refs={r['referrers'] or '-'}")
        else:
            print(f"  PR {r['name']:<25} state={r['state']} merged={r['merged']} comments={r['comments']}")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
