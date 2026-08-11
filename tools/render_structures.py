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
    os.path.join(PACK, "mods", "Cobblemon-fabric-1.7.3+1.21.1.jar"),
    os.path.join(PACK, "mods", "cobblemon-additions-4.1.6.jar"),
    os.path.join(PACK, "mods", "mega_showdown-fabric-1.8.4+1.7.3+1.21.1.jar"),
    os.path.join(PACK, "mods", "VanillaBackport-fabric-1.21.1-1.1.7.10.jar"),
]
# scatter-prop folders and jigsaw piece sets that are shown assembled instead
_STANDALONE_EXCLUDE = ("/decorations/", "/shipwreck_coves/",
                       "/turnback_cave/")

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
                "dripleaf", "pickle", "bamboo", "bush", "rose", "daisy", "tulip",
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
            "cross", "plant", "crop", "pattern", "front")
_TEX_SIDE = ("side", "north", "all", "texture", "particle", "front", "top",
             "end", "cross", "plant", "crop", "pattern")


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


# ---------------------------------------------------------------- tints

# raw grass/foliage textures are grayscale in the assets and tinted by
# biome in game - bake a plains-ish tint
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
    top, side = block_textures(idx, name)
    short = name.split(":")[-1]
    if short == "grass_block":
        top = _tint(top, GRASS_TINT)
    elif short in _GRASS_BOTH:
        top, side = _tint(top, GRASS_TINT), _tint(side, GRASS_TINT)
    elif (short.endswith("_leaves")
          and not any(short.startswith(p) for p in _PRECOLORED_LEAVES)):
        top, side = _tint(top, FOLIAGE_TINT), _tint(side, FOLIAGE_TINT)
    return top, side


# ---------------------------------------------------------------- shapes
#
# Non-full-cube blocks get an approximate real shape instead of a stretched
# unit cube. Shared by the isometric painter and the 3D voxel exporter:
#   {"t":"cross"}                  two crossed quads (plants)
#   {"t":"bx","b":[[x0,y0,z0,x1,y1,z1],...], "u":[u0,v0,u1,v1]?}
#       axis-aligned boxes in 16ths with projected UVs ("u" overrides the
#       side-face texture window, e.g. chains whose links sit at u 0..3)
#   {"t":"fence"|"wall"|"pane"}    center post + arms toward neighbors

_KEEP_PROPS = ("type", "half", "facing", "open", "layers")
_CROSS_WORDS = ("sapling", "fern", "seagrass", "kelp", "tulip", "orchid",
                "allium", "dandelion", "poppy", "lilac", "peony", "daisy",
                "rose", "cobweb", "amethyst_cluster", "bush", "vine",
                "sugar_cane", "dripstone", "wheat", "beetroot", "carrot",
                "potato", "pitcher", "sunflower", "torchflower", "sprouts",
                "roots", "bluet", "lily_of_the_valley", "cornflower",
                "propagule", "dripleaf", "lichen", "mushroom", "flower",
                "azalea", "frogspawn", "crop", "grass")
_SIDE_PLATE = {"north": (0, 0, 13, 16, 16, 16), "south": (0, 0, 0, 16, 16, 3),
               "east": (0, 0, 0, 3, 16, 16), "west": (13, 0, 0, 16, 16, 16)}
_WALL_PLATE = {"north": (0, 0, 15, 16, 16, 16), "south": (0, 0, 0, 16, 16, 1),
               "east": (0, 0, 0, 1, 16, 16), "west": (15, 0, 0, 16, 16, 16)}


def _bx(*boxes, u=None):
    d = {"t": "bx", "b": [list(b) for b in boxes]}
    if u:
        d["u"] = list(u)
    return d


def shape_for(name: str, props: dict):
    short = name.split(":")[-1]
    p = props or {}
    if (short.endswith(("_block", "_stem", "_leaves"))
            or short == "grass_block"):
        return None
    if "potted" in short or short == "flower_pot":
        return _bx((5, 0, 5, 11, 8, 11))
    if any(w in short for w in _CROSS_WORDS):
        return {"t": "cross"}
    if "torch" in short:
        return _bx((7, 0, 7, 9, 10, 9))
    if "lantern" in short:
        return _bx((5, 0, 5, 11, 9, 11))
    if "candle" in short:
        return _bx((6, 0, 6, 10, 7, 10))
    if short == "chain":
        return _bx((6.5, 0, 6.5, 9.5, 16, 9.5), u=(0, 0, 3, 16))
    if "end_rod" in short or "lightning_rod" in short:
        return _bx((6, 0, 6, 10, 16, 10))
    if "bamboo" in short:
        return _bx((6.5, 0, 6.5, 9.5, 16, 9.5), u=(0, 0, 3, 16))
    if short.endswith("_slab"):
        if p.get("type") == "double":
            return None
        return _bx((0, 8, 0, 16, 16, 16) if p.get("type") == "top"
                   else (0, 0, 0, 16, 8, 16))
    if short.endswith("_stairs"):
        f = p.get("facing", "north")
        top = p.get("half") == "top"
        slab = (0, 8, 0, 16, 16, 16) if top else (0, 0, 0, 16, 8, 16)
        rx, rz = (0, 16), (0, 16)
        if f == "north":
            rz = (0, 8)
        elif f == "south":
            rz = (8, 16)
        elif f == "east":
            rx = (8, 16)
        else:
            rx = (0, 8)
        y0, y1 = (0, 8) if top else (8, 16)
        return _bx(slab, (rx[0], y0, rz[0], rx[1], y1, rz[1]))
    if short.endswith("_trapdoor"):
        if p.get("open") == "true":
            return _bx(_SIDE_PLATE.get(p.get("facing"),
                                       _SIDE_PLATE["north"]))
        return _bx((0, 13, 0, 16, 16, 16) if p.get("half") == "top"
                   else (0, 0, 0, 16, 3, 16))
    if short.endswith("_door"):
        return _bx(_SIDE_PLATE.get(p.get("facing"), _SIDE_PLATE["north"]))
    if "carpet" in short:
        return _bx((0, 0, 0, 16, 1, 16))
    if "pressure_plate" in short:
        return _bx((1, 0, 1, 15, 1, 15))
    if short == "snow":
        layers = int(p.get("layers", "1"))
        return None if layers >= 8 else _bx((0, 0, 0, 16, 2 * layers, 16))
    if short in ("chest", "trapped_chest", "ender_chest"):
        return _bx((1, 0, 1, 15, 14, 15))
    if short.endswith("_bed"):
        return _bx((0, 0, 0, 16, 9, 16))
    if short.endswith(("_fence", "_fence_gate")):
        return {"t": "fence"}
    if short.endswith("_wall"):
        return {"t": "wall"}
    if "pane" in short or short == "iron_bars":
        return {"t": "pane"}
    if short == "ladder" or "wall_sign" in short or "wall_banner" in short:
        return _bx(_WALL_PLATE.get(p.get("facing"), _WALL_PLATE["north"]))
    if short.endswith("_sign"):
        return _bx((1, 6, 7, 15, 14, 9), (7, 0, 7, 9, 6, 9))
    if short.endswith("_banner"):
        return _bx((1, 0, 7, 15, 16, 9))
    if "button" in short or short == "lever":
        return _bx((5, 0, 5, 11, 3, 11))
    if "skull" in short or "head" in short:
        return _bx((4, 0, 4, 12, 8, 12))
    if "campfire" in short:
        return _bx((0, 0, 0, 16, 4, 16))
    if short == "lily_pad":
        return _bx((1, 0, 1, 15, 1, 15))
    if "rail" in short:
        return _bx((0, 0, 0, 16, 1, 16))
    if "anvil" in short:
        return _bx((2, 0, 2, 14, 16, 14))
    if short == "hopper":
        return _bx((0, 8, 0, 16, 16, 16), (4, 0, 4, 12, 8, 12))
    if short == "lectern":
        return _bx((0, 0, 0, 16, 2, 16), (4, 2, 4, 12, 15, 12))
    if short == "brewing_stand":
        return _bx((0, 0, 0, 16, 2, 16), (7, 2, 7, 9, 14, 9))
    if short == "bell":
        return _bx((4, 4, 4, 12, 12, 12))
    if short == "sea_pickle":
        return _bx((4, 0, 4, 12, 6, 12))
    if short == "cake":
        return _bx((1, 0, 1, 15, 8, 15))
    if short in ("dirt_path", "farmland"):
        return _bx((0, 0, 0, 16, 15, 16))
    return None


def _collect_props(nbt, offset, name_index, keep, rot, with_props):
    """Like _collect but keeps shape-relevant blockstate properties,
    rotating facing along with the piece."""
    palette = nbt.get("palette") or (nbt.get("palettes") or [[]])[0]
    size = [int(v) for v in nbt["size"]]
    local = []
    for pe in palette:
        nm = str(pe["Name"])
        props = {}
        if with_props:
            props = {str(k): str(v)
                     for k, v in (pe.get("Properties") or {}).items()
                     if str(k) in _KEEP_PROPS}
            if props.get("facing") in _ROT_DIR:
                props["facing"] = _rot_facing(props["facing"], rot % 4)
        key = nm + "|" + ",".join(f"{k}={v}"
                                  for k, v in sorted(props.items()))
        local.append((nm, props, key))
    remap = []
    for nm, props, key in local:
        if key not in name_index:
            name_index[key] = (len(name_index), nm, props)
        remap.append(name_index[key][0])
    ox, oy, oz = offset
    for b in nbt.get("blocks") or []:
        st = int(b["state"])
        if st >= len(local) or is_skipped(local[st][0]):
            continue
        x, y, z = (int(v) for v in b["pos"])
        rx, rz = _rot_pos(x, z, size[0], size[2], rot)
        keep.append((rx + ox, y + oy, rz + oz, remap[st]))


def collect_blocks(parts, with_props=True):
    """[(x, y, z, state)], [(name, props)] across all parts."""
    keep, name_index = [], {}
    for part in parts:
        nbt, offset = part[0], part[1]
        rot = part[2] if len(part) > 2 else 0
        _collect_props(nbt, offset, name_index, keep, rot, with_props)
    ents = [None] * len(name_index)
    for _key, (i, nm, props) in name_index.items():
        ents[i] = (nm, props)
    return keep, ents


# ---------------------------------------------------------------- rendering

def load_nbt(blob: bytes):
    return nbtlib.File.load(io.BytesIO(blob), gzipped=blob[:2] == b"\x1f\x8b")


def _rot_pos(x, z, sx, sz, rot):
    """Rotate a local position clockwise within an sx*sz footprint."""
    if rot == 0:
        return x, z
    if rot == 1:
        return sz - 1 - z, x
    if rot == 2:
        return sx - 1 - x, sz - 1 - z
    return z, sx - 1 - x


def _rot_dims(sx, sz, rot):
    return (sz, sx) if rot % 2 else (sx, sz)


def _collect(nbt, offset, name_index, keep, occupied, rot=0):
    """Append one structure's blocks (with offset and rotation) into a shared
    block list, remapping palette indices into the shared name table."""
    palette = nbt.get("palette") or (nbt.get("palettes") or [[]])[0]
    local = [str(p["Name"]) for p in palette]
    size = [int(v) for v in nbt["size"]]
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
        rx, rz = _rot_pos(x, z, size[0], size[2], rot)
        pos = (rx + ox, y + oy, rz + oz)
        keep.append((pos[0], pos[1], pos[2], remap[st]))
        if not is_clear(local[st]):
            occupied.add(pos)


_POST_CORE = {"fence": (6, 0, 6, 10, 16, 10),
              "wall": (4, 0, 4, 12, 16, 12),
              "pane": (7, 0, 7, 9, 16, 9)}
_POST_ARMS = {
    "fence": {"e": [(10, 6, 7, 16, 9, 9), (10, 12, 7, 16, 15, 9)],
              "w": [(0, 6, 7, 6, 9, 9), (0, 12, 7, 6, 15, 9)],
              "s": [(7, 6, 10, 9, 9, 16), (7, 12, 10, 9, 15, 16)],
              "n": [(7, 6, 0, 9, 9, 6), (7, 12, 0, 9, 15, 6)]},
    "wall": {"e": [(12, 0, 5, 16, 14, 11)], "w": [(0, 0, 5, 4, 14, 11)],
             "s": [(5, 0, 12, 11, 14, 16)], "n": [(5, 0, 0, 11, 14, 4)]},
    "pane": {"e": [(9, 0, 7, 16, 16, 9)], "w": [(0, 0, 7, 7, 16, 9)],
             "s": [(7, 0, 9, 9, 16, 16)], "n": [(7, 0, 0, 9, 16, 7)]},
}


def _shade_img(img: Image.Image, f: float) -> Image.Image:
    r, g, b, a = img.split()
    pt = lambda v: min(255, int(v * f))
    return Image.merge("RGBA", (r.point(pt), g.point(pt), b.point(pt), a))


def _iso_pt(fx, fy, fz):
    """Block-local fraction -> point in a 2S x 2S sprite."""
    return (S + (fx - fz) * S, (fx + fz) * S / 2 - fy * S + S)


def _draw_box(spr, b, top_img, side_south, side_east, uov=None):
    """Warp one axis-aligned sub-box (16ths) into the iso sprite; the
    texture window is projected from the box's extent (vanilla-style)."""
    x0, y0, z0, x1, y1, z1 = (v / 16.0 for v in b)
    if uov:
        su0, sv_t, su1, sv_b = uov[0], uov[1], uov[2], uov[3]
        s_win = ((su0, sv_b), (su1, sv_b), (su1, sv_t), (su0, sv_t))
        e_win = s_win
    else:
        vb, vt = 16 - b[1], 16 - b[4]
        s_win = ((b[0], vb), (b[3], vb), (b[3], vt), (b[0], vt))
        e_win = ((b[2], vb), (b[5], vb), (b[5], vt), (b[2], vt))
    faces = (
        (side_south, s_win,
         (_iso_pt(x0, y0, z1), _iso_pt(x1, y0, z1),
          _iso_pt(x1, y1, z1), _iso_pt(x0, y1, z1))),
        (side_east, e_win,
         (_iso_pt(x1, y0, z0), _iso_pt(x1, y0, z1),
          _iso_pt(x1, y1, z1), _iso_pt(x1, y1, z0))),
        (top_img,
         ((b[0], b[2]), (b[3], b[2]), (b[3], b[5]), (b[0], b[5])),
         (_iso_pt(x0, y1, z0), _iso_pt(x1, y1, z0),
          _iso_pt(x1, y1, z1), _iso_pt(x0, y1, z1))),
    )
    for img, src, dst in faces:
        try:
            co = _coeffs(list(src), list(dst))
        except Exception:
            continue                        # degenerate face
        patch = img.transform((2 * S, 2 * S), Image.Transform.PERSPECTIVE,
                              co, resample=Image.Resampling.NEAREST)
        spr.alpha_composite(patch)


def bake_shape_sprite(shape, top, side, mask=0):
    """2S x 2S sprite for a non-cube block; mask = fence/wall/pane arms
    (1 east, 2 west, 4 south, 8 north)."""
    spr = Image.new("RGBA", (2 * S, 2 * S), (0, 0, 0, 0))
    t = shape["t"]
    if t == "cross":
        spr.alpha_composite(side, (S - 8, 3 * S // 2 - 16))
        return spr
    if t == "bx":
        boxes = [tuple(b) for b in shape["b"]]
        uov = shape.get("u")
    else:
        boxes = [_POST_CORE[t]]
        for bit, d in ((1, "e"), (2, "w"), (4, "s"), (8, "n")):
            if mask & bit:
                boxes += _POST_ARMS[t][d]
        uov = None
    side_s = _shade_img(side, 0.72)
    side_e = _shade_img(side, 0.55)
    # painter order: back-to-front, then bottom-up
    for b in sorted(boxes, key=lambda b: (b[0] + b[2], b[1])):
        _draw_box(spr, b, top, side_s, side_e, uov)
    return spr


def render_parts(parts, idx: AssetIndex,
                 y_clip_frac: float | None = None) -> Image.Image | None:
    """parts: [(nbt, (ox, oy, oz)[, rot]), ...] - render one or many pieces.
    y_clip_frac removes the top of the build for a cutaway interior view."""
    keep, ents = collect_blocks(parts)
    if not keep:
        return None
    if y_clip_frac is not None:
        ys = [k[1] for k in keep]
        clip = min(ys) + int((max(ys) - min(ys)) * y_clip_frac)
        keep = [k for k in keep if k[1] <= clip]
        if not keep:
            return None
    shapes = [shape_for(nm, pr) for nm, pr in ents]
    occupied = {(x, y, z) for x, y, z, st in keep
                if shapes[st] is None and not is_clear(ents[st][0])}
    conn = {(x, y, z) for x, y, z, st in keep
            if shapes[st] is None
            or shapes[st]["t"] in ("fence", "wall", "pane")}

    texs: dict[int, tuple] = {}
    sprites: dict = {}

    def tex(st):
        if st not in texs:
            texs[st] = block_textures_tinted(idx, ents[st][0])
        return texs[st]

    def sprite(st, x, y, z):
        sh = shapes[st]
        if sh is None:
            if st not in sprites:
                sprites[st] = bake_sprite(*tex(st))
            return sprites[st]
        if sh["t"] in ("cross", "bx"):
            if st not in sprites:
                sprites[st] = bake_shape_sprite(sh, *tex(st))
            return sprites[st]
        mask = ((1 if (x + 1, y, z) in conn else 0)
                | (2 if (x - 1, y, z) in conn else 0)
                | (4 if (x, y, z + 1) in conn else 0)
                | (8 if (x, y, z - 1) in conn else 0))
        kk = (st, mask)
        if kk not in sprites:
            sprites[kk] = bake_shape_sprite(sh, *tex(st), mask)
        return sprites[kk]

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
        canvas.alpha_composite(sprite(st, x, y, z), (px, py))

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
        if re.fullmatch(r"\d{3}", digits):
            coord = tuple(int(c) - 1 for c in digits)      # [x][y][z]
        elif re.fullmatch(r"\d+x\d+", digits):
            a, b = (int(v) - 1 for v in digits.split("x"))
            coord = (a, 0, b)                              # flat 2D grid
        else:
            return None
        nbt = load_nbt(zf.read(path))
        size = [int(v) for v in nbt["size"]]
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


# ---------------------------------------------------------------- jigsaw

_DIRS = {"north": (0, 0, -1), "south": (0, 0, 1),
         "east": (1, 0, 0), "west": (-1, 0, 0),
         "up": (0, 1, 0), "down": (0, -1, 0)}
_OPP = {"north": "south", "south": "north", "east": "west", "west": "east",
        "up": "down", "down": "up"}
_ROT_DIR = {"north": ["north", "east", "south", "west"],
            "east": ["east", "south", "west", "north"],
            "south": ["south", "west", "north", "east"],
            "west": ["west", "north", "east", "south"]}


def _rot_facing(facing, rot):
    if facing in ("up", "down"):
        return facing
    return _ROT_DIR[facing][rot]


class Jigsaw:
    """A jigsaw assembler good enough for one illustrative layout."""

    def __init__(self, arcs, seed=1337, max_pieces=70, max_depth=7):
        import random
        self.zips = {a: zipfile.ZipFile(a) for a in arcs if os.path.exists(a)}
        self.rng = random.Random(seed)
        self.max_pieces = max_pieces
        self.max_depth = max_depth
        self.nbt_cache: dict[str, object] = {}
        self.jig_cache: dict[str, list] = {}

    def _read(self, path):
        for zf in self.zips.values():
            try:
                return zf.read(path)
            except KeyError:
                continue
        return None

    def read_json_rl(self, kind, rl):
        ns, rest = rl.split(":", 1)
        blob = self._read(f"data/{ns}/worldgen/{kind}/{rest}.json")
        return json.loads(blob.decode("utf-8-sig")) if blob else None

    def load_nbt_rl(self, rl):
        if rl in self.nbt_cache:
            return self.nbt_cache[rl]
        ns, rest = rl.split(":", 1)
        blob = (self._read(f"data/{ns}/structures/{rest}.nbt")
                or self._read(f"data/{ns}/structure/{rest}.nbt"))
        nbt = load_nbt(blob) if blob else None
        self.nbt_cache[rl] = nbt
        return nbt

    def jigsaw_blocks(self, rl):
        """[(pos, facing, name, target, pool)] for a piece."""
        if rl in self.jig_cache:
            return self.jig_cache[rl]
        out = []
        nbt = self.load_nbt_rl(rl)
        if nbt is not None:
            palette = nbt.get("palette") or (nbt.get("palettes") or [[]])[0]
            jig_states = {}
            for i, p in enumerate(palette):
                if str(p["Name"]) == "minecraft:jigsaw":
                    ori = str((p.get("Properties") or {}).get(
                        "orientation", "north_up"))
                    jig_states[i] = ori.split("_")[0]
            for b in nbt.get("blocks") or []:
                st = int(b["state"])
                if st not in jig_states:
                    continue
                bn = b.get("nbt") or {}
                out.append((tuple(int(v) for v in b["pos"]), jig_states[st],
                            str(bn.get("name", "")), str(bn.get("target", "")),
                            str(bn.get("pool", ""))))
        self.jig_cache[rl] = out
        return out

    def pool_elements(self, pool_rl):
        pj = self.read_json_rl("template_pool", pool_rl)
        if not pj:
            return [], None
        els = []
        for e in pj.get("elements", []):
            loc = (e.get("element") or {}).get("location")
            if loc:
                els += [loc] * max(1, int(e.get("weight", 1)))
        return els, pj.get("fallback")

    def assemble(self, start_pool):
        els, _ = self.pool_elements(start_pool)
        if not els:
            return []
        start = self.rng.choice(els)
        nbt = self.load_nbt_rl(start)
        if nbt is None:
            return []
        size = [int(v) for v in nbt["size"]]
        placed = [(start, (0, 0, 0), 0)]
        boxes = [((0, 0, 0), (size[0], size[1], size[2]))]
        queue = [(start, (0, 0, 0), 0, 0)]     # rl, offset, rot, depth
        while queue and len(placed) < self.max_pieces:
            rl, off, rot, depth = queue.pop(0)
            src_nbt = self.load_nbt_rl(rl)
            ssize = [int(v) for v in src_nbt["size"]]
            for jpos, jfac, jname, jtarget, jpool in self.jigsaw_blocks(rl):
                if not jpool or jpool.endswith("empty"):
                    continue
                rx, rz = _rot_pos(jpos[0], jpos[2], ssize[0], ssize[2], rot)
                wpos = (rx + off[0], jpos[1] + off[1], rz + off[2])
                wfac = _rot_facing(jfac, rot)
                d = _DIRS[wfac]
                anchor = (wpos[0] + d[0], wpos[1] + d[1], wpos[2] + d[2])
                pools = [jpool]
                _, fb = self.pool_elements(jpool)
                if fb:
                    pools.append(fb)
                if depth + 1 >= self.max_depth and fb:
                    pools = [fb]
                done = False
                for pool_rl in pools:
                    if done:
                        break
                    cands, _ = self.pool_elements(pool_rl)
                    self.rng.shuffle(cands)
                    for cand in cands:
                        if done:
                            break
                        cnbt = self.load_nbt_rl(cand)
                        if cnbt is None:
                            continue
                        csize = [int(v) for v in cnbt["size"]]
                        cjigs = [j for j in self.jigsaw_blocks(cand)
                                 if j[2] == jtarget or j[3] == jname]
                        if not cjigs:
                            cjigs = [j for j in self.jigsaw_blocks(cand)]
                        for cpos, cfac, _, _, _ in cjigs:
                            for crot in range(4):
                                if _rot_facing(cfac, crot) != _OPP[wfac]:
                                    continue
                                ccx, ccz = _rot_pos(cpos[0], cpos[2],
                                                    csize[0], csize[2], crot)
                                coff = (anchor[0] - ccx, anchor[1] - cpos[1],
                                        anchor[2] - ccz)
                                w, dpt = _rot_dims(csize[0], csize[2], crot)
                                box = (coff, (w, csize[1], dpt))
                                if any(_overlap(box, b, shrink=1)
                                       for b in boxes):
                                    continue
                                placed.append((cand, coff, crot))
                                boxes.append(box)
                                queue.append((cand, coff, crot, depth + 1))
                                done = True
                                break
                            if done:
                                break
        return placed

    def parts(self, start_pool):
        return [(self.load_nbt_rl(rl), off, rot)
                for rl, off, rot in self.assemble(start_pool)]


def _overlap(a, b, shrink=0):
    (ax, ay, az), (aw, ah, ad) = a
    (bx, by, bz), (bw, bh, bd) = b
    return (ax + shrink < bx + bw and bx + shrink < ax + aw and
            ay + shrink < by + bh and by + shrink < ay + ah and
            az + shrink < bz + bd and bz + shrink < az + ad)


# slug, ns, worldgen/structure resource location, seed, max pieces, cutaway
JIGSAW_EXAMPLES = [
    ("turnback-cave-example", "legendarymonuments",
     "legendarymonuments:turnback_cave", 7, 60, 0.55),
    ("lush-shipwreck-cove", "cobblemon",
     "cobblemon:shipwreck_coves/lush_shipwreck_cove", 7, 40, 0.45),
    ("submerged-shipwreck-cove", "cobblemon",
     "cobblemon:shipwreck_coves/submerged_shipwreck_cove", 7, 40, 0.45),
]


def render_jigsaw_example(slug, struct_rl, seed, max_pieces, idx,
                          cutaway=None):
    jig = Jigsaw(STRUCT_SOURCES, seed=seed, max_pieces=max_pieces)
    sj = jig.read_json_rl("structure", struct_rl)
    if not sj or "start_pool" not in sj:
        return None
    jig.max_depth = min(int(sj.get("size", 6)) + 1, 9)
    parts = jig.parts(sj["start_pool"])
    if not parts:
        return None
    print(f"  {slug}: assembled {len(parts)} pieces")
    return render_parts(parts, idx, y_clip_frac=cutaway)


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
            gm = re.match(r"data/([^/]+)/structures?/(.+?)(?:/main)?"
                          r"/(\d{3}|\d+x\d+)\.nbt$", n)
            if gm:
                groups.setdefault((arc, gm.group(1), gm.group(2)), []).append(
                    (gm.group(3), n, info.file_size))
                continue
            if _PIECE_RE.search(n):
                continue                    # other numeric pieces - skip
            if any(w in n for w in _STANDALONE_EXCLUDE):
                continue
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
    force = "--force" in sys.argv
    rest = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = rest[0] if rest else None
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
        if os.path.exists(out_path) and only is None and not force:
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

    for slug, ns, struct_rl, seed, max_pieces, cut in JIGSAW_EXAMPLES:
        if only is not None and only not in slug:
            continue
        out_path = os.path.join(OUT, f"{slug}.png")
        if not os.path.exists(out_path) or only is not None or force:
            try:
                img = render_jigsaw_example(slug, struct_rl, seed,
                                            max_pieces, idx, cut)
                if img is not None:
                    img.save(out_path)
                    ok += 1
            except Exception as ex:
                err += 1
                print(f"  {slug}: {type(ex).__name__}: {ex}")
    for slug, ns, struct_rl, seed, max_pieces, cut in JIGSAW_EXAMPLES:
        if os.path.exists(os.path.join(OUT, f"{slug}.png")):
            inv.append({"slug": slug, "ns": ns, "arc": "",
                        "rel": slug.replace("-", "_") + " (example layout)",
                        "size": 999_000})

    with open(os.path.join(ROOT, "data", "structures.json"), "w",
              encoding="utf-8") as fh:
        json.dump([{k: e[k] for k in ("slug", "ns", "rel", "size")}
                   for e in inv], fh, indent=1)
    print(f"done: {ok} rendered, {skip} cached, {err} errors/empty")


if __name__ == "__main__":
    main()
