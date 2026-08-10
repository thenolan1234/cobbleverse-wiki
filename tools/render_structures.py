#!/usr/bin/env python3
"""
render_structures.py - isometric renders of the pack's structure NBT files
(gyms, legendary monuments, leagues, raid dens, poke centers...).

Classic voxel-painter approach: every block becomes a pre-baked isometric
sprite (top diamond + two sheared side faces, textured from the pack's own
block textures), drawn back-to-front with hidden-face culling.

Output: renders/structures/<slug>.png + a JSON inventory for the site build.

    python render_structures.py            # render everything missing
    python render_structures.py moltres    # re-render one (by slug match)
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import zipfile

import nbtlib
from PIL import Image

from extract_item_icons import AssetIndex, VANILLA

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
PACK = r"C:\Users\nolan\AppData\Roaming\ModrinthApp\profiles\COBBLEVERSE - Pokemon Adventure [Cobblemon]"
OUT = os.path.join(ROOT, "renders", "structures")

S = 16                       # half tile width == texture size
MAX_W = 1400                 # downscale renders wider than this

STRUCT_SOURCES = [
    os.path.join(PACK, "datapacks", "COBBLEVERSE-DP-v31.zip"),
    os.path.join(PACK, "mods", "LegendaryMonuments-Cobbleverse.jar"),
    os.path.join(PACK, "mods", "LumyMon-0.6.6.jar"),
    os.path.join(PACK, "datapacks", "PokeCenterPCs-DP.zip"),
]

_SKIP = ("air", "structure_void", "structure_block", "jigsaw", "barrier",
         "light", "command_block")
_CLEAR_WORDS = ("glass", "pane", "leaves", "water", "fence", "wall", "door",
                "trapdoor", "torch", "lantern", "chain", "rail", "bars",
                "sign", "banner", "flower", "sapling", "fern", "tall_grass",
                "short_grass", "seagrass", "vine", "carpet", "pressure_plate",
                "button", "slab", "stairs", "snow", "candle", "campfire",
                "ladder", "bed", "head", "skull", "pot", "crop", "kelp",
                "coral", "egg", "bell", "lightning_rod", "cobweb", "chest",
                "anvil", "brewing", "cauldron", "lectern", "hopper", "azalea",
                "dripleaf", "pickerel", "bush", "rose", "daisy", "tulip",
                "orchid", "allium", "dandelion", "poppy", "lilac", "peony",
                "spawner", "amethyst_cluster", "end_rod", "frogspawn", "wire",
                "lever", "repeater", "comparator", "path", "farmland")
_SPECIAL_COLOR = {
    "minecraft:water": (63, 118, 228, 150),
    "minecraft:lava": (207, 92, 20, 255),
    "minecraft:chest": (162, 115, 52, 255),
    "minecraft:trapped_chest": (162, 115, 52, 255),
    "minecraft:ender_chest": (44, 62, 78, 255),
}


def is_skipped(name: str) -> bool:
    short = name.split(":")[-1]
    return short in _SKIP or short.endswith("_air")


def is_clear(name: str) -> bool:
    short = name.split(":")[-1]
    return any(w in short for w in _CLEAR_WORDS)


# ---------------------------------------------------------------- textures

_TEX_TOP = ("top", "up", "end", "all", "texture", "particle", "side", "north",
            "cross", "plant", "pattern", "front")
_TEX_SIDE = ("side", "north", "all", "texture", "particle", "front", "top",
             "end", "cross", "plant", "pattern")


def block_textures(idx: AssetIndex, name: str):
    """(top RGBA 16x16, side RGBA 16x16) for a block id, best effort."""
    if name in _SPECIAL_COLOR:
        img = Image.new("RGBA", (16, 16), _SPECIAL_COLOR[name])
        return img, img
    ns, short = (name.split(":", 1) + [""])[:2] if ":" in name else ("minecraft", name)
    model = idx.read_json(f"{ns}:block/{short}")
    texs = {}
    seen = set()
    key = f"{ns}:block/{short}"
    for _ in range(6):
        if key in seen or model is None:
            break
        seen.add(key)
        for k, v in (model.get("textures") or {}).items():
            texs.setdefault(k, v)
        parent = model.get("parent")
        if not isinstance(parent, str):
            break
        if ":" not in parent:
            parent = "minecraft:" + parent
        key = parent.replace(":", ":", 1)
        pns, ppath = parent.split(":", 1)
        model = idx.read_json(f"{pns}:{ppath}")

    def resolve(pref):
        for k in pref:
            v = texs.get(k)
            while isinstance(v, str) and v.startswith("#"):
                v = texs.get(v[1:])
            if isinstance(v, str):
                img = idx.read_texture(v)
                if img is not None:
                    return img.convert("RGBA").resize((16, 16),
                                                      Image.Resampling.NEAREST)
        return None

    top = resolve(_TEX_TOP)
    side = resolve(_TEX_SIDE) or top
    if top is None:
        for direct in (f"{ns}:block/{short}", f"{ns}:block/{short}_top",
                       f"{ns}:block/{short}_side"):
            img = idx.read_texture(direct)
            if img is not None:
                top = side = img.convert("RGBA").resize(
                    (16, 16), Image.Resampling.NEAREST)
                break
    if top is None:
        top = side = Image.new("RGBA", (16, 16), (140, 130, 150, 255))
    return top, side or top


def _coeffs(src, dst):
    import numpy as np
    a, b = [], []
    for (sx, sy), (dx, dy) in zip(src, dst):
        a.append([dx, dy, 1, 0, 0, 0, -sx * dx, -sx * dy])
        a.append([0, 0, 0, dx, dy, 1, -sy * dx, -sy * dy])
        b += [sx, sy]
    return np.linalg.solve(np.array(a, dtype=float),
                           np.array(b, dtype=float)).tolist()


def bake_sprite(top: Image.Image, side: Image.Image) -> Image.Image:
    """2S x 2S isometric block sprite: diamond top + two sheared sides."""
    spr = Image.new("RGBA", (2 * S, 2 * S), (0, 0, 0, 0))
    sq = [(0, 0), (16, 0), (16, 16), (0, 16)]

    def warp(img, dst, shade):
        img = img.point(lambda v: int(v * shade)) if shade < 1 else img
        # keep alpha unshaded
        if shade < 1:
            img.putalpha(side.getchannel("A") if img is not side else
                         img.getchannel("A"))
        co = _coeffs(sq, dst)
        return img.transform((2 * S, 2 * S), Image.Transform.PERSPECTIVE, co,
                             resample=Image.Resampling.NEAREST)

    def shaded(img, f):
        r, g, b, a = img.split()
        pt = lambda v: min(255, int(v * f))
        return Image.merge("RGBA", (r.point(pt), g.point(pt), b.point(pt), a))

    top_q = [(S, 0), (2 * S, S // 2), (S, S), (0, S // 2)]
    left_q = [(0, S // 2), (S, S), (S, 2 * S), (0, 3 * S // 2)]
    right_q = [(S, S), (2 * S, S // 2), (2 * S, 3 * S // 2), (S, 2 * S)]
    for img, q, f in ((top, top_q, 1.0), (shaded(side, 0.72), left_q, 1.0),
                      (shaded(side, 0.55), right_q, 1.0)):
        co = _coeffs(sq, q)
        patch = img.transform((2 * S, 2 * S), Image.Transform.PERSPECTIVE, co,
                              resample=Image.Resampling.NEAREST)
        spr.alpha_composite(patch)
    return spr


# ---------------------------------------------------------------- rendering

def load_nbt(blob: bytes):
    return nbtlib.File.load(io.BytesIO(blob), gzipped=blob[:2] == b"\x1f\x8b")


def _collect(nbt, offset, name_index, keep, occupied):
    """Append one structure's blocks (with offset) into a shared block list,
    remapping palette indices into the shared name table."""
    palette = nbt.get("palette") or (nbt.get("palettes") or [[]])[0]
    local = [str(p["Name"]) for p in palette]
    remap = []
    for nm in local:
        if nm not in name_index:
            name_index[nm] = len(name_index)
        remap.append(name_index[nm])
    ox, oy, oz = offset
    for b in nbt.get("blocks") or []:
        st = int(b["state"])
        if st >= len(local) or is_skipped(local[st]):
            continue
        x, y, z = (int(v) for v in b["pos"])
        pos = (x + ox, y + oy, z + oz)
        keep.append((pos[0], pos[1], pos[2], remap[st]))
        if not is_clear(local[st]):
            occupied.add(pos)


def render_parts(parts, idx: AssetIndex) -> Image.Image | None:
    """parts: [(nbt, (ox, oy, oz)), ...] - render one or many pieces."""
    keep: list = []
    occupied: set = set()
    name_index: dict[str, int] = {}
    for nbt, offset in parts:
        _collect(nbt, offset, name_index, keep, occupied)
    if not keep:
        return None
    names = [None] * len(name_index)
    for nm, i in name_index.items():
        names[i] = nm

    sprites: dict[int, Image.Image] = {}
    for st in {k[3] for k in keep}:
        sprites[st] = bake_sprite(*block_textures(idx, names[st]))

    xs = [k[0] for k in keep]
    zs = [k[2] for k in keep]
    ys = [k[1] for k in keep]
    px0 = min(x - z for x, y, z, s in keep) * S
    px1 = max(x - z for x, y, z, s in keep) * S
    py0 = min((x + z) * (S // 2) - y * S for x, y, z, s in keep)
    py1 = max((x + z) * (S // 2) - y * S for x, y, z, s in keep)
    W = px1 - px0 + 2 * S
    H = py1 - py0 + 2 * S
    if W * H > 9000 * 9000:
        return None                        # absurd bounds guard
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    keep.sort(key=lambda k: (k[0] + k[2], k[1]))
    for x, y, z, st in keep:
        if ((x + 1, y, z) in occupied and (x, y, z + 1) in occupied
                and (x, y + 1, z) in occupied):
            continue                        # fully hidden from this view
        px = (x - z) * S - px0
        py = (x + z) * (S // 2) - y * S - py0
        canvas.alpha_composite(sprites[st], (px, py))

    bbox = canvas.getbbox()
    if bbox:
        canvas = canvas.crop(bbox)
    if canvas.width > MAX_W:
        canvas = canvas.resize(
            (MAX_W, int(canvas.height * MAX_W / canvas.width)),
            Image.Resampling.LANCZOS)
    return canvas


def render_structure(blob: bytes, idx: AssetIndex) -> Image.Image | None:
    return render_parts([(load_nbt(blob), (0, 0, 0))], idx)


def render_piece_grid(zf: zipfile.ZipFile, pieces: list[tuple[str, str]],
                      idx: AssetIndex) -> Image.Image | None:
    """pieces: [(digits, zip path)] with digits like '213' = grid coords.
    Digit order is [x][y][z]; strides accumulate actual piece sizes."""
    loaded = []
    for digits, path in pieces:
        if not re.fullmatch(r"\d{3}", digits):
            return None
        nbt = load_nbt(zf.read(path))
        size = [int(v) for v in nbt["size"]]
        coord = tuple(int(c) - 1 for c in digits)
        loaded.append((coord, size, nbt))
    # cumulative offsets per axis from the max size at each grid index
    strides = []
    for axis in range(3):
        sizes: dict[int, int] = {}
        for coord, size, _ in loaded:
            sizes[coord[axis]] = max(sizes.get(coord[axis], 0), size[axis])
        offs = {}
        acc = 0
        for i in sorted(sizes):
            offs[i] = acc
            acc += sizes[i]
        strides.append(offs)
    parts = [(nbt, (strides[0][c[0]], strides[1][c[1]], strides[2][c[2]]))
             for c, _, nbt in loaded]
    return render_parts(parts, idx)


# ---------------------------------------------------------------- inventory

_PIECE_RE = re.compile(r"/\d{1,4}\.nbt$")


def inventory():
    """Standalone structure nbts plus assembled 3-digit piece grids."""
    out = []
    seen = set()
    groups: dict[tuple, list] = {}
    for arc in STRUCT_SOURCES:
        if not os.path.exists(arc):
            continue
        zf = zipfile.ZipFile(arc)
        for info in zf.infolist():
            n = info.filename
            if not n.endswith(".nbt") or "/structure" not in n:
                continue
            gm = re.match(r"data/([^/]+)/structures?/(.+?)(?:/main)?/(\d{3})\.nbt$", n)
            if gm:
                groups.setdefault((arc, gm.group(1), gm.group(2)), []).append(
                    (gm.group(3), n, info.file_size))
                continue
            if _PIECE_RE.search(n):
                continue                    # other numeric pieces - skip
            if info.file_size < 2500:
                continue
            m = re.match(r"data/([^/]+)/structures?/(.+)\.nbt$", n)
            if not m:
                continue
            ns, rel = m.group(1), m.group(2)
            slug = re.sub(r"[^a-z0-9]+", "-", rel.lower()).strip("-")
            if slug in seen:
                continue
            seen.add(slug)
            out.append({"slug": slug, "arc": arc, "path": n,
                        "size": info.file_size, "ns": ns, "rel": rel})
    for (arc, ns, rel), pieces in groups.items():
        if len(pieces) < 4:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", rel.lower()).strip("-")
        if slug in seen:
            continue
        seen.add(slug)
        out.append({"slug": slug, "arc": arc, "ns": ns, "rel": rel,
                    "size": sum(p[2] for p in pieces),
                    "group": [(d, p) for d, p, _ in pieces]})
    return out


def main() -> None:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    inv = inventory()
    print(f"{len(inv)} standalone structures found")
    mods_dir = os.path.join(PACK, "mods")
    jars = [os.path.join(mods_dir, f) for f in sorted(os.listdir(mods_dir))
            if f.endswith(".jar")]
    if os.path.exists(VANILLA):
        jars.append(VANILLA)
    print("indexing block textures...")
    idx = AssetIndex(jars)

    os.makedirs(OUT, exist_ok=True)
    ok = skip = err = 0
    todo = [e for e in inv if only is None or only in e["slug"]]
    zips: dict[str, zipfile.ZipFile] = {}
    for i, e in enumerate(todo, 1):
        out_path = os.path.join(OUT, f"{e['slug']}.png")
        if os.path.exists(out_path) and only is None:
            skip += 1
            continue
        try:
            if e["arc"] not in zips:
                zips[e["arc"]] = zipfile.ZipFile(e["arc"])
            if "group" in e:
                img = render_piece_grid(zips[e["arc"]], e["group"], idx)
            else:
                img = render_structure(zips[e["arc"]].read(e["path"]), idx)
            if img is None:
                err += 1
                continue
            img.save(out_path)
            ok += 1
        except Exception as ex:
            err += 1
            if err <= 10:
                print(f"  {e['slug']}: {type(ex).__name__}: {ex}")
        if i % 25 == 0:
            print(f"  ... {i}/{len(todo)}")

    with open(os.path.join(ROOT, "data", "structures.json"), "w",
              encoding="utf-8") as fh:
        json.dump([{k: e[k] for k in ("slug", "ns", "rel", "size")}
                   for e in inv], fh, indent=1)
    print(f"done: {ok} rendered, {skip} cached, {err} errors/empty")


if __name__ == "__main__":
    main()
