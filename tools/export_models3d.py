#!/usr/bin/env python3
"""
export_models3d.py - export every Pokemon model as posed, textured face data
for the interactive 3D viewer, plus its (composited) normal & shiny textures.

Reuses the exact pipeline of render_models.py - pose, resolver texture
stacks, hidden-bone rules, pruning - so the 3D view matches the portraits.

Output per species:
  models3d/<sid>.json  {"tw","th","p":[x,y,z x4 per face],"u":[u,v x4],"s":[shade]}
  models3d/<sid>.png / <sid>_shiny.png
"""

from __future__ import annotations

import json
import os
import sys

import render_models as rm

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "models3d")


def export_one(sid: str, entry: dict) -> str:
    tex = rm.load_texture_stack(entry, False)
    if tex is None:
        return "no-texture"
    blob = rm.read_asset(entry["geo"], entry.get("jar"))
    geo = json.loads(blob.decode("utf-8-sig"))
    wanted = rm.portrait_anims(entry.get("poser"), entry.get("jar"))
    pose = (rm.load_pose(entry["anim"], wanted, entry.get("jar"))
            if entry.get("anim") else {})
    cubes, tw, th = rm.build_faces(geo, pose)
    cubes = rm.prune_strays(cubes)
    pos, uv, shade = [], [], []
    for cb in cubes:
        for quad, uvq in cb["faces"]:
            for p in quad:
                pos += [round(p[0], 2), round(p[1], 2), round(p[2], 2)]
            for q in uvq:
                uv += [round(q[0], 2), round(q[1], 2)]
            shade.append(round(rm._shade(quad), 2))
    if not shade:
        return "empty"
    with open(os.path.join(OUT, f"{sid}.json"), "w") as fh:
        json.dump({"tw": tw, "th": th, "p": pos, "u": uv, "s": shade},
                  fh, separators=(",", ":"))
    tex.save(os.path.join(OUT, f"{sid}.png"))
    shiny = rm.load_texture_stack(entry, True)
    if shiny is not None:
        shiny.save(os.path.join(OUT, f"{sid}_shiny.png"))
    return "ok"


def main() -> None:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    with open(os.path.join(ROOT, "data", "wikidata.json"),
              encoding="utf-8") as fh:
        species = set(json.load(fh)["species"].keys())
    mods_dir = os.path.join(rm.PACK, "mods")
    jars = [os.path.join(mods_dir, f) for f in sorted(os.listdir(mods_dir))
            if f.endswith(".jar")]
    jars.sort(key=lambda j: 0 if "Cobblemon-fabric" in j else 1)
    rp = os.path.join(rm.PACK, "resourcepacks")
    if os.path.isdir(rp):
        jars += [os.path.join(rp, f) for f in sorted(os.listdir(rp))
                 if f.endswith(".zip")
                 and not f.lower().startswith("z do not")]
    found = rm.discover(jars)
    targets = sorted(species & set(found.keys()))
    os.makedirs(OUT, exist_ok=True)
    ok = skip = err = 0
    todo = [s for s in targets if only is None or only in s]
    for i, sid in enumerate(todo, 1):
        if os.path.exists(os.path.join(OUT, f"{sid}.json")) and only is None:
            skip += 1
            continue
        try:
            status = export_one(sid, found[sid])
            if status == "ok":
                ok += 1
            else:
                err += 1
        except Exception as ex:
            err += 1
            if err <= 10:
                print(f"  {sid}: {type(ex).__name__}: {ex}")
        if i % 100 == 0:
            print(f"  ... {i}/{len(todo)}")
    total = sum(os.path.getsize(os.path.join(OUT, f))
                for f in os.listdir(OUT)) / 1_000_000
    print(f"done: {ok} exported, {skip} cached, {err} errors/empty "
          f"({total:.1f} MB)")


if __name__ == "__main__":
    main()
