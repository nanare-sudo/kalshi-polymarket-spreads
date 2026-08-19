#!/usr/bin/env python3
"""Baut live.json für das Neuronaldensity-Dashboard.

Läuft in GitHub Actions (serverseitig — Kalshi blockt Browser-Requests mit Origin-Header).
Quellen: Kalshi trade-api v2, Polymarket Gamma, NWS/METAR. Alle öffentlich, keine Keys.

    python3 scripts/build_live_data.py
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "data", "live.json")
UA = "neuronaldensity-dashboard/1.0 (+https://nanare-sudo.github.io/kalshi-polymarket-spreads/)"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA = "https://gamma-api.polymarket.com"

# Wetterstationen der wichtigsten Kalshi-Temperaturserien
WEATHER_SERIES = {
    "KXHIGHNY": ("New York", "KNYC"), "KXHIGHCHI": ("Chicago", "KMDW"),
    "KXHIGHMIA": ("Miami", "KMIA"), "KXHIGHAUS": ("Austin", "KAUS"),
    "KXHIGHDEN": ("Denver", "KDEN"), "KXHIGHTPHX": ("Phoenix", "KPHX"),
    "KXHIGHPHIL": ("Philadelphia", "KPHL"), "KXHIGHLAX": ("Los Angeles", "KLAX"),
}


def get(url, params=None, retries=3):
    if params:
        url = f"{url}?{urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if attempt == retries - 1:
                print(f"  ! failed {url[:70]}: {e}")
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def dollars(obj, base):
    """Kalshi Aug-2026: *_dollars Strings, Fallback auf legacy Integer-Cents."""
    v = obj.get(f"{base}_dollars")
    if v is not None:
        try:
            return float(v)
        except (TypeError, ValueError):
            pass
    c = obj.get(base)
    return c / 100 if isinstance(c, (int, float)) else None


def count(obj, base):
    v = obj.get(f"{base}_fp")
    if v is not None:
        try:
            return float(v)
        except (TypeError, ValueError):
            pass
    c = obj.get(base)
    return c if isinstance(c, (int, float)) else None


def clean_title(t):
    t = re.sub(r"\s+", " ", (t or "").strip())
    return t[:110]


# ---------------------------------------------------------------- Kalshi
def kalshi_markets(limit=600):
    """Aktivste offene Kalshi-Märkte über /events mit nested markets.

    WICHTIG: /markets ohne Filter liefert MVE-Kombinationsmärkte mit unbrauchbaren
    Sammel-Titeln ("yes A,yes B,yes C") und Volumen 0. Nur /events?with_nested_markets
    gibt echte Einzelmärkte mit lesbaren Titeln und Volumendaten.
    """
    out, cursor, pages = [], None, 0
    while len(out) < limit and pages < 12:
        body = get(f"{KALSHI}/events", {"status": "open", "limit": 200,
                                        "with_nested_markets": "true", "cursor": cursor})
        if not body:
            break
        events = body.get("events", [])
        for ev in events:
            ev_title = clean_title(ev.get("title") or ev.get("sub_title"))
            series = ev.get("series_ticker") or (ev.get("event_ticker", "").split("-")[0])
            for m in ev.get("markets", []):
                price = dollars(m, "last_price")
                if price is None or not 0 < price < 1:
                    continue
                mt = clean_title(m.get("title"))
                sub = clean_title(m.get("yes_sub_title") or m.get("subtitle"))
                out.append({
                    "venue": "kalshi", "id": m.get("ticker"), "series": series,
                    "title": mt or ev_title,
                    "sub": sub or "",
                    "event_title": ev_title, "category": ev.get("category"),
                    "prob": round(price * 100, 1),
                    "vol24": round(count(m, "volume_24h") or 0),
                    "oi": round(count(m, "open_interest") or 0),
                    "bid": dollars(m, "yes_bid"), "ask": dollars(m, "yes_ask"),
                    "close": m.get("close_time"),
                })
        cursor = body.get("cursor")
        pages += 1
        if not cursor or not events:
            break
    out.sort(key=lambda m: -m["vol24"])
    return out[:limit]


# ---------------------------------------------------------------- Polymarket
def poly_markets(limit=600):
    out = []
    for offset in range(0, limit, 100):
        body = get(f"{GAMMA}/markets", {"active": "true", "closed": "false", "limit": 100,
                                        "offset": offset, "order": "volume24hr", "ascending": "false"})
        if not body:
            break
        for m in body:
            try:
                prices = json.loads(m.get("outcomePrices") or "[]")
                p = float(prices[0]) if prices else None
            except Exception:
                p = None
            if p is None or not 0 < p < 1:
                continue
            out.append({
                "venue": "polymarket", "id": str(m.get("id")),
                "title": clean_title(m.get("question")),
                "sub": clean_title((m.get("groupItemTitle") or "")),
                "prob": round(p * 100, 1),
                "vol24": round(float(m.get("volume24hr") or 0)),
                "liq": round(float(m.get("liquidity") or 0)),
                "close": m.get("endDate"),
                "slug": m.get("slug"),
            })
        if len(body) < 100:
            break
    return out


# ---------------------------------------------------------------- Cross-venue gaps
STOP = set("will the be to in a an of on for at by is are and or not this that with from as it".split())


def tokens(s):
    return {w for w in re.findall(r"[a-z0-9]{3,}", (s or "").lower()) if w not in STOP}


def find_gaps(kalshi, poly, top=14):
    """IDF-gewichtetes Token-Matching (vereinfachte Variante der Actor-Pipeline).

    Seltene Tokens ("desantis", "cpi") zählen weit mehr als häufige ("will", "2028").
    Zahlen müssen kompatibel sein, sonst wird das Paar verworfen.
    """
    import math
    from collections import Counter

    pk = [(m, tokens(m["title"] + " " + m["sub"] + " " + m.get("event_title", ""))) for m in kalshi if m["vol24"] > 0]
    pp = [(m, tokens(m["title"] + " " + m["sub"])) for m in poly if m["vol24"] > 0]

    # Geschwister-Legs je Kalshi-Markt: bei Multi-Outcome-Events ("Wer zuerst?") sind die
    # konkurrierenden Outcomes die Subtitles der anderen Märkte desselben Titels.
    # Gruppierung über den Ticker-Prefix (KXOAIANTH-40-OAI / -ANTH), nicht über den Titel:
    # Kalshi schreibt denselben Event mal "OpenAI", mal "Open AI".
    by_event = {}
    for m in kalshi:
        by_event.setdefault((m["id"] or "").rsplit("-", 1)[0], []).append(m)
    sibling_legs = {}
    for group in by_event.values():
        for m in group:
            sibling_legs[m["id"]] = {t for other in group if other["id"] != m["id"]
                                     for t in tokens(other["sub"])}
    df = Counter()
    for _, t in pk + pp:
        df.update(t)
    n = max(1, len(pk) + len(pp))
    idf = {w: math.log(n / (1 + c)) for w, c in df.items()}

    def weight(ts):
        return sum(idf.get(t, 0) for t in ts)

    pairs = []
    for km, kt in pk:
        if len(kt) < 2:
            continue
        for pm, pt in pp:
            if len(pt) < 2:
                continue
            inter = kt & pt
            if len(inter) < 2:
                continue
            union_w = weight(kt | pt)
            if union_w <= 0:
                continue
            jac = weight(inter) / union_w
            if jac < 0.30:
                continue
            # Zahlen müssen übereinstimmen (verhindert "25bp" vs "50bp"-Fehlpaare)
            kn = set(re.findall(r"\d+", km["title"]))
            pn = set(re.findall(r"\d+", pm["title"]))
            if kn and pn and not (kn & pn):
                continue
            # Outcome-Prüfung: gleiche Frage, verschiedene Antwort ist KEIN Paar.
            # Kalshi-Multi-Outcome-Events ("Will OpenAI or Anthropic IPO first?") haben das
            # konkrete Leg im yes_sub_title. Polymarket führt jedes Leg als eigenen Markt,
            # oft ohne groupItemTitle — dann MUSS das Kalshi-Leg im Polymarket-Text auftauchen,
            # sonst vergleichen wir zwei verschiedene Outcomes derselben Frage.
            ks = tokens(km["sub"])
            if ks:
                ptext_raw = (pm["title"] + " " + pm["sub"]).lower()
                if not (ks & tokens(ptext_raw)):
                    continue
                # "Will Anthropic or OpenAI IPO first?" ist auf Polymarket EIN Markt, dessen
                # Preis sich auf den ZUERST genannten bezieht. Kalshi führt beide Legs einzeln.
                # Nur das Leg matchen, das im Polymarket-Titel vorne steht — sonst vergleichen
                # wir "OpenAI zuerst" (12%) mit "Anthropic zuerst" (94,5%).
                others = sibling_legs.get(km["id"], set()) - ks
                my_pos = min((ptext_raw.find(t) for t in ks if ptext_raw.find(t) >= 0), default=-1)
                rival_pos = min((ptext_raw.find(t) for t in others if ptext_raw.find(t) >= 0), default=-1)
                if rival_pos >= 0 and my_pos > rival_pos:
                    continue
            gap = abs(km["prob"] - pm["prob"])
            pairs.append({
                "kalshi": {"title": km["title"], "prob": km["prob"], "vol24": km["vol24"], "id": km["id"]},
                "polymarket": {"title": pm["title"], "prob": pm["prob"], "vol24": pm["vol24"], "slug": pm.get("slug")},
                "gap_pp": round(gap, 1), "match_score": round(jac, 2),
            })
    seen, uniq = set(), []
    for p in sorted(pairs, key=lambda x: (-x["match_score"], -x["gap_pp"])):
        key = p["kalshi"]["id"]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return sorted(uniq[:top * 2], key=lambda x: -x["gap_pp"])[:top]


# ---------------------------------------------------------------- Weather
def weather_block(kalshi_all):
    cities = []
    ids = ",".join(st for _, st in WEATHER_SERIES.values())
    metar = get("https://aviationweather.gov/api/data/metar", {"ids": ids, "format": "json", "hours": 3}) or []
    obs = {}
    for m in metar if isinstance(metar, list) else []:
        sid = m.get("icaoId")
        t = m.get("temp")
        if sid and isinstance(t, (int, float)):
            prev = obs.get(sid)
            rt = m.get("reportTime") or ""
            if not prev or rt > prev["time"]:
                obs[sid] = {"time": rt, "c": t, "f": round(t * 9 / 5 + 32, 1)}

    for series, (city, station) in WEATHER_SERIES.items():
        ms = [m for m in kalshi_all if m["series"] == series]
        if not ms:
            body = get(f"{KALSHI}/markets", {"series_ticker": series, "status": "open", "limit": 40})
            for m in (body or {}).get("markets", []):
                price = dollars(m, "last_price")
                if price is None:
                    continue
                ms.append({"title": clean_title(m.get("title")), "sub": clean_title(m.get("yes_sub_title")),
                           "prob": round(price * 100, 1), "vol24": round(count(m, "volume_24h") or 0),
                           "floor": m.get("floor_strike"), "cap": m.get("cap_strike"), "id": m.get("ticker")})
        else:
            ms = [{**m, "floor": None, "cap": None} for m in ms]
        if not ms:
            continue
        o = obs.get(station)
        cities.append({
            "city": city, "series": series, "station": station,
            "temp_f": o["f"] if o else None, "temp_c": round(o["c"], 1) if o else None,
            "observed_at": o["time"] if o else None,
            "markets": sorted(ms, key=lambda m: -m.get("vol24", 0))[:6],
        })
    return cities


def main():
    print("Fetching Kalshi …")
    kalshi = kalshi_markets()
    print(f"  {len(kalshi)} markets")
    print("Fetching Polymarket …")
    poly = poly_markets()
    print(f"  {len(poly)} markets")

    # Nur ungewisse Märkte: bereits entschiedene 100%/0%-Märkte sind visuell wertlos
    live = [m for m in kalshi + poly if 3 <= m["prob"] <= 97]

    def topic(m):
        """Grobe Themenzuordnung für Vielfalt — Esports darf das Bild nicht dominieren."""
        t = (m["title"] + " " + m.get("event_title", "")).lower()
        if re.search(r"\b(lol|dota|counter-strike|cs2|esports|valorant|bo3|bo5|game \d)\b", t):
            return "esports"
        if re.search(r"\b(nfl|nba|mlb|nhl|soccer|tennis|golf|ufc|f1|premier league|world cup)\b", t):
            return "sports"
        if re.search(r"\b(bitcoin|btc|ethereum|eth|crypto|solana|xrp|coin)\b", t):
            return "crypto"
        if re.search(r"\b(fed|inflation|cpi|gdp|rate|recession|jobs|unemploy|tariff|s&p|nasdaq)\b", t):
            return "economy"
        if re.search(r"\b(openai|anthropic|ai |gpt|llm|nvidia|apple|google|tesla|spacex|launch|nasa)\b", t):
            return "tech"
        if re.search(r"\b(temperature|rain|snow|hurricane|weather|high in|low in)\b", t):
            return "weather"
        if re.search(r"\b(election|president|senate|congress|nominee|parliament|minister|ceasefire|war)\b", t):
            return "politics"
        return "other"

    def pick(pool, n, per_topic):
        """Top-n nach Volumen, aber höchstens per_topic je Thema und keine Titel-Dubletten."""
        out, tcount, seen = [], {}, set()
        for m in sorted(pool, key=lambda m: -m["vol24"]):
            key = (m["title"] + m["sub"]).lower()[:80]
            if key in seen:
                continue
            tp = topic(m)
            if tcount.get(tp, 0) >= per_topic:
                continue
            seen.add(key)
            out.append(m)
            tcount[tp] = tcount.get(tp, 0) + 1
            if len(out) >= n:
                break
        return out

    def interleave(a, b, n):
        """Beide Venues abwechselnd — Polymarkets Volumen würde Kalshi sonst komplett verdrängen."""
        out, i = [], 0
        while len(out) < n and (i < len(a) or i < len(b)):
            if i < len(a):
                out.append(a[i])
            if len(out) < n and i < len(b):
                out.append(b[i])
            i += 1
        return out[:n]

    k_live = [m for m in live if m["venue"] == "kalshi"]
    p_live = [m for m in live if m["venue"] == "polymarket"]

    active = interleave(pick(p_live, 24, 4), pick(k_live, 24, 4), 36)
    # Probability Wall: über alle Wahrscheinlichkeits-Dekaden streuen statt nur Extremwerte
    pool = interleave(pick([m for m in p_live if m["vol24"] > 100], 70, 10),
                      pick([m for m in k_live if m["vol24"] > 20], 70, 10), 120)
    buckets = {}
    for m in pool:
        buckets.setdefault(int(m["prob"] // 10), []).append(m)
    confident = [m for b in sorted(buckets, reverse=True) for m in buckets[b][:4]][:32]
    gaps = find_gaps(kalshi, poly)
    print(f"  {len(gaps)} cross-venue pairs")
    weather = weather_block(kalshi)
    print(f"  {len(weather)} weather cities")

    data = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts": {"kalshi": len(kalshi), "polymarket": len(poly), "gaps": len(gaps)},
        "most_active": active,
        "probability_wall": confident,
        "cross_venue": gaps,
        "weather": weather,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"-> {OUT} ({os.path.getsize(OUT)//1024} KB)")


if __name__ == "__main__":
    main()
