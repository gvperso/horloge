#!/usr/bin/env python3
"""Met à jour events.json avec les annonces US à fort impact de la semaine.

Source : calendrier hebdomadaire public de Forex Factory (nfs.faireconomy.media).
Le flux ne couvre que la semaine en cours : on fusionne avec le fichier existant
pour garder les événements déjà connus, et on purge ce qui est passé depuis plus de 2 jours.
Lancé deux fois par jour par .github/workflows/news.yml.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "events.json")
KEEP_PAST = timedelta(days=2)

CATEGORIES = [
    ("Fed", ["fomc", "federal funds", "fed chair", "powell", "fed "]),
    ("Inflation", ["cpi", "ppi", "pce", "inflation"]),
    ("Emploi", ["non-farm", "nonfarm", "unemployment", "jobless", "jolts", "adp", "employment", "payroll"]),
    ("Croissance", ["gdp"]),
    ("Activité", ["ism", "pmi", "philly", "empire"]),
    ("Conso", ["retail", "consumer", "sentiment", "confidence"]),
]


def category(title):
    t = title.lower()
    for name, keys in CATEGORIES:
        if any(k in t for k in keys):
            return name
    return "Macro"


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": "horloge-trading/1.0 (usage personnel)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    try:
        raw = fetch()
    except Exception as e:  # le flux peut être temporairement indisponible : on ne casse rien
        print(f"Flux indisponible : {e}", file=sys.stderr)
        return 0

    now = datetime.now(timezone.utc)
    fresh = {}
    for ev in raw:
        if ev.get("country") != "USD" or ev.get("impact") != "High":
            continue
        try:
            d = datetime.fromisoformat(ev["date"]).astimezone(timezone.utc)
        except (KeyError, ValueError):
            continue
        t = d.strftime("%Y-%m-%dT%H:%M:%SZ")
        title = ev.get("title", "").strip()
        fresh[(t, title)] = {"t": t, "n": title, "k": category(title)}

    old = []
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            old = json.load(f).get("events", [])

    merged = {(e["t"], e["n"]): e for e in old}
    # la semaine fraîchement lue fait foi : on retire les anciens événements de sa période puis on ajoute
    if raw:
        dates = [datetime.fromisoformat(e["date"]).astimezone(timezone.utc) for e in raw if e.get("date")]
        lo, hi = min(dates), max(dates)
        merged = {k: v for k, v in merged.items()
                  if not (lo <= datetime.fromisoformat(v["t"].replace("Z", "+00:00")) <= hi)}
    merged.update(fresh)

    events = sorted(
        (e for e in merged.values()
         if datetime.fromisoformat(e["t"].replace("Z", "+00:00")) >= now - KEEP_PAST),
        key=lambda e: (e["t"], e["n"]),
    )
    out = {"updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "Forex Factory (impact High, USD)", "events": events}

    old_events = old
    if old_events == events:
        print("Aucun changement.")
        return 0
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"{len(events)} événements écrits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
