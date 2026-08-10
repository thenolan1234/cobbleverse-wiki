#!/usr/bin/env python3
"""
extract.py - read the COBBLEVERSE modpack's own data files into one JSON blob.

Extended from the cobbleindex tooling (indexer.py): keeps its recipe / loot /
tag / lang parsing and adds Cobblemon-specific domains:

  - species            (stats, types, catch rate, drops, evolutions)
  - species_additions  (pack overrides, merged onto species)
  - spawn_pool_world   (biome / bucket / level / weight spawn data)
  - biome + item tags  (recursively resolvable)
  - spawn presets      (structure-linked spawn conditions)
  - fossils
  - rctmod trainers    (teams, spawn biomes, series)
  - advancements       (cobbleverse / lumymon / mega_showdown progression)

Reads jars and datapack zips only. Never writes into the pack folder.

    python extract.py                      # uses default pack location
    python extract.py --pack "<profile>"   # explicit
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from collections import defaultdict

DEFAULT_PACK = r"C:\Users\nolan\AppData\Roaming\ModrinthApp\profiles\COBBLEVERSE - Pokemon Adventure [Cobblemon]"

# ---------------------------------------------------------------- helpers

def _clean(s: str) -> str:
    s = re.sub(r"\u00a7.", "", s or "").strip()
    # some pack lang files were saved with a mangled \u00e9
    return (s.replace("Pok\ufffdmon", "Pok\u00e9mon")
             .replace("Pok\ufffddex", "Pok\u00e9dex")
             .replace("Pok\ufffd", "Pok\u00e9"))


def _norm(item_id: str) -> str:
    if not item_id:
        return ""
    return item_id if ":" in item_id else f"minecraft:{item_id}"


_LANG_RE = re.compile(r"assets/([^/]+)/lang/en_us\.json$")
_RECIPE_RE = re.compile(r"data/([^/]+)/recipes?/(.+)\.json$")
_LOOT_RE = re.compile(r"data/([^/]+)/loot_tables?/(.+)\.json$")
_ITEMTAG_RE = re.compile(r"data/([^/]+)/tags/items?/(.+)\.json$")
_BLOCKTAG_RE = re.compile(r"data/([^/]+)/tags/blocks?/(.+)\.json$")
_BIOMETAG_RE = re.compile(r"data/([^/]+)/tags/worldgen/biome/(.+)\.json$")
_SPECIES_RE = re.compile(r"data/([^/]+)/species/(.+)\.json$")
_SPECIES_ADD_RE = re.compile(r"data/([^/]+)/species_additions/(.+)\.json$")
_SPAWN_RE = re.compile(r"data/([^/]+)/spawn_pool_world/(.+)\.json$")
_PRESET_RE = re.compile(r"data/([^/]+)/spawn_detail_presets/(.+)\.json$")
_SEASONING_RE = re.compile(r"data/([^/]+)/seasonings/(.+)\.json$")
_BAIT_RE = re.compile(r"data/([^/]+)/spawn_bait_effects/(.+)\.json$")
_FOSSIL_RE = re.compile(r"data/([^/]+)/fossils/(.+)\.json$")
_TRAINER_RE = re.compile(r"data/rctmod/trainers/([^/]+)\.json$")
_MOB_RE = re.compile(r"data/rctmod/mobs/(.+)\.json$")
_SERIES_RE = re.compile(r"data/rctmod/series/([^/]+)\.json$")
_ADV_RE = re.compile(
    r"data/(cobbleverse|lumymon|mega_showdown|legendarymonuments)/advancements?/(.+)\.json$")

# lang key prefixes worth keeping (everything else is dropped to save space)
_LANG_KEEP = ("item.", "block.", "tooltip.", "advancements.", "entity.rctmod",
              "type.rctmod", "series.rctmod", "container.", "text.cobbleverse")


class Store:
    """Minecraft override semantics: a datapack file at the same data/ path
    replaces a mod jar's file. We scan jars first, then datapacks, so for
    path-keyed domains a later non-addon source replaces an earlier one.
    Add-on packs (datapacks/extra, not active by default) never replace the
    base data - their content is kept separately and flagged `addon`.
    Tags are the exception: vanilla MERGES tag files across packs."""

    def __init__(self) -> None:
        self.names: dict[str, str] = {}
        self.tooltips: dict[str, str] = {}
        self.lang: dict[str, str] = {}
        self.item_tags: dict[str, list] = defaultdict(list)
        self.block_tags: dict[str, list] = defaultdict(list)
        self.biome_tags: dict[str, list] = defaultdict(list)
        self.recipes_by_path: dict[str, dict] = {}
        self.addon_recipes: list[dict] = []
        self.loot_by_path: dict[str, list] = {}
        self.addon_loot: list[dict] = []
        self.spawns_by_path: dict[str, list] = {}
        self.addon_spawns: list[dict] = []
        self.species_by_path: dict[str, dict] = {}
        self.species: dict[str, dict] = {}          # filled in finalize()
        self.species_adds: list[dict] = []
        self.presets: dict[str, dict] = {}
        self.seasonings: dict[str, dict] = {}
        self.baits: dict[str, dict] = {}
        self.fossils: list[dict] = []
        self.trainers: dict[str, dict] = {}
        self.mobs: dict[str, dict] = {}
        self.series: dict[str, dict] = {}
        self.advancements: dict[str, dict] = {}
        self.origins: list[dict] = []

    def finalize(self) -> None:
        """Collapse path-keyed species to id-keyed. Base first, then add-ons
        only where the species id is new."""
        for sp in self.species_by_path.values():
            if not sp.get("addon"):
                self.species[sp["id"]] = sp
        for sp in self.species_by_path.values():
            if sp.get("addon") and sp["id"] not in self.species:
                self.species[sp["id"]] = sp

    @property
    def all_recipes(self) -> list[dict]:
        return list(self.recipes_by_path.values()) + self.addon_recipes

    @property
    def all_loot(self) -> list[dict]:
        return [e for lst in self.loot_by_path.values() for e in lst] + self.addon_loot

    @property
    def all_spawns(self) -> list[dict]:
        return [e for lst in self.spawns_by_path.values() for e in lst] + self.addon_spawns


# ---------------------------------------------------------------- vanilla-ish parsing
# (recipe / loot / ingredient flattening adapted from cobbleindex's indexer.py)

def _ingredient_ids(node) -> list[str]:
    out: list[str] = []
    if node is None:
        return out
    if isinstance(node, str):
        return [("#" + node[1:]) if node.startswith("#") else _norm(node)]
    if isinstance(node, list):
        for sub in node:
            out.extend(_ingredient_ids(sub))
        return out
    if isinstance(node, dict):
        if "item" in node:
            out.append(_norm(node["item"]))
        if "tag" in node:
            out.append("#" + node["tag"].lstrip("#"))
        for key in ("ingredient", "base", "addition", "template", "input"):
            if key in node:
                out.extend(_ingredient_ids(node[key]))
    return out


def parse_recipe(raw: dict, path: str, origin: str) -> dict | None:
    rtype = (raw.get("type") or "").split(":")[-1]
    result = raw.get("result")
    label = None
    if isinstance(result, str):
        out_id, count = _norm(result), 1
    elif isinstance(result, dict):
        out_id = _norm(result.get("id") or result.get("item") or "")
        try:
            count = int(result.get("count", 1) or 1)
        except (TypeError, ValueError):
            count = 1
        # component-renamed outputs (e.g. costume boxes on a vanilla base item)
        comp = result.get("components")
        if isinstance(comp, dict):
            nm = comp.get("minecraft:item_name") or comp.get("minecraft:custom_name")
            if isinstance(nm, dict):
                nm = nm.get("text") or nm.get("translate")
            if isinstance(nm, str):
                label = _clean(nm.strip('"'))
    else:
        return None
    if not out_id:
        return None

    inputs: list[str] = []
    if "key" in raw:
        for spec in raw["key"].values():
            inputs.extend(_ingredient_ids(spec))
    if "ingredients" in raw:
        inputs.extend(_ingredient_ids(raw["ingredients"]))
    for key in ("ingredient", "base", "addition", "template", "input"):
        if key in raw:
            inputs.extend(_ingredient_ids(raw[key]))

    rec = {"o": out_id, "c": count, "t": rtype,
           "i": sorted(set(inputs)), "src": origin, "path": path}
    if label:
        rec["label"] = label
    return rec


def _rolls_range(node) -> tuple[float, float]:
    if isinstance(node, (int, float)):
        return float(node), float(node)
    if isinstance(node, dict):
        if "min" in node or "max" in node:
            lo = float(node.get("min", node.get("max", 1)))
            hi = float(node.get("max", node.get("min", 1)))
            return lo, hi
        if "value" in node:
            return _rolls_range(node["value"])
    return 1.0, 1.0


def _count_range(functions) -> tuple[float, float]:
    for fn in functions or []:
        if (fn.get("function") or "").endswith("set_count"):
            return _rolls_range(fn.get("count"))
    return 1.0, 1.0


def parse_loot(raw: dict, origin: str, table_id: str) -> list[dict]:
    out = []
    for pool in raw.get("pools", []) or []:
        rolls = _rolls_range(pool.get("rolls", 1))
        entries = pool.get("entries", []) or []
        total_w = sum(e.get("weight", 1) for e in entries) or 1
        for entry in entries:
            etype = (entry.get("type") or "").split(":")[-1]
            if etype not in ("item", "loot_table"):
                continue
            ref = entry.get("name") or entry.get("value") or ""
            if not isinstance(ref, str) or not ref:
                continue
            item_id = _norm(ref) if etype == "item" else str(ref)
            weight = entry.get("weight", 1)
            chance = weight / total_w
            count = _count_range(entry.get("functions"))
            # a few source files ship reversed min/max - normalize for display
            rolls_n = (min(rolls), max(rolls))
            count = (min(count), max(count))
            expected = ((rolls_n[0] + rolls_n[1]) / 2) * chance * ((count[0] + count[1]) / 2)
            row = {"i": item_id, "t": table_id, "p": round(chance, 5),
                   "r": list(rolls_n), "n": list(count),
                   "e": round(expected, 5), "src": origin}
            if etype == "loot_table":
                row["ref"] = True
            out.append(row)
    return out


# ---------------------------------------------------------------- cobblemon parsing

_STAT_KEYS = ("hp", "attack", "defence", "special_attack", "special_defence", "speed")


def parse_species(raw: dict, path: str, origin: str) -> dict | None:
    name = raw.get("name")
    if not name:
        return None
    sid = name.lower().replace(" ", "").replace("-", "").replace(".", "").replace("'", "").replace(":", "").replace("\u2019", "")
    drops = raw.get("drops") or {}
    dentries = []
    for d in drops.get("entries", []) or []:
        if not isinstance(d, dict) or "item" not in d:
            continue
        dentries.append({
            "item": _norm(d["item"]),
            "pct": d.get("percentage"),
            "range": d.get("quantityRange"),
        })
    evos = []
    for ev in raw.get("evolutions", []) or []:
        if not isinstance(ev, dict):
            continue
        evos.append({
            "to": (ev.get("result") or "").split(" ")[0].lower(),
            "resultRaw": ev.get("result") or "",
            "variant": ev.get("variant"),
            "item": ev.get("requiredContext"),
            "consumeHeldItem": ev.get("consumeHeldItem"),
            "req": ev.get("requirements") or [],
        })
    return {
        "id": sid,
        "name": name,
        "dex": raw.get("nationalPokedexNumber"),
        "types": [t for t in (raw.get("primaryType"), raw.get("secondaryType")) if t],
        "stats": {k: (raw.get("baseStats") or {}).get(k, 0) for k in _STAT_KEYS},
        "catchRate": raw.get("catchRate"),
        "maleRatio": raw.get("maleRatio"),
        "expGroup": raw.get("experienceGroup"),
        "eggGroups": raw.get("eggGroups") or [],
        "abilities": raw.get("abilities") or [],
        "labels": raw.get("labels") or [],
        "implemented": raw.get("implemented", True),
        "dropAmount": drops.get("amount"),
        "drops": dentries,
        "evolutions": evos,
        "src": origin,
        "path": path,
    }


def parse_spawn_file(raw: dict, path: str, origin: str, addon: bool) -> list[dict]:
    if raw.get("enabled") is False:
        return []
    out = []
    for sp in raw.get("spawns", []) or []:
        if not isinstance(sp, dict):
            continue
        stype = sp.get("type", "pokemon")
        base = {
            "id": sp.get("id"),
            "bucket": sp.get("bucket"),
            "level": sp.get("level") or sp.get("levelRange"),
            "weight": sp.get("weight"),
            "ctx": sp.get("spawnablePositionType") or sp.get("context"),
            "presets": sp.get("presets") or [],
            "cond": sp.get("condition") or {},
            "anti": sp.get("anticondition") or {},
            "wmult": sp.get("weightMultiplier"),
            "src": origin,
            "addon": addon,
        }
        if stype == "pokemon-herd":
            members = sp.get("herdablePokemon") or []
            for m in members:
                if not isinstance(m, dict) or not m.get("pokemon"):
                    continue
                token = str(m["pokemon"]).split(" ")
                e = dict(base)
                e.update({
                    "pokemon": token[0].lower(),
                    "aspects": " ".join(token[1:]),
                    "herd": True,
                    "level": m.get("levelRange") or base["level"],
                })
                out.append(e)
        else:
            token = str(sp.get("pokemon") or "").split(" ")
            if not token[0]:
                continue
            e = dict(base)
            e.update({"pokemon": token[0].lower(), "aspects": " ".join(token[1:])})
            out.append(e)
    return out


def parse_trainer(raw: dict, tid: str, origin: str) -> dict:
    name = raw.get("name")
    if isinstance(name, dict):
        name = name.get("literal") or name.get("translatable") or tid
    team = []
    for mon in raw.get("team", []) or []:
        if not isinstance(mon, dict):
            continue
        team.append({
            "species": mon.get("species"),
            "level": mon.get("level"),
            "ability": mon.get("ability"),
            "nature": mon.get("nature"),
            "heldItem": (mon.get("heldItem") or [None])[0] if isinstance(mon.get("heldItem"), list) else mon.get("heldItem"),
            "moves": mon.get("moveset") or [],
            "shiny": mon.get("shiny"),
        })
    bag = [{"item": b.get("item"), "qty": b.get("quantity", 1)}
           for b in raw.get("bag", []) or [] if isinstance(b, dict)]
    return {"id": tid, "name": name or tid, "team": team, "bag": bag,
            "rules": raw.get("battleRules") or {}, "src": origin}


# ---------------------------------------------------------------- ingest

def _txt(node) -> str:
    """Pull a displayable string out of a minecraft text component."""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        return (node.get("translate") or node.get("translatable")
                or node.get("text") or node.get("literal") or "")
    return ""


def ingest(store: Store, origin: str, path: str, blob: bytes, addon: bool) -> None:
    try:
        raw = json.loads(blob.decode("utf-8-sig"))
    except Exception:
        return
    if not isinstance(raw, dict):
        return

    if _LANG_RE.search(path):
        for key, val in raw.items():
            if not isinstance(val, str):
                continue
            if key.startswith(("item.", "block.")):
                parts = key.split(".")
                if len(parts) >= 3:
                    store.names[f"{parts[1]}:{'.'.join(parts[2:])}"] = _clean(val)
            elif key.startswith("tooltip."):
                parts = key.split(".")
                if len(parts) >= 3:
                    store.tooltips[f"{parts[1]}:{'.'.join(parts[2:])}"] = _clean(val)
            if key.startswith(_LANG_KEEP):
                store.lang[key] = _clean(val)
        return

    if m := _SPECIES_ADD_RE.search(path):
        raw["_origin"] = origin
        raw["_addon"] = addon
        store.species_adds.append(raw)
        return

    if m := _SPECIES_RE.search(path):
        if sp := parse_species(raw, path, origin):
            sp["addon"] = addon
            if addon and path in store.species_by_path:
                pass  # never let an inactive add-on replace base data
            else:
                store.species_by_path[path] = sp
        return

    if m := _SPAWN_RE.search(path):
        entries = parse_spawn_file(raw, path, origin, addon)
        if addon:
            store.addon_spawns.extend(entries)
        elif entries or path in store.spawns_by_path:
            store.spawns_by_path[path] = entries
        return

    if m := _PRESET_RE.search(path):
        store.presets[m.group(2)] = raw
        return

    if m := _SEASONING_RE.search(path):
        if not addon:
            store.seasonings[path] = raw
        return

    if m := _BAIT_RE.search(path):
        if not addon:
            store.baits[path] = raw
        return

    if m := _FOSSIL_RE.search(path):
        store.fossils.append({"id": m.group(2), "raw": raw, "src": origin})
        return

    if m := _TRAINER_RE.search(path):
        tid = m.group(1)
        store.trainers[tid] = parse_trainer(raw, tid, origin)
        return

    if m := _MOB_RE.search(path):
        mid = m.group(1).split("/")[-1]
        store.mobs[mid] = {
            "series": raw.get("series") or [],
            "type": raw.get("type"),
            "biomes": raw.get("biomeTagWhitelist") or [],
            "biomesBlack": raw.get("biomeTagBlacklist") or [],
            "signatureItem": raw.get("signatureItem"),
            "maxDefeats": raw.get("maxTrainerDefeats"),
            "spawnWeightFactor": raw.get("spawnWeightFactor"),
            "requiresDefeats": raw.get("requiredDefeats") or raw.get("requirements"),
            "src": origin,
        }
        return

    if m := _SERIES_RE.search(path):
        store.series[m.group(1)] = {
            "title": _txt(raw.get("title")) or m.group(1),
            "desc": _txt(raw.get("description")),
            "difficulty": raw.get("difficulty"),
            "src": origin,
        }
        return

    if m := _ADV_RE.search(path):
        ns, rel = m.group(1), m.group(2)
        if rel.startswith("recipes/"):
            return
        disp = raw.get("display") or {}
        icon = disp.get("icon")
        if isinstance(icon, dict):
            icon = icon.get("id") or icon.get("item")
        store.advancements[f"{ns}:{rel}"] = {
            "parent": raw.get("parent"),
            "title": _txt(disp.get("title")),
            "desc": _txt(disp.get("description")),
            "icon": icon,
            "frame": disp.get("frame", "task"),
            "hidden": disp.get("hidden", False),
            "src": origin,
        }
        return

    if m := _RECIPE_RE.search(path):
        if rec := parse_recipe(raw, path, origin):
            rec["addon"] = addon
            if addon:
                store.addon_recipes.append(rec)
            else:
                store.recipes_by_path[path] = rec
        return

    if m := _LOOT_RE.search(path):
        table_id = f"{m.group(1)}:{m.group(2)}"
        entries = []
        for e in parse_loot(raw, origin, table_id):
            e["addon"] = addon
            entries.append(e)
        if addon:
            store.addon_loot.extend(entries)
        elif entries or path in store.loot_by_path:
            store.loot_by_path[path] = entries
        return

    if m := _ITEMTAG_RE.search(path):
        tag_id = f"{m.group(1)}:{m.group(2)}"
        for v in raw.get("values", []) or []:
            vid = v.get("id") if isinstance(v, dict) else v
            if isinstance(vid, str):
                store.item_tags[tag_id].append(vid)
        return

    if m := _BLOCKTAG_RE.search(path):
        tag_id = f"{m.group(1)}:{m.group(2)}"
        for v in raw.get("values", []) or []:
            vid = v.get("id") if isinstance(v, dict) else v
            if isinstance(vid, str):
                store.block_tags[tag_id].append(vid)
        return

    if m := _BIOMETAG_RE.search(path):
        tag_id = f"{m.group(1)}:{m.group(2)}"
        for v in raw.get("values", []) or []:
            vid = v.get("id") if isinstance(v, dict) else v
            if isinstance(vid, str):
                store.biome_tags[tag_id].append(vid)
        return


_INTERESTING = ("data/", "assets/")


def scan_zip(store: Store, zip_path: str, addon: bool, lang_only: bool = False) -> None:
    origin = os.path.basename(zip_path)
    n_before = 0
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            for fname in names:
                if not fname.endswith(".json"):
                    continue
                if lang_only and not _LANG_RE.search(fname):
                    continue
                if not (fname.startswith(_INTERESTING) or "/lang/" in fname):
                    continue
                try:
                    ingest(store, origin, fname, zf.read(fname), addon)
                except Exception:
                    continue
    except zipfile.BadZipFile:
        return
    store.origins.append({"file": origin, "addon": addon, "langOnly": lang_only})


# ---------------------------------------------------------------- merge / post

def apply_species_additions(store: Store) -> None:
    for add in store.species_adds:
        if add.get("_addon"):
            continue  # inactive add-on packs must not change base species data
        target = (add.get("target") or "").split(":")[-1].lower()
        target = target.replace("-", "").replace(" ", "")
        sp = store.species.get(target)
        if not sp:
            continue
        sp.setdefault("modifiedBy", []).append(add["_origin"])
        if "drops" in add:
            drops = add["drops"] or {}
            dentries = [{"item": _norm(d["item"]), "pct": d.get("percentage"),
                         "range": d.get("quantityRange")}
                        for d in drops.get("entries", []) or []
                        if isinstance(d, dict) and "item" in d]
            sp["drops"] = dentries
            sp["dropAmount"] = drops.get("amount")
        if "baseStats" in add:
            sp["stats"] = {k: (add["baseStats"] or {}).get(k, sp["stats"].get(k, 0))
                           for k in _STAT_KEYS}
        if "catchRate" in add:
            sp["catchRate"] = add["catchRate"]
        if "evolutions" in add:
            for ev in add["evolutions"] or []:
                if isinstance(ev, dict):
                    sp["evolutions"].append({
                        "to": (ev.get("result") or "").split(" ")[0].lower(),
                        "resultRaw": ev.get("result") or "",
                        "variant": ev.get("variant"),
                        "consumeHeldItem": ev.get("consumeHeldItem"),
                        "req": ev.get("requirements") or [],
                        "added": add["_origin"],
                    })


def resolve_tags(tags: dict[str, list]) -> dict[str, list]:
    """Flatten #tag references inside tag member lists."""
    out: dict[str, list] = {}

    def expand(tag: str, seen: set[str]) -> list[str]:
        if tag in seen:
            return []
        seen.add(tag)
        members: list[str] = []
        for v in tags.get(tag, []):
            if v.startswith("#"):
                members.extend(expand(v.lstrip("#"), seen))
            else:
                members.append(v)
        return members

    for tag in tags:
        seen: set[str] = set()
        flat = expand(tag, seen)
        # dedupe, keep order
        out[tag] = list(dict.fromkeys(flat))
    return out


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default=DEFAULT_PACK)
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--out", default=os.path.join(here, "..", "data", "wikidata.json"))
    args = ap.parse_args()

    pack = args.pack
    if not os.path.isdir(pack):
        sys.exit(f"pack folder not found: {pack}")

    store = Store()

    mods_dir = os.path.join(pack, "mods")
    jars = sorted(f for f in os.listdir(mods_dir)
                  if f.endswith(".jar") and not f.endswith(".disabled"))
    for i, jar in enumerate(jars):
        scan_zip(store, os.path.join(mods_dir, jar), addon=False)
        if (i + 1) % 25 == 0:
            print(f"  ... {i + 1}/{len(jars)} jars")

    dp_dir = os.path.join(pack, "datapacks")
    for f in sorted(os.listdir(dp_dir)):
        if f.endswith(".zip"):
            scan_zip(store, os.path.join(dp_dir, f), addon=False)
    extra_dir = os.path.join(dp_dir, "extra")
    if os.path.isdir(extra_dir):
        for f in sorted(os.listdir(extra_dir)):
            if f.endswith(".zip"):
                scan_zip(store, os.path.join(extra_dir, f), addon=True)

    rp_dir = os.path.join(pack, "resourcepacks")
    if os.path.isdir(rp_dir):
        for f in sorted(os.listdir(rp_dir)):
            if f.endswith(".zip"):
                scan_zip(store, os.path.join(rp_dir, f), addon=False, lang_only=True)

    store.finalize()
    apply_species_additions(store)

    data = {
        "names": store.names,
        "tooltips": store.tooltips,
        "lang": store.lang,
        "itemTags": resolve_tags(store.item_tags),
        "blockTags": resolve_tags(store.block_tags),
        "biomeTags": resolve_tags(store.biome_tags),
        "recipes": store.all_recipes,
        "loot": [e for e in store.all_loot if e["e"] > 0],
        "species": store.species,
        "spawns": store.all_spawns,
        "presets": store.presets,
        "seasonings": list(store.seasonings.values()),
        "baits": list(store.baits.values()),
        "fossils": store.fossils,
        "trainers": store.trainers,
        "mobs": store.mobs,
        "series": store.series,
        "advancements": store.advancements,
        "origins": store.origins,
    }

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"), ensure_ascii=False)

    print(f"\nwrote {out_path} ({os.path.getsize(out_path) / 1_000_000:.1f} MB)")
    for k in ("names", "recipes", "loot", "species", "spawns", "trainers",
              "mobs", "advancements", "itemTags", "biomeTags", "fossils"):
        v = data[k]
        print(f"  {len(v):>6}  {k}")


if __name__ == "__main__":
    main()
