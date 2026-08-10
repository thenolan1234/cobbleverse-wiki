#!/usr/bin/env python3
"""
render_trainers.py - render trainer NPC portraits from their Minecraft skins.

RCT trainers are player-model NPCs whose skins ship in the pack
(COBBLEVERSE RCTmod RP.zip overriding the rctmod jar). The player model is a
fixed geometry, so each skin renders through the same pipeline as the
Pokemon models. Slim-arm skins are detected per-skin; legacy 64x32 skins
use mirrored right-limb UVs, exactly like the game.

Output: renders/trainers/<trainer_id>.png. Idempotent.
"""

from __future__ import annotations

import io
import json
import os
import zipfile

from PIL import Image

import render_models as rm

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
PACK = rm.PACK
OUT = os.path.join(ROOT, "renders", "trainers")
FINAL = 160

SKIN_SOURCES = [
    os.path.join(PACK, "resourcepacks", "COBBLEVERSE RCTmod RP.zip"),
    os.path.join(PACK, "mods", "rctmod-fabric-1.21.1-0.18.1-beta.jar"),
]


def find_skins() -> dict[str, tuple[str, str]]:
    """trainer id -> (archive, path). First source wins (RP overrides jar)."""
    skins: dict[str, tuple[str, str]] = {}
    for arc in SKIN_SOURCES:
        if not os.path.exists(arc):
            continue
        zf = zipfile.ZipFile(arc)
        for n in zf.namelist():
            if "/textures/trainers/" in n and n.endswith(".png"):
                tid = os.path.basename(n)[:-4]
                skins.setdefault(tid, (arc, n))
    return skins


def _cube(name, origin, size, uv, inflate=0.0, mirror=False):
    c = {"origin": list(origin), "size": list(size), "uv": list(uv)}
    if inflate:
        c["inflate"] = inflate
    if mirror:
        c["mirror"] = True
    return {"name": name, "pivot": [0, 0, 0], "cubes": [c]}


def player_geo(slim: bool, legacy: bool) -> dict:
    aw = 3 if slim else 4          # arm width
    bones = [
        _cube("head", (-4, 24, -4), (8, 8, 8), (0, 0)),
        _cube("hat", (-4, 24, -4), (8, 8, 8), (32, 0), inflate=0.6),
        _cube("body", (-4, 12, -2), (8, 12, 4), (16, 16)),
        _cube("arm_right", (-4 - aw, 12, -2), (aw, 12, 4), (40, 16)),
        _cube("leg_right", (-3.95, 0, -2), (4, 12, 4), (0, 16)),
    ]
    if legacy:
        bones += [
            _cube("arm_left", (4, 12, -2), (aw, 12, 4), (40, 16), mirror=True),
            _cube("leg_left", (-0.05, 0, -2), (4, 12, 4), (0, 16), mirror=True),
        ]
    else:
        bones += [
            _cube("arm_left", (4, 12, -2), (aw, 12, 4), (32, 48)),
            _cube("leg_left", (-0.05, 0, -2), (4, 12, 4), (16, 48)),
            _cube("jacket", (-4, 12, -2), (8, 12, 4), (16, 32), inflate=0.4),
            _cube("sleeve_right", (-4 - aw, 12, -2), (aw, 12, 4), (40, 32),
                  inflate=0.3),
            _cube("sleeve_left", (4, 12, -2), (aw, 12, 4), (48, 48),
                  inflate=0.3),
            _cube("pants_right", (-3.95, 0, -2), (4, 12, 4), (0, 32),
                  inflate=0.25),
            _cube("pants_left", (-0.05, 0, -2), (4, 12, 4), (0, 48),
                  inflate=0.25),
        ]
    return {"minecraft:geometry": [{
        "description": {"identifier": "geometry.player",
                        "texture_width": 64,
                        "texture_height": 32 if legacy else 64},
        "bones": bones,
    }]}


def is_slim(skin: Image.Image) -> bool:
    if skin.height < 64:
        return False
    # classic skins have opaque pixels in the arm's 4th column region
    try:
        return skin.getpixel((54, 20))[3] == 0
    except Exception:
        return False


def render_skin(skin: Image.Image) -> Image.Image:
    legacy = skin.height == 32
    geo = player_geo(is_slim(skin), legacy)
    cubes, tw, th = rm.build_faces(geo)
    img = rm.render(cubes, tw, th, skin, size=360)
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    side = max(img.width, img.height)
    pad = int(side * 0.06)
    sq = Image.new("RGBA", (side + 2 * pad,) * 2, (0, 0, 0, 0))
    sq.alpha_composite(img, (pad + (side - img.width) // 2,
                             pad + (side - img.height) // 2))
    return sq.resize((FINAL, FINAL), Image.Resampling.LANCZOS)


def main() -> None:
    with open(os.path.join(ROOT, "data", "wikidata.json"),
              encoding="utf-8") as fh:
        trainers = set(json.load(fh)["trainers"].keys())
    skins = find_skins()
    targets = sorted(trainers & set(skins.keys()))
    print(f"{len(targets)} of {len(trainers)} trainers have skins "
          f"({len(skins)} skin files found)")
    os.makedirs(OUT, exist_ok=True)
    zips: dict[str, zipfile.ZipFile] = {}
    ok = skip = err = 0
    for i, tid in enumerate(targets, 1):
        out_path = os.path.join(OUT, f"{tid}.png")
        if os.path.exists(out_path):
            skip += 1
            continue
        arc, path = skins[tid]
        try:
            if arc not in zips:
                zips[arc] = zipfile.ZipFile(arc)
            skin = Image.open(io.BytesIO(zips[arc].read(path))).convert("RGBA")
            render_skin(skin).save(out_path)
            ok += 1
        except Exception as e:
            err += 1
            if err <= 10:
                print(f"  {tid}: {type(e).__name__}: {e}")
        if i % 250 == 0:
            print(f"  ... {i}/{len(targets)}")
    print(f"done: {ok} rendered, {skip} cached, {err} errors")


if __name__ == "__main__":
    main()
