#!/usr/bin/env python3
"""
build_site.py - render the Cobbleverse wiki pages from data/wikidata.json
plus the curated guide content in content/*.json.

    python build_site.py

Outputs *.html into the wiki folder (parent of tools/). Safe to re-run.
"""

from __future__ import annotations

import json
import os

from templates import TYPE_COLORS, NAV_ITEMS, slugify
from pages_apps import (build_pokedex, build_items, build_trainers,
                        build_spawnfinder)
from pages_articles import (build_guide, build_progression, build_legendaries,
                            build_mods, build_home, build_videos,
                            build_structures)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def pretty(ident: str) -> str:
    return str(ident or "").split(":")[-1].split("/")[-1].replace("_", " ").title()


# ---------------------------------------------------------------- summaries

def _norm(item_id: str) -> str:
    if not item_id:
        return ""
    return item_id if ":" in item_id else f"minecraft:{item_id}"


def make_name_of(names: dict):
    def name_of(ident: str) -> str:
        return names.get(ident) or pretty(ident)
    return name_of


def evo_desc(e: dict, name_of) -> str:
    bits = []
    v = e.get("variant") or ""
    if v == "trade":
        bits.append("trade")
    if v == "item_interact":
        item = e.get("item")
        if isinstance(item, str):
            bits.append(f"use {name_of(_norm(item))}")
        elif isinstance(item, dict) and item.get("item"):
            bits.append(f"use {name_of(_norm(item['item']))}")
        else:
            bits.append("use item")
    if v == "block_click":
        bits.append("interact with block")
    for r in e.get("req", []) or []:
        if not isinstance(r, dict):
            continue
        var = r.get("variant") or ""
        if var == "level":
            lo = r.get("minLevel")
            bits.append(f"level {lo}+" if lo is not None else "level up")
        elif var == "friendship":
            bits.append(f"friendship {r.get('amount', '?')}+")
        elif var == "held_item":
            ic = r.get("itemCondition")
            if isinstance(ic, dict):
                ic = ic.get("item")
            if isinstance(ic, str):
                bits.append(f"holding {name_of(_norm(ic.lstrip('#')))}")
            else:
                bits.append("holding item")
        elif var == "time_range":
            bits.append(f"during {r.get('range', '?')}")
        elif var == "biome":
            b = r.get("biomeCondition")
            bits.append(f"in {pretty(str(b).lstrip('#'))}" if b else "specific biome")
        elif var == "has_move":
            bits.append(f"knows {r.get('move', '?')}")
        elif var == "has_move_type":
            bits.append(f"knows a {r.get('type', '?')} move")
        elif var == "party_member":
            bits.append(f"{pretty(str(r.get('target', '?')))} in party")
        elif var == "properties":
            bits.append(str(r.get("target", "")).replace("_", " "))
        elif var == "moon_phase":
            bits.append(f"moon phase {r.get('moonPhase', '?')}")
        elif var == "blocks_traveled":
            bits.append(f"travel {r.get('amount', '?')} blocks")
        elif var == "recoil":
            bits.append(f"take {r.get('amount', '?')} recoil")
        elif var == "damage_taken":
            bits.append(f"take {r.get('amount', '?')} damage")
        elif var == "use_move":
            bits.append(f"use {r.get('move', '?')} {r.get('amount', '?')}×")
        elif var == "defeat":
            bits.append(f"defeat {pretty(str(r.get('target', '?')))}")
        elif var == "attack_defence_ratio":
            bits.append(f"atk/def {r.get('ratio', '?')}")
        elif var == "battle_critical_hits":
            bits.append(f"{r.get('amount', '?')} crits in one battle")
        elif var == "structure":
            bits.append("near structure")
        elif var == "weather":
            bits.append(str(r.get("isRaining") and "raining" or "weather"))
        elif var:
            bits.append(var.replace("_", " "))
    if not bits:
        bits.append(v.replace("_", " ") if v else "level up")
    out = ", ".join(bits)
    if e.get("added"):
        out += f" [{e['added']}]"
    return out


_COND_LABELS = [
    ("timeRange", lambda v: f"time {v}"),
    ("canSeeSky", lambda v: "open sky" if v else "under cover"),
    ("isRaining", lambda v: "raining" if v else "not raining"),
    ("isThundering", lambda v: "thundering" if v else None),
    ("moonPhase", lambda v: f"moon {v}"),
    ("minLureLevel", lambda v: f"lure {v}+"),
    ("bait", lambda v: f"bait {pretty(str(v))}"),
    ("fluidIsSource", lambda v: None),
    ("dimensions", lambda v: "dim " + ", ".join(pretty(x) for x in v)),
    ("structures", lambda v: "in " + ", ".join(pretty(str(x).lstrip('#')) for x in v)),
    ("neededNearbyBlocks", lambda v: "near " + ", ".join(pretty(str(x).lstrip('#')) for x in v[:4])),
    ("neededBaseBlocks", lambda v: "on " + ", ".join(pretty(str(x).lstrip('#')) for x in v[:4])),
    ("labels", lambda v: None),
]


def cond_summary(c: dict) -> str:
    if not isinstance(c, dict):
        return ""
    bits = []
    def rng(lo_k, hi_k, label):
        lo, hi = c.get(lo_k), c.get(hi_k)
        if lo is None and hi is None:
            return
        if lo is not None and hi is not None:
            bits.append(f"{label} {lo}-{hi}")
        elif lo is not None:
            bits.append(f"{label} ≥{lo}")
        else:
            bits.append(f"{label} ≤{hi}")
    rng("minSkyLight", "maxSkyLight", "skylight")
    rng("minLight", "maxLight", "light")
    rng("minY", "maxY", "Y")
    handled = {"minSkyLight", "maxSkyLight", "minLight", "maxLight", "minY",
               "maxY", "biomes"}
    for key, fmt in _COND_LABELS:
        handled.add(key)
        if key in c:
            try:
                lab = fmt(c[key])
            except Exception:
                lab = None
            if lab:
                bits.append(lab)
    for key, val in c.items():
        if key not in handled and not isinstance(val, (dict, list)):
            bits.append(f"{key}={val}")
    return " · ".join(bits)


def wmult_summary(w) -> str:
    if not isinstance(w, dict):
        return ""
    mult = w.get("multiplier")
    cond = cond_summary(w.get("condition") or {})
    if not cond:
        biomes = (w.get("condition") or {}).get("biomes")
        if biomes:
            cond = "in " + ", ".join(pretty(str(b).lstrip("#")) for b in biomes[:3])
    return f"weight ×{mult:g} when {cond}" if mult and cond else (f"weight ×{mult:g}" if mult else "")


def preset_summary(p: dict) -> str:
    if not isinstance(p, dict):
        return ""
    return cond_summary(p.get("condition") or {})


# ---------------------------------------------------------------- payloads

def build_payloads(d: dict, trainers_guide: dict | None = None):
    names = d["names"]
    name_of = make_name_of(names)
    species = d["species"]
    species_names = {sid: s["name"] for sid, s in species.items()}
    species_dex = {sid: s["dex"] for sid, s in species.items()
                   if isinstance(s.get("dex"), int)}

    # --- pokedex ------------------------------------------------
    spawns_by: dict[str, list] = {}
    used_biome_tags: set[str] = set()
    for sp in d["spawns"]:
        cond = sp.get("cond") or {}
        anti = sp.get("anti") or {}
        biomes = cond.get("biomes") or []
        anti_biomes = anti.get("biomes") or []
        for b in biomes + anti_biomes:
            if isinstance(b, str) and b.startswith("#"):
                used_biome_tags.add(b.lstrip("#"))
        entry = {
            "bucket": sp.get("bucket"),
            "level": sp.get("level"),
            "weight": sp.get("weight"),
            "ctx": sp.get("ctx"),
            "aspects": sp.get("aspects") or "",
            "herd": bool(sp.get("herd")),
            "presets": sp.get("presets") or [],
            "biomes": biomes,
            "anti": anti_biomes,
            "cond": cond_summary(cond),
            "wmult": wmult_summary(sp.get("wmult")),
            "src": sp.get("src"),
            "addon": bool(sp.get("addon")),
        }
        # structured condition fields for the spawn-trap build checklist.
        # Presets (e.g. 'natural') supply conditions too - entry-level
        # values win, preset values fill the gaps.
        merged = {}
        for p in sp.get("presets") or []:
            pc = (d.get("presets", {}).get(p) or {}).get("condition") or {}
            merged.update(pc)
        merged.update(cond)
        for src_k, out_k in (("neededBaseBlocks", "base"),
                             ("neededNearbyBlocks", "near")):
            v = merged.get(src_k)
            if v:
                entry[out_k] = v
        for k in ("minSkyLight", "maxSkyLight", "canSeeSky", "timeRange",
                  "isRaining", "isThundering", "minY", "maxY"):
            if k in merged:
                entry[k] = merged[k]
        spawns_by.setdefault(sp["pokemon"], []).append(entry)

    evo_from: dict[str, list] = {}
    pd_species = {}
    ref_items: set[str] = set()
    for sid, s in species.items():
        evos = []
        for e in s.get("evolutions", []):
            desc = evo_desc(e, name_of)
            to = e.get("to") or ""
            evos.append({"to": to, "desc": desc})
            if to:
                evo_from.setdefault(to, []).append({"from": sid, "desc": desc})
        for dr in s.get("drops", []):
            ref_items.add(dr["item"])
        pd_species[sid] = {
            "name": s["name"], "dex": s.get("dex"), "types": s.get("types", []),
            "stats": s.get("stats", {}), "catchRate": s.get("catchRate"),
            "maleRatio": s.get("maleRatio"), "eggGroups": s.get("eggGroups", []),
            "abilities": s.get("abilities", []), "labels": s.get("labels", []),
            "implemented": s.get("implemented", True),
            "dropAmount": s.get("dropAmount"),
            "drops": s.get("drops", []), "evolutions": evos,
            "src": s.get("src"), "addon": s.get("addon", False),
            "modifiedBy": s.get("modifiedBy"),
        }

    fossils = []
    for f in d.get("fossils", []):
        raw = f.get("raw") or {}
        result = str(raw.get("result") or "").split(" ")[0].lower()
        items = [x for x in (raw.get("fossils") or []) if isinstance(x, str)]
        ref_items.update(items)
        fossils.append({"result": result,
                        "resultName": species_names.get(result, pretty(result)),
                        "items": items})

    presets = {k: preset_summary(v) for k, v in d.get("presets", {}).items()}
    biome_tags = {t: d["biomeTags"].get(t, []) for t in used_biome_tags}

    pokedex_payload = {
        "species": pd_species,
        "spawnsBy": spawns_by,
        "evoFrom": evo_from,
        "biomeTags": biome_tags,
        "presets": presets,
        "fossils": fossils,
        "names": {i: name_of(i) for i in ref_items},
        "typeColors": TYPE_COLORS,
    }

    used_block_tags: set[str] = set()
    for entries in spawns_by.values():
        for e in entries:
            for k in ("base", "near"):
                for b in e.get(k, []) or []:
                    if isinstance(b, str) and b.startswith("#"):
                        used_block_tags.add(b.lstrip("#"))
    spawnfinder_payload = {
        "species": {sid: {"name": s["name"], "dex": s.get("dex"),
                          "labels": s.get("labels", [])}
                    for sid, s in species.items()},
        "spawnsBy": spawns_by,
        "biomeTags": biome_tags,
        "blockTags": {t: d.get("blockTags", {}).get(t, [])
                      for t in used_block_tags},
        "presets": presets,
    }

    # --- items --------------------------------------------------
    item_tags = d["itemTags"]
    recipes = []
    referenced: set[str] = set(names.keys())
    for r in d["recipes"]:
        ins = []
        for raw_i in r["i"]:
            if raw_i.startswith("#"):
                tag = raw_i.lstrip("#")
                members = item_tags.get(tag, [])
                referenced.update(members)
                ins.append({"tag": tag, "n": len(members), "m": members[:12]})
            else:
                referenced.add(raw_i)
                ins.append({"id": raw_i})
        referenced.add(r["o"])
        rec = {"o": r["o"], "c": r["c"], "t": r["t"], "i": ins,
               "src": r["src"], "addon": r.get("addon", False)}
        if r.get("label"):
            rec["label"] = r["label"]
        recipes.append(rec)

    loot = []
    for e in d["loot"]:
        row = {"i": e["i"], "t": e["t"], "p": e["p"], "r": e["r"],
               "n": e["n"], "e": e["e"], "src": e["src"],
               "addon": e.get("addon", False)}
        if e.get("ref"):
            row["ref"] = True   # nested loot-table reference, not an item
        else:
            referenced.add(e["i"])
        loot.append(row)

    mon_drops: dict[str, list] = {}
    for sid, s in species.items():
        for dr in s.get("drops", []):
            referenced.add(dr["item"])
            mon_drops.setdefault(dr["item"], []).append({
                "sp": sid, "name": s["name"],
                "pct": dr.get("pct"), "range": dr.get("range")})

    evo_items: dict[str, list] = {}
    for sid, s in species.items():
        for e in s.get("evolutions", []):
            cands = []
            item = e.get("item")
            if isinstance(item, str):
                cands.append(_norm(item))
            elif isinstance(item, dict) and item.get("item"):
                cands.append(_norm(item["item"]))
            for r in e.get("req", []) or []:
                if isinstance(r, dict) and r.get("variant") == "held_item":
                    ic = r.get("itemCondition")
                    if isinstance(ic, dict):
                        ic = ic.get("item")
                    if isinstance(ic, str) and not ic.startswith("#"):
                        cands.append(_norm(ic))
            for c in cands:
                referenced.add(c)
                lst = evo_items.setdefault(c, [])
                if sid not in lst:
                    lst.append(sid)

    sig_items: dict[str, dict] = {}
    for mid, mob in d.get("mobs", {}).items():
        sig = mob.get("signatureItem")
        if sig and mid in d.get("trainers", {}):
            referenced.add(sig)
            sig_items.setdefault(sig, {"id": mid,
                                       "name": d["trainers"][mid]["name"]})

    items_payload = {
        "names": {i: name_of(i) for i in referenced},
        "tips": {i: t for i, t in d["tooltips"].items() if i in referenced},
        "recipes": recipes,
        "loot": loot,
        "monDrops": mon_drops,
        "evoItems": evo_items,
        "sigItems": sig_items,
        "fossils": fossils,
        "speciesNames": species_names,
        "speciesDex": species_dex,
    }

    # --- trainers -----------------------------------------------
    tr_ref: set[str] = set()
    for t in d["trainers"].values():
        for b in t.get("bag", []):
            if b.get("item"):
                tr_ref.add(b["item"])
    for mob in d.get("mobs", {}).values():
        if mob.get("signatureItem"):
            tr_ref.add(mob["signatureItem"])
    for s in (trainers_guide or {}).get("series", []):
        for g in s.get("gyms", []):
            for key in ("badge", "signatureItem"):
                if g.get(key):
                    tr_ref.add(g[key])
    lang = d.get("lang", {})
    series = {}
    for sid, s in d.get("series", {}).items():
        s = dict(s)
        for key in ("title", "desc"):
            val = s.get(key) or ""
            if "." in val and val in lang:      # unresolved translate key
                s[key] = lang[val]
        if "." in (s.get("title") or ""):
            s["title"] = pretty(sid)
        series[sid] = s
    trainers_payload = {
        "trainers": d["trainers"],
        "mobs": d.get("mobs", {}),
        "series": series,
        "names": {i: name_of(i) for i in tr_ref},
        "speciesNames": species_names,
        "speciesDex": species_dex,
    }

    return pokedex_payload, items_payload, trainers_payload, spawnfinder_payload


# ---------------------------------------------------------------- seasonings

_STAT = {"hp": "HP", "atk": "Attack", "def": "Defence", "spa": "Sp. Attack",
         "spd": "Sp. Defence", "spe": "Speed"}


def _stat(sub):
    return _STAT.get(str(sub).split(":")[-1], str(sub).split(":")[-1])


def _pct(x):
    v = float(x) * 100
    return f"{v:.0f}%" if v == int(v) else f"{v:.1f}%"


def _bait_phrase(e):
    t = e.get("type", "").split(":")[-1]
    ch, val, sub = e.get("chance", 1), e.get("value", 0), e.get("subcategory")
    if t == "nature":
        return f"{_pct(ch)} chance to bias natures toward {_stat(sub)}"
    if t == "iv":
        return f"+{val:g} {_stat(sub)} IVs ({_pct(ch)})"
    if t == "ev":
        return f"lures Pokémon that yield {_stat(sub)} EVs"
    if t == "egg_group":
        return f"lures the {str(sub).replace('_', ' ')} egg group (+{val:g} weight)"
    if t == "typing":
        return f"lures {str(sub).split(':')[-1]}-type Pokémon (+{val:g} weight)"
    if t == "pokemon_chance":
        return f"{_pct(ch)} chance of {str(sub).split(':')[-1].replace('_', ' ').title()}"
    if t == "bite_time":
        return f"shortens fishing bite time ({val:g})"
    if t == "ha_chance":
        return f"{_pct(ch)} chance of a hidden ability"
    if t == "level_raise":
        return f"raises spawn level by {val:g}"
    if t == "friendship":
        return f"+{val:g} starting friendship"
    if t == "gender_chance":
        return f"{_pct(ch)} chance of {str(sub).split(':')[-1]} gender"
    if t == "drops_reroll":
        return "rerolls the Pokémon's drops"
    if t == "shiny_reroll":
        return f"extra shiny roll ×{val:g}" if val else "extra shiny roll"
    if t == "rarity_bucket":
        return "shifts spawns one rarity bucket up (toward ultra-rare)"
    return f"{t} {val:g} {sub or ''}".strip()


def seasoning_sections(d, name_of):
    from templates import icon_img, esc
    rows = []
    for b in sorted(d.get("baits", []), key=lambda b: name_of(b.get("item", ""))):
        item = b.get("item")
        if not item:
            continue
        effects = "; ".join(_bait_phrase(e) for e in b.get("effects", []))
        rows.append(
            f"<tr><td>{icon_img(item, 20)} "
            f"<a href='items.html#{esc(item)}'>{esc(name_of(item))}</a></td>"
            f"<td>{esc(effects)}</td></tr>")
    bait_body = (
        "<p>Season a <a href='items.html#cobblemon:poke_snack'>Poké Snack"
        "</a> with these ingredients to steer what spawns near it — every "
        "value below is read from the pack's own "
        "<code>spawn_bait_effects</code> data. Combine with a spawn "
        "platform (see Spawn trapping above) for best results.</p>"
        "<table class='data'><tr><th>Ingredient</th><th>Bait effect</th></tr>"
        + "".join(rows) + "</table>")

    srows = []
    for s in sorted(d.get("seasonings", []),
                    key=lambda s: name_of(s.get("ingredient", ""))):
        item = s.get("ingredient")
        fx = s.get("mobEffects") or []
        if not item or not fx:
            continue
        parts = []
        for e in fx:
            nm = str(e.get("effect", "")).split(":")[-1].replace("_", " ").title()
            dur = int(e.get("duration", 0)) // 20
            amp = int(e.get("amplifier", 0))
            parts.append(f"{nm}{' ' + 'I' * (amp + 1) if amp else ''} "
                         f"({dur}s)")
        srows.append(
            f"<tr><td>{icon_img(item, 20)} "
            f"<a href='items.html#{esc(item)}'>{esc(name_of(item))}</a></td>"
            f"<td>{esc('; '.join(parts))}</td></tr>")
    food_body = (
        "<p>These ingredients grant potion effects when cooked into snacks "
        "and eaten (from the pack's <code>seasonings</code> data; "
        "ingredients that only change the snack's colour are omitted).</p>"
        "<table class='data'><tr><th>Ingredient</th><th>Effect when eaten"
        "</th></tr>" + "".join(srows) + "</table>")

    return [{"heading": "Poké Snack bait ingredients", "body": bait_body},
            {"heading": "Seasoning food effects", "body": food_body}]


# ---------------------------------------------------------------- main

def main() -> None:
    d = load_json(os.path.join(ROOT, "data", "wikidata.json"))
    if d is None:
        raise SystemExit("data/wikidata.json missing - run extract.py first")

    content_dir = os.path.join(ROOT, "content")
    content = {}
    for key in ("progression", "legendaries", "trainers_guide", "mods",
                "mechanics", "regions", "items_notable", "videos", "tips",
                "locations"):
        content[key] = load_json(os.path.join(content_dir, f"{key}.json"))

    # data-exact seasoning tables regenerate into Mechanics every build
    if content.get("mechanics"):
        gen_headings = {"Poké Snack bait ingredients",
                        "Seasoning food effects"}
        content["mechanics"] = dict(content["mechanics"])
        secs = [s for s in content["mechanics"].get("sections", [])
                if s.get("heading") not in gen_headings]
        secs.extend(seasoning_sections(d, make_name_of(d["names"])))
        content["mechanics"]["sections"] = secs

    counts = {
        "species": len(d["species"]),
        "spawns": len(d["spawns"]),
        "recipes": len(d["recipes"]),
        "loot": len(d["loot"]),
        "trainers": len(d["trainers"]),
        "names": len(d["names"]),
        "mods": sum(1 for o in d.get("origins", [])
                    if o["file"].endswith(".jar")),
    }

    (pokedex_payload, items_payload, trainers_payload,
     spawnfinder_payload) = build_payloads(d, content["trainers_guide"])

    pages = {
        "index.html": build_home(counts, content),
        "progression.html": build_progression(content["progression"], d["names"]),
        "pokedex.html": build_pokedex(pokedex_payload, counts),
        "spawns.html": build_spawnfinder(spawnfinder_payload, counts),
        "items.html": build_items(items_payload, counts),
        "trainers.html": build_trainers(trainers_payload, counts,
                                        content["trainers_guide"]),
        "legendaries.html": build_legendaries(content["legendaries"], d["species"]),
        "mechanics.html": build_guide("mechanics.html", "Mechanics",
                                      content["mechanics"],
                                      "The pack's gameplay systems, from its configs"),
        "world.html": build_guide("world.html", "World & Regions",
                                  content["regions"],
                                  "World generation, structures and add-on packs"),
        "key-items.html": build_guide("key-items.html", "Key Items",
                                      content["items_notable"],
                                      "The items that matter in this pack"),
        "mods.html": build_mods(content["mods"]),
        "videos.html": build_videos(content["videos"]),
        "tips.html": build_guide("tips.html", "Tips & Tricks", content["tips"],
                                 "Distilled from the community's best guide "
                                 "videos, checked against the pack data"),
    }

    if d.get("shops", {}).get("merchants"):
        from pages_shops import build_shops
        pages["shops.html"] = build_shops(d["shops"], make_name_of(d["names"]))
    from pages_teambuilder import build_teambuilder
    pages["teambuilder.html"] = build_teambuilder(d["species"], d["mobs"],
                                                  d["trainers"])
    loc_content = content.get("locations")
    if loc_content:
        from pages_locations import build_locations
        pages["locations.html"] = build_locations(loc_content, d)

    struct_inv = load_json(os.path.join(ROOT, "data", "structures.json")) or []
    struct_dir = os.path.join(ROOT, "renders", "structures")
    have = ({f[:-4] for f in os.listdir(struct_dir) if f.endswith(".png")}
            if os.path.isdir(struct_dir) else set())
    if struct_inv and have:
        pages["structures.html"] = build_structures(struct_inv, have,
                                                    d["species"],
                                                    content["legendaries"])
        from viewer_page import build_viewer
        pages["viewer.html"] = build_viewer()

    # ---- global search index (shared by every page's nav search bar)
    idx = []
    for sid, s in d["species"].items():
        idx.append({"t": s["name"], "k": "pokemon", "i": sid,
                    "x": s.get("dex")})
    for iid, nm in d["names"].items():
        idx.append({"t": nm, "k": "item", "i": iid})
    for tid, t in d["trainers"].items():
        idx.append({"t": t["name"], "k": "trainer", "i": tid})
    for href, label in NAV_ITEMS:
        idx.append({"t": label, "k": "page", "i": href})
    guide_pages = [("mechanics", "mechanics.html"), ("regions", "world.html"),
                   ("items_notable", "key-items.html"), ("tips", "tips.html"),
                   ("legendaries", "legendaries.html"),
                   ("videos", "videos.html")]
    for key, href in guide_pages:
        c = content.get(key) or {}
        for s in c.get("sections", []) or []:
            h = s.get("heading")
            if h:
                idx.append({"t": h, "k": "guide",
                            "i": f"{href}#{slugify(h)}"})
        for leg in c.get("legendaries", []) or []:
            if leg.get("name"):
                idx.append({"t": leg["name"], "k": "guide",
                            "i": f"legendaries.html#{slugify(leg['name'])}"})
    for e in (load_json(os.path.join(ROOT, "data", "structures.json")) or []):
        nm = e["rel"].split("/")[-1].replace("_", " ").title()
        idx.append({"t": nm + " (structure)", "k": "guide",
                    "i": "structures.html"})
    for m in d.get("shops", {}).get("merchants", []):
        idx.append({"t": m["name"] + " (shop)", "k": "guide",
                    "i": f"shops.html#{slugify(m['name'])}"})
    for loc in (content.get("locations") or {}).get("locations", []) or []:
        idx.append({"t": loc["name"] + " (dungeon)", "k": "guide",
                    "i": f"locations.html#{loc['slug']}"})
    with open(os.path.join(ROOT, "searchindex.js"), "w",
              encoding="utf-8") as fh:
        fh.write("const SEARCH_INDEX=" +
                 json.dumps(idx, separators=(",", ":"), ensure_ascii=False)
                 .replace("</", "<\\/") + ";")
    print(f"  {os.path.getsize(os.path.join(ROOT, 'searchindex.js')) / 1_000_000:5.1f} MB  searchindex.js ({len(idx):,} entries)")

    # ---- hover preview data (shared card tooltips on every page)
    species_dex = {sid: s.get("dex") for sid, s in d["species"].items()}
    lang = d.get("lang", {})
    ser_titles = {}
    for sid_, s_ in d.get("series", {}).items():
        t_ = s_.get("title") or sid_
        if "." in t_:
            t_ = lang.get(t_, pretty(sid_))
        ser_titles[sid_] = t_
    hover = {"p": {}, "i": {}, "t": {}}
    for sid, s in d["species"].items():
        hover["p"][sid] = {
            "n": s["name"], "d": s.get("dex"), "ty": s.get("types", []),
            "b": sum((s.get("stats") or {}).values()), "c": s.get("catchRate")}
    for iid, nm in d["names"].items():
        e = {"n": nm}
        tip = d["tooltips"].get(iid)
        if tip and len(tip) <= 220:
            e["tip"] = tip
        hover["i"][iid] = e
    for tid, t in d["trainers"].items():
        team = t.get("team", [])
        lvls = [m.get("level") for m in team if m.get("level")]
        e = {"n": t["name"], "c": len(team)}
        if lvls:
            e["lo"], e["hi"] = min(lvls), max(lvls)
        if team and team[0].get("species"):
            lead = str(team[0]["species"]).lower()
            e["ld"] = lead
            if species_dex.get(lead):
                e["ldx"] = species_dex[lead]
        mob = d.get("mobs", {}).get(tid) or {}
        ser = (mob.get("series") or [None])[0]
        if ser:
            e["s"] = ser_titles.get(ser, ser)
        hover["t"][tid] = e
    with open(os.path.join(ROOT, "hoverdata.js"), "w", encoding="utf-8") as fh:
        fh.write("const HOVER_DATA=" +
                 json.dumps(hover, separators=(",", ":"), ensure_ascii=False)
                 .replace("</", "<\\/") + ";")
    print(f"  {os.path.getsize(os.path.join(ROOT, 'hoverdata.js')) / 1_000_000:5.1f} MB  hoverdata.js")

    for fname, html in pages.items():
        path = os.path.join(ROOT, fname)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        print(f"  {os.path.getsize(path) / 1_000_000:5.1f} MB  {fname}")
    print("done.")


if __name__ == "__main__":
    main()
