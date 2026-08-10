#!/usr/bin/env python3
"""
fetch_sprites.py - download 96x96 Pokemon sprites (PokeAPI sprites repo on
GitHub) for every species in data/wikidata.json, keyed by national dex number,
into sprites/<dex>.png. Idempotent: existing files are skipped, so re-runs
only fetch what's missing. Species without official art (pack customs) 404
and are simply skipped - the wiki hides missing images.

    python fetch_sprites.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "sprites")
BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/"
VARIANTS = {          # subfolder -> url prefix
    "": BASE,         # normal:  sprites/<dex>.png
    "shiny": BASE + "shiny/",   # shiny: sprites/shiny/<dex>.png
}


def fetch(job: tuple[str, int]) -> tuple[str, int, str]:
    variant, dex = job
    path = os.path.join(OUT, variant, f"{dex}.png")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return variant, dex, "cached"
    req = urllib.request.Request(f"{VARIANTS[variant]}{dex}.png",
                                 headers={"User-Agent": "cobbleverse-wiki"})
    try:
        data = urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:
        return variant, dex, f"miss ({type(e).__name__})"
    if data[:4] != b"\x89PNG":
        return variant, dex, "miss (not png)"
    with open(path, "wb") as fh:
        fh.write(data)
    return variant, dex, "ok"


def main() -> None:
    with open(os.path.join(ROOT, "data", "wikidata.json"), encoding="utf-8") as fh:
        species = json.load(fh)["species"]
    dexes = sorted({s["dex"] for s in species.values()
                    if isinstance(s.get("dex"), int) and 1 <= s["dex"] <= 1030})
    jobs = [(variant, d) for variant in VARIANTS for d in dexes]
    for variant in VARIANTS:
        os.makedirs(os.path.join(OUT, variant), exist_ok=True)
    print(f"fetching {len(jobs)} sprites (normal + shiny) -> {OUT}")
    ok = cached = miss = 0
    with ThreadPoolExecutor(max_workers=16) as pool:
        futs = [pool.submit(fetch, j) for j in jobs]
        for i, fut in enumerate(as_completed(futs), 1):
            variant, dex, status = fut.result()
            if status == "ok":
                ok += 1
            elif status == "cached":
                cached += 1
            else:
                miss += 1
                print(f"  {variant or 'normal'}/#{dex}: {status}")
            if i % 400 == 0:
                print(f"  ... {i}/{len(jobs)}")
    total_mb = sum(os.path.getsize(os.path.join(dp, f))
                   for dp, _, fs in os.walk(OUT) for f in fs) / 1_000_000
    print(f"done: {ok} fetched, {cached} cached, {miss} missing "
          f"({total_mb:.1f} MB total)")
    if miss and not ok and not cached:
        sys.exit("nothing fetched - is the network available?")


if __name__ == "__main__":
    main()
