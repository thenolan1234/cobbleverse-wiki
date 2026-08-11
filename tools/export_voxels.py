#!/usr/bin/env python3
"""
export_voxels.py - export every structure as compact voxel JSON for the
interactive 3D viewer (viewer.html).

Format per structure (voxels/<slug>.json):
  {
    "size": [x, y, z],
    "palette": [{"n": name, "t": [r,g,b], "s": [r,g,b], "a": [top,side],
                 "o": 1|0}, ...],
    "blocks": "<base64 of Uint16 x,z pairs + Uint8 y,state quads>"
  }
Blocks are packed 6 bytes each: u16 x, u16 z, u8 y, u8 state
(structures are wider than tall; palettes stay under 256 states after merge).

"a" indexes into the shared block-texture atlas voxels/atlas.png (16px tiles,
32 per row). Atlas tile indices stay stable across runs: the sheet is
reloaded and only appended to, so single-structure re-exports don't shift
the indices other JSONs already reference.
"""

from __future__ import annotations

import base64
import json
import math
import os
import struct
import sys

from PIL import Image

import render_structures as rs
from extract_item_icons import VANILLA

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "voxels")
ATLAS_PATH = os.path.join(OUT, "atlas.png")
ATLAS_META = os.path.join(OUT, "atlas_meta.json")
TILE_COLS = 32

# block_textures gives raw textures; grass/foliage are grayscale in the
# assets and tinted by biome in game — bake a plains-ish tint here
GRASS_TINT = (124, 189, 74)
FOLIAGE_TINT = (106, 173, 51)
_GRASS_BOTH = ("short_grass", "grass", "tall_grass", "fern", "large_fern",
               "vine", "lily_pad", "sugar_cane")
_PRECOLORED_LEAVES = ("cherry", "azalea", "flowering_azalea", "pale_oak")


def _tint(img: Image.Image, rgb) -> Image.Image:
    r, g, b, a = img.convert("RGBA").split()
    ch = [c.point(lambda v, m=m: v * m // 255) for c, m in zip((r, g, b), rgb)]
    return Image.merge("RGBA", (*ch, a))


def block_textures_tinted(idx, name: str):
    top, side = rs.block_textures(idx, name)
    short = name.split(":")[-1]
    if short == "grass_block":
        top = _tint(top, GRASS_TINT)
    elif short in _GRASS_BOTH:
        top, side = _tint(top, GRASS_TINT), _tint(side, GRASS_TINT)
    elif (short.endswith("_leaves")
          and not any(short.startswith(p) for p in _PRECOLORED_LEAVES)):
        top, side = _tint(top, FOLIAGE_TINT), _tint(side, FOLIAGE_TINT)
    return top, side


class Atlas:
    """Shared 16px tile sheet; indices are append-only stable across runs."""

    def __init__(self):
        self.tiles: list[Image.Image] = []
        self.index: dict[bytes, int] = {}
        self.dirty = False
        have_png, have_meta = (os.path.exists(ATLAS_PATH),
                               os.path.exists(ATLAS_META))
        if have_png != have_meta:
            # restarting the index space would silently corrupt every JSON
            # that references the old indices
            raise RuntimeError(
                "atlas.png / atlas_meta.json out of sync - delete both and "
                "re-export everything with --force")
        if have_png:
            with open(ATLAS_META) as fh:
                count = json.load(fh)["count"]
            sheet = Image.open(ATLAS_PATH).convert("RGBA")
            need_h = math.ceil(count / TILE_COLS) * 16
            if sheet.width < TILE_COLS * 16 or sheet.height < need_h:
                raise RuntimeError(
                    f"atlas.png too small for meta count {count} - delete "
                    "both and re-export everything with --force")
            for i in range(count):
                cx = (i % TILE_COLS) * 16
                cy = (i // TILE_COLS) * 16
                self._append(sheet.crop((cx, cy, cx + 16, cy + 16)))

    def _append(self, img: Image.Image) -> None:
        self.index[img.tobytes()] = len(self.tiles)
        self.tiles.append(img)

    def add(self, img: Image.Image) -> int:
        img = img.convert("RGBA")
        if img.size != (16, 16):
            img = img.resize((16, 16), Image.Resampling.NEAREST)
        # hard alpha: translucent texels (water 150) otherwise wash out
        # against the page background through the alpha canvas
        r, g, b, a = img.split()
        img = Image.merge("RGBA", (r, g, b,
                                   a.point(lambda v: 255 if v > 127 else 0)))
        got = self.index.get(img.tobytes())
        if got is not None:
            return got
        self.dirty = True
        self._append(img)
        return len(self.tiles) - 1

    def save(self) -> None:
        if not self.dirty:
            return
        rows = max(1, math.ceil(len(self.tiles) / TILE_COLS))
        sheet = Image.new("RGBA", (TILE_COLS * 16, rows * 16), (0, 0, 0, 0))
        for i, t in enumerate(self.tiles):
            sheet.paste(t, ((i % TILE_COLS) * 16, (i // TILE_COLS) * 16))
        sheet.save(ATLAS_PATH)
        with open(ATLAS_META, "w") as fh:
            json.dump({"count": len(self.tiles)}, fh)
        self.dirty = False


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


def export_one(slug, parts, idx, color_cache, atlas):
    keep, names = collect_blocks(parts)
    if not keep or len(names) > 255:
        return None
    xs = [k[0] for k in keep]
    ys = [k[1] for k in keep]
    zs = [k[2] for k in keep]
    x0, y0, z0 = min(xs), min(ys), min(zs)
    if max(ys) - y0 > 255 or max(xs) - x0 > 65000 or max(zs) - z0 > 65000:
        return None
    # the viewer allocates an occupancy byte per bounding-box cell
    if ((max(xs) - x0 + 1) * (max(ys) - y0 + 1) * (max(zs) - z0 + 1)
            > 128_000_000):
        return None
    palette = []
    for nm in names:
        if nm not in color_cache:
            top, side = block_textures_tinted(idx, nm)
            color_cache[nm] = {"t": avg_color(top), "s": avg_color(side),
                               "a": [atlas.add(top), atlas.add(side)]}
        c = color_cache[nm]
        palette.append({"n": nm, "t": c["t"], "s": c["s"], "a": c["a"],
                        "o": 0 if rs.is_clear(nm) else 1})
    buf = bytearray()
    for x, y, z, st in keep:
        buf += struct.pack("<HHBB", x - x0, z - z0, y - y0, st)
    return {"size": [max(xs) - x0 + 1, max(ys) - y0 + 1, max(zs) - z0 + 1],
            "palette": palette,
            "blocks": base64.b64encode(bytes(buf)).decode()}


def main() -> None:
    force = "--force" in sys.argv
    rest = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = rest[0] if rest else None
    inv = rs.inventory()
    mods_dir = os.path.join(rs.PACK, "mods")
    jars = [os.path.join(mods_dir, f) for f in sorted(os.listdir(mods_dir))
            if f.endswith(".jar")]
    if os.path.exists(VANILLA):
        jars.append(VANILLA)
    print("indexing textures...")
    idx = rs.AssetIndex(jars)
    os.makedirs(OUT, exist_ok=True)
    atlas = Atlas()
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
        if os.path.exists(out_path) and not only and not force:
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
            data = export_one(slug, parts, idx, color_cache, atlas)
            if data is None:
                err += 1
                continue
            # persist new tiles BEFORE the JSON that references them, so an
            # interrupted run never leaves dangling atlas indices on disk
            atlas.save()
            with open(out_path, "w") as fh:
                json.dump(data, fh, separators=(",", ":"))
            ok += 1
        except Exception as ex:
            err += 1
            if err <= 10:
                print(f"  {slug}: {type(ex).__name__}: {ex}")
        if i % 40 == 0:
            print(f"  ... {i}/{len(jobs)}")
    atlas.save()
    print(f"atlas: {len(atlas.tiles)} tiles")
    total = sum(os.path.getsize(os.path.join(OUT, f))
                for f in os.listdir(OUT)) / 1_000_000
    print(f"done: {ok} exported, {skip} cached, {err} errors "
          f"({total:.1f} MB)")


if __name__ == "__main__":
    main()
