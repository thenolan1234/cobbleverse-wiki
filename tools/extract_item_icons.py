#!/usr/bin/env python3
"""
extract_item_icons.py - pull item icon textures out of the pack's own jars
(and the vanilla client jar) for every item the wiki references.

Resolution per item ns:name:
  1. models/item/<name>.json -> textures.layer0 (or first non-# entry),
     following parent chains into block models when needed
  2. textures/item/<name>.png directly
  3. textures/block/<name>.png directly

Output: icons/<ns>/<name>.png (nested item paths flattened with '__').
Animated strip textures keep their first frame. Idempotent.
"""

from __future__ import annotations

import io
import json
import os
import zipfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
PACK = r"C:\Users\nolan\AppData\Roaming\ModrinthApp\profiles\COBBLEVERSE - Pokemon Adventure [Cobblemon]"
VANILLA = r"C:\Users\nolan\AppData\Roaming\ModrinthApp\meta\versions\1.21.1-0.18.4\1.21.1-0.18.4.jar"
OUT = os.path.join(ROOT, "icons")


def collect_item_ids(d: dict) -> set[str]:
    ids: set[str] = set(d["names"].keys())
    for r in d["recipes"]:
        ids.add(r["o"])
        for i in r["i"]:
            if not i.startswith("#"):
                ids.add(i)
    for members in d["itemTags"].values():
        ids.update(m for m in members if not m.startswith("#"))
    for e in d["loot"]:
        if not e.get("ref"):
            ids.add(e["i"])
    for s in d["species"].values():
        for dr in s.get("drops", []):
            ids.add(dr["item"])
    for f in d.get("fossils", []):
        ids.update(x for x in (f.get("raw", {}).get("fossils") or [])
                   if isinstance(x, str))
    for t in d.get("trainers", {}).values():
        for b in t.get("bag", []):
            if b.get("item"):
                ids.add(b["item"])
    for m in d.get("mobs", {}).values():
        if m.get("signatureItem"):
            ids.add(m["signatureItem"])
    return {i for i in ids if ":" in i}


class AssetIndex:
    def __init__(self, jars: list[str]) -> None:
        self.zips: dict[str, zipfile.ZipFile] = {}
        self.models: dict[str, tuple[str, str]] = {}   # ns:models-path -> (jar, entry)
        self.textures: dict[str, tuple[str, str]] = {} # ns:tex-path -> (jar, entry)
        for jar in jars:
            try:
                zf = zipfile.ZipFile(jar)
            except (zipfile.BadZipFile, FileNotFoundError):
                continue
            self.zips[jar] = zf
            for n in zf.namelist():
                if not n.startswith("assets/"):
                    continue
                parts = n.split("/")
                if len(parts) < 4:
                    continue
                ns = parts[1]
                if parts[2] == "models" and n.endswith(".json"):
                    key = f"{ns}:{'/'.join(parts[3:])[:-5]}"
                    self.models.setdefault(key, (jar, n))
                elif parts[2] == "textures" and n.endswith(".png"):
                    key = f"{ns}:{'/'.join(parts[3:])[:-4]}"
                    self.textures.setdefault(key, (jar, n))

    def read_json(self, key: str):
        hit = self.models.get(key)
        if not hit:
            return None
        try:
            return json.loads(self.zips[hit[0]].read(hit[1]).decode("utf-8-sig"))
        except Exception:
            return None

    def read_texture(self, ref: str) -> Image.Image | None:
        if ":" not in ref:
            ref = f"minecraft:{ref}"
        hit = self.textures.get(ref)
        if not hit:
            return None
        try:
            img = Image.open(io.BytesIO(self.zips[hit[0]].read(hit[1])))
            img = img.convert("RGBA")
        except Exception:
            return None
        if img.height > img.width:            # animated strip: first frame
            img = img.crop((0, 0, img.width, img.width))
        return img


_TEX_PREF = ("layer0", "layer1", "all", "top", "side", "front", "particle",
             "texture", "cross", "plant", "fan", "end")


def resolve_texture(idx: AssetIndex, ns: str, name: str) -> Image.Image | None:
    seen = set()
    key = f"{ns}:item/{name}"
    for _ in range(6):                        # follow parent chain
        if key in seen:
            break
        seen.add(key)
        model = idx.read_json(key)
        if model is None:
            break
        texs = model.get("textures") or {}
        cand = None
        for pref in _TEX_PREF:
            v = texs.get(pref)
            if isinstance(v, str) and not v.startswith("#"):
                cand = v
                break
        if cand is None:
            for v in texs.values():
                if isinstance(v, str) and not v.startswith("#"):
                    cand = v
                    break
        if cand:
            img = idx.read_texture(cand)
            if img is not None:
                return img
        parent = model.get("parent")
        if not isinstance(parent, str):
            break
        if ":" not in parent:
            parent = f"minecraft:{parent}"
        pns, ppath = parent.split(":", 1)
        if ppath in ("item/generated", "item/handheld", "builtin/generated",
                     "builtin/entity"):
            break
        key = f"{pns}:{ppath}"
    for direct in (f"{ns}:item/{name}", f"{ns}:items/{name}",
                   f"{ns}:block/{name}", f"{ns}:blocks/{name}"):
        img = idx.read_texture(direct)
        if img is not None:
            return img
    return None


def main() -> None:
    with open(os.path.join(ROOT, "data", "wikidata.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    ids = collect_item_ids(d)
    print(f"{len(ids)} item ids referenced")

    mods_dir = os.path.join(PACK, "mods")
    jars = [os.path.join(mods_dir, f) for f in sorted(os.listdir(mods_dir))
            if f.endswith(".jar")]
    if os.path.exists(VANILLA):
        jars.append(VANILLA)
    else:
        print("WARNING: vanilla jar not found - minecraft: items will lack icons")
    print(f"indexing {len(jars)} jars...")
    idx = AssetIndex(jars)
    print(f"  {len(idx.models)} models, {len(idx.textures)} textures")

    ok = skip = miss = 0
    missing = []
    for item in sorted(ids):
        ns, name = item.split(":", 1)
        safe = name.replace("/", "__")
        out_path = os.path.join(OUT, ns, f"{safe}.png")
        if os.path.exists(out_path):
            skip += 1
            continue
        img = resolve_texture(idx, ns, name)
        if img is None:
            miss += 1
            missing.append(item)
            continue
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        img.save(out_path)
        ok += 1
    total_mb = sum(os.path.getsize(os.path.join(dp, f))
                   for dp, _, fs in os.walk(OUT) for f in fs) / 1_000_000
    print(f"done: {ok} extracted, {skip} cached, {miss} without texture "
          f"({total_mb:.1f} MB)")
    if missing:
        print("sample missing:", missing[:15])


if __name__ == "__main__":
    main()
