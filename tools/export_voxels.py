#!/usr/bin/env python3
"""
export_voxels.py - export every structure as compact voxel JSON for the
interactive 3D viewer (viewer.html).

Format per structure (voxels/<slug>.json):
  {
    "size": [x, y, z],
    "palette": [{"n": name, "t": [r,g,b], "s": [r,g,b], "o": 1|0}, ...],
    "blocks": "<base64 of Uint16 x,z pairs + Uint8 y,state quads>"
  }
Blocks are packed 6 bytes each: u16 x, u16 z, u8 y, u8 state
(structures are wider than tall; palettes stay under 256 states after merge).
"""

from __future__ import annotations

import base64
import json
import os
import struct
import sys

from PIL import Image

import render_structures as rs
from extract_item_icons import VANILLA

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "voxels")


def avg_color(img: Image.Image):
    small = img.convert("RGBA").resize((4, 4))
    px = [p for p in small.getdata() if p[3] > 40]
    if not px:
        return [200, 120, 200]
    return [sum(c[i] for c in px) // len(px) for i in range(3)]


def collect_blocks(parts):
    keep, occupied, name_index = [], set(), {}
    for part in parts:
        nbt, offset = part[0], part[1]
        rot = part[2] if len(part) > 2 else 0
        rs._collect(nbt, offset, name_index, keep, occupied, rot)
    names = [None] * len(name_index)
    for nm, i in name_index.items():
        names[i] = nm
    return keep, names


def export_one(slug, parts, idx, color_cache):
    keep, names = collect_blocks(parts)
    if not keep or len(names) > 255:
        return None
    xs = [k[0] for k in keep]
    ys = [k[1] for k in keep]
    zs = [k[2] for k in keep]
    x0, y0, z0 = min(xs), min(ys), min(zs)
    if max(ys) - y0 > 255 or max(xs) - x0 > 65000 or max(zs) - z0 > 65000:
        return None
    palette = []
    for nm in names:
        if nm not in color_cache:
            top, side = rs.block_textures(idx, nm)
            color_cache[nm] = {"t": avg_color(top), "s": avg_color(side)}
        c = color_cache[nm]
        palette.append({"n": nm, "t": c["t"], "s": c["s"],
                        "o": 0 if rs.is_clear(nm) else 1})
    buf = bytearray()
    for x, y, z, st in keep:
        buf += struct.pack("<HHBB", x - x0, z - z0, y - y0, st)
    return {"size": [max(xs) - x0 + 1, max(ys) - y0 + 1, max(zs) - z0 + 1],
            "palette": palette,
            "blocks": base64.b64encode(bytes(buf)).decode()}


def main() -> None:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    inv = rs.inventory()
    mods_dir = os.path.join(rs.PACK, "mods")
    jars = [os.path.join(mods_dir, f) for f in sorted(os.listdir(mods_dir))
            if f.endswith(".jar")]
    if os.path.exists(VANILLA):
        jars.append(VANILLA)
    print("indexing textures...")
    idx = rs.AssetIndex(jars)
    os.makedirs(OUT, exist_ok=True)
    color_cache: dict = {}
    zips: dict = {}
    ok = skip = err = 0

    jobs = []
    for e in inv:
        jobs.append((e["slug"], e))
    for slug, ns, struct_rl, seed, max_pieces, cut in rs.JIGSAW_EXAMPLES:
        jobs.append((slug, {"jigsaw": (struct_rl, seed, max_pieces)}))

    for i, (slug, e) in enumerate(jobs, 1):
        if only and only not in slug:
            continue
        out_path = os.path.join(OUT, f"{slug}.json")
        if os.path.exists(out_path) and not only:
            skip += 1
            continue
        try:
            if "jigsaw" in e:
                struct_rl, seed, max_pieces = e["jigsaw"]
                jig = rs.Jigsaw(rs.STRUCT_SOURCES, seed=seed,
                                max_pieces=max_pieces)
                sj = jig.read_json_rl("structure", struct_rl)
                jig.max_depth = min(int(sj.get("size", 6)) + 1, 9)
                parts = jig.parts(sj["start_pool"])
            elif "group" in e:
                if e["arc"] not in zips:
                    zips[e["arc"]] = rs.zipfile.ZipFile(e["arc"])
                zf = zips[e["arc"]]
                loaded = []
                import re as _re
                for digits, path in e["group"]:
                    nbt = rs.load_nbt(zf.read(path))
                    size = [int(v) for v in nbt["size"]]
                    if _re.fullmatch(r"\d{3}", digits):
                        coord = tuple(int(c) - 1 for c in digits)
                    else:
                        a, b = (int(v) - 1 for v in digits.split("x"))
                        coord = (a, 0, b)
                    loaded.append((coord, size, nbt))
                strides = []
                for axis in range(3):
                    sizes = {}
                    for coord, size, _ in loaded:
                        sizes[coord[axis]] = max(sizes.get(coord[axis], 0),
                                                 size[axis])
                    offs, acc = {}, 0
                    for k in sorted(sizes):
                        offs[k] = acc
                        acc += sizes[k]
                    strides.append(offs)
                parts = [(nbt, (strides[0][c[0]], strides[1][c[1]],
                                strides[2][c[2]]))
                         for c, _, nbt in loaded]
            else:
                if e["arc"] not in zips:
                    zips[e["arc"]] = rs.zipfile.ZipFile(e["arc"])
                parts = [(rs.load_nbt(zips[e["arc"]].read(e["path"])),
                          (0, 0, 0))]
            data = export_one(slug, parts, idx, color_cache)
            if data is None:
                err += 1
                continue
            with open(out_path, "w") as fh:
                json.dump(data, fh, separators=(",", ":"))
            ok += 1
        except Exception as ex:
            err += 1
            if err <= 10:
                print(f"  {slug}: {type(ex).__name__}: {ex}")
        if i % 40 == 0:
            print(f"  ... {i}/{len(jobs)}")
    total = sum(os.path.getsize(os.path.join(OUT, f))
                for f in os.listdir(OUT)) / 1_000_000
    print(f"done: {ok} exported, {skip} cached, {err} errors "
          f"({total:.1f} MB)")


if __name__ == "__main__":
    main()
