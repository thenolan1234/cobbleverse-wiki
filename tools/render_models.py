#!/usr/bin/env python3
"""
render_models.py - render Cobblemon's own Bedrock-format Pokemon models into
3D portrait PNGs, straight from the pack's jars. No external assets: geometry
(.geo.json) and textures come from the mod files, so every render matches what
the pack actually shows in game (including shiny textures).

Output: renders/<speciesid>.png and renders/shiny/<speciesid>.png

    python render_models.py                 # render everything missing
    python render_models.py charizard       # (re)render one species, verbose
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import sys
import zipfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
PACK = r"C:\Users\nolan\AppData\Roaming\ModrinthApp\profiles\COBBLEVERSE - Pokemon Adventure [Cobblemon]"
OUT = os.path.join(ROOT, "renders")

CANVAS = 512          # supersampled render, downscaled to FINAL
FINAL = 192
YAW = math.radians(38)     # three-quarter view
PITCH = math.radians(-14)  # slight look-down


# ---------------------------------------------------------------- math

def rot_x(p, a):
    x, y, z = p
    c, s = math.cos(a), math.sin(a)
    return (x, y * c - z * s, y * s + z * c)


def rot_y(p, a):
    x, y, z = p
    c, s = math.cos(a), math.sin(a)
    return (x * c + z * s, y, -x * s + z * c)


def rot_z(p, a):
    x, y, z = p
    c, s = math.cos(a), math.sin(a)
    return (x * c - y * s, x * s + y * c, z)


def rotate_zyx(p, rx, ry, rz):
    """Bone rotation (geometry AND animation channels - measured to share one
    convention): apply X (negated), then Y, then Z (negated) sequentially,
    degrees. Settled by corner-connectivity metrics over all 48 order/sign
    combos: this is the only family keeping glameow's 15-segment tail
    contiguous (max gap 0.2 units) while machop/charizard/pikachu poses stay
    correct. Do NOT flip Z again - it raises every humanoid's arms."""
    p = rot_x(p, math.radians(-rx))
    p = rot_y(p, math.radians(ry))
    p = rot_z(p, math.radians(-rz))
    return p


def rotate_anim(p, rx, ry, rz):
    """Animation-channel rotation - same convention as rotate_zyx (kept as a
    separate hook so experiments can override one without the other)."""
    return rotate_zyx(p, rx, ry, rz)


# ---------------------------------------------------------------- molang

_MOLANG_VARS = re.compile(r"\b(?:q|v|t|c|query|variable|temp|context)\.[A-Za-z_.]+")
_MOLANG_MATH = {
    "sin": lambda d: math.sin(math.radians(d)),
    "cos": lambda d: math.cos(math.radians(d)),
    "abs": abs,
    "sqrt": lambda x: math.sqrt(max(x, 0)),
    "floor": math.floor,
    "ceil": math.ceil,
    "mod": lambda a, b: math.fmod(a, b) if b else 0,
    "pow": lambda a, b: a ** b,
    "clamp": lambda x, lo, hi: max(lo, min(hi, x)),
    "lerp": lambda a, b, t: a + (b - a) * t,
    "min": min,
    "max": max,
    "random": lambda a, b: (a + b) / 2,
    "exp": math.exp,
    "ln": lambda x: math.log(x) if x > 0 else 0,
    "trunc": math.trunc,
    "round": round,
}


class _MathNS:
    def __getattr__(self, name):
        fn = _MOLANG_MATH.get(name.lower())
        if fn is None:
            return lambda *a: 0.0
        return fn


_ANIM_TIME = re.compile(r"\b(?:q|query)\.(?:anim_time|life_time)\b")
# sample times chosen to avoid aliasing with the common sin(t*90*k) idles
_T_SAMPLES = [k * 0.377 for k in range(16)]


def molang(expr) -> float:
    """Evaluate a molang expression at rest. Time-varying terms are averaged
    over time, so oscillating idles (wing flaps, tail sways) resolve to
    their centre pose instead of a random mid-swing frame."""
    if isinstance(expr, (int, float)):
        return float(expr)
    if not isinstance(expr, str):
        return 0.0
    s = expr.strip().rstrip(";")
    timed = bool(_ANIM_TIME.search(s))
    s = _ANIM_TIME.sub("__T__", s)
    s = _MOLANG_VARS.sub("0", s)
    s = s.replace("Math.", "math.").replace("MATH.", "math.")
    if "?" in s or "->" in s or "=" in s.replace("==", "").replace("<=", "").replace(">=", ""):
        return 0.0                      # complex molang - rest pose
    ns = {"math": _MathNS()}
    try:
        if not timed:
            return float(eval(s, {"__builtins__": {}}, {**ns, "__T__": 0.0}))
        vals = [float(eval(s, {"__builtins__": {}}, {**ns, "__T__": t}))
                for t in _T_SAMPLES]
        return sum(vals) / len(vals)
    except Exception:
        return 0.0


def _kf_value(spec):
    """First-keyframe [x,y,z] out of an animation channel."""
    if spec is None:
        return None
    if isinstance(spec, (int, float, str)):
        v = molang(spec)
        return [v, v, v]
    if isinstance(spec, list):
        return [molang(x) for x in (spec + [0, 0, 0])[:3]]
    if isinstance(spec, dict):
        keys = sorted(spec.keys(), key=lambda k: float(k) if
                      re.fullmatch(r"-?\d+(\.\d+)?", str(k)) else 1e9)
        if not keys:
            return None
        first = spec[keys[0]]
        if isinstance(first, dict):
            first = first.get("post") or first.get("pre")
        return _kf_value(first)
    return None


_BEDROCK_REF = re.compile(r"bedrock\(\s*'[^']*'\s*,\s*'([^']+)'")


def portrait_anims(poser_path: str | None, prefer_jar: str | None = None) -> list[str]:
    """Animation names the game's own poser uses for PORTRAIT/PROFILE."""
    blob = read_asset(poser_path, prefer_jar) if poser_path else None
    if blob is None:
        return []
    try:
        poser = json.loads(blob.decode("utf-8-sig"))
    except Exception:
        return []
    poses = poser.get("poses") or {}
    chosen = None
    for pdata in poses.values():
        types = pdata.get("poseTypes") or []
        if "PORTRAIT" in types or "PROFILE" in types:
            chosen = pdata
            break
    if chosen is None and poses:
        for pdata in poses.values():
            if "STAND" in (pdata.get("poseTypes") or []):
                chosen = pdata
                break
    if not chosen:
        return []
    out = []
    for entry in chosen.get("animations") or []:
        if isinstance(entry, str):
            out.extend(_BEDROCK_REF.findall(entry))
    return out


def load_pose(anim_path: str, wanted: list[str] | None = None,
              prefer_jar: str | None = None) -> dict:
    """bone name -> {'rot': [x,y,z], 'pos': [x,y,z]} from the idle animation."""
    blob = read_asset(anim_path, prefer_jar) if anim_path else None
    if blob is None:
        return {}
    try:
        data = json.loads(blob.decode("utf-8-sig"))
    except Exception:
        return {}
    anims = data.get("animations", {})
    best = None
    for pref in (wanted or []):
        for key in anims:
            if key.endswith("." + pref):
                best = anims[key]
                break
        if best:
            break
    if not best:
        for pref in (".ground_idle", ".idle", ".surfacewater_idle",
                     ".water_idle", ".air_idle", ".battle_idle", ".sleep"):
            for key in anims:
                if key.endswith(pref):
                    best = anims[key]
                    break
            if best:
                break
    if not best:
        return {}
    pose = {}
    for bone, spec in (best.get("bones") or {}).items():
        if not isinstance(spec, dict):
            continue
        rot = _kf_value(spec.get("rotation"))
        pos = _kf_value(spec.get("position"))
        scl = _kf_value(spec.get("scale")) if "scale" in spec else None
        if rot or pos or scl is not None:
            pose[bone.lower()] = {"rot": rot or [0, 0, 0],
                                  "pos": pos or [0, 0, 0],
                                  "scl": scl}
    return pose


# ---------------------------------------------------------------- geometry

def build_faces(geo: dict, pose: dict | None = None,
                verbose: bool = False) -> list:
    """Return list of (corners3d[4], uv_quad[4]) faces in model space."""
    g = geo["minecraft:geometry"][0]
    desc = g["description"]
    tw, th = desc.get("texture_width", 64), desc.get("texture_height", 64)
    bones = {b["name"]: b for b in g.get("bones", [])}
    pose = pose or {}

    def bone_chain(name):
        chain = []
        b = bones.get(name)
        while b:
            chain.append(b)
            b = bones.get(b.get("parent"))
        return chain  # leaf -> root

    def apply_bones(p, chain):
        for b in chain:
            pr = pose.get(b["name"].lower())
            piv = b.get("pivot", [0, 0, 0])
            if pr and pr.get("scl") is not None:
                s = pr["scl"]
                p = (piv[0] + (p[0] - piv[0]) * s[0],
                     piv[1] + (p[1] - piv[1]) * s[1],
                     piv[2] + (p[2] - piv[2]) * s[2])

            def about_pivot(q, rot, fn):
                if not any(rot):
                    return q
                t = (q[0] - piv[0], q[1] - piv[1], q[2] - piv[2])
                t = fn(t, *rot)
                return (t[0] + piv[0], t[1] + piv[1], t[2] + piv[2])

            # animation rotation composes on top of the bind rotation -
            # applied first (bone-local), each with its own convention
            if pr:
                p = about_pivot(p, pr["rot"], rotate_anim)
            p = about_pivot(p, list(b.get("rotation") or (0, 0, 0)),
                            rotate_zyx)
            if pr and any(pr["pos"]):
                # bedrock animation positions: x runs opposite to geometry x
                p = (p[0] - pr["pos"][0], p[1] + pr["pos"][1],
                     p[2] + pr["pos"][2])
        return p

    all_names = [b["name"].lower() for b in g.get("bones", [])]
    has_closed_wing = any("wing_closed" in n for n in all_names)
    # emotion/state variant decals - the neutral variant stays visible.
    # NOTE: plain "eyelid" bones stay VISIBLE (cyndaquil's squint IS its
    # eyelids); only sleep/mood eyelid variants match these words.
    _MOODS = ("angry", "unamused", "sad_", "_sad", "glare", "happy",
              "recoil", "shocked", "scared", "sleep", "closed_eye",
              "eye_closed", "blink")

    def _eyeish(n: str) -> bool:
        return "eye" in n or "pupil" in n

    # only hide mood-variant eyes if a neutral eye bone actually exists -
    # some models name their ONLY eyes with these words
    has_neutral_eye = any(
        _eyeish(n) and not any(m in n for m in _MOODS) for n in all_names)

    def _bone_off(low: str) -> bool:
        if "hidden" in low:
            return True                 # alternate-pose parts
        if low == "vines" or low.startswith("vine_"):
            return True                 # vine-whip attack props
        if has_closed_wing and "wing_open" in low:
            return True                 # grounded portrait: folded wings
        if any(m in low for m in _MOODS):
            if _eyeish(low) and not has_neutral_eye:
                return False            # would delete the only eyes
            return True                 # emotion-variant face decals
        return False

    def is_hidden(name: str) -> bool:
        """Bones the game doesn't show in a neutral idle portrait."""
        b = bones.get(name)
        while b:
            if _bone_off(b["name"].lower()):
                return True
            b = bones.get(b.get("parent"))
        return False

    faces = []
    for bone in g.get("bones", []):
        if is_hidden(bone["name"]):
            continue
        chain = bone_chain(bone["name"])
        for cube in bone.get("cubes", []) or []:
            ox, oy, oz = cube["origin"]
            sx, sy, sz = cube["size"]
            inf = cube.get("inflate", 0)
            x0, y0, z0 = ox - inf, oy - inf, oz - inf
            x1, y1, z1 = ox + sx + inf, oy + sy + inf, oz + sz + inf
            mirror = cube.get("mirror", False)

            # 8 corners keyed by (xi, yi, zi)
            c = {}
            for xi, x in ((0, x0), (1, x1)):
                for yi, y in ((0, y0), (1, y1)):
                    for zi, z in ((0, z0), (1, z1)):
                        p = (x, y, z)
                        crot = cube.get("rotation")
                        if crot and any(crot):
                            piv = cube.get("pivot", [0, 0, 0])
                            q = (p[0] - piv[0], p[1] - piv[1], p[2] - piv[2])
                            q = rotate_zyx(q, *crot)
                            p = (q[0] + piv[0], q[1] + piv[1], q[2] + piv[2])
                        c[(xi, yi, zi)] = apply_bones(p, chain)

            # face corner order: [top-left, top-right, bottom-right,
            # bottom-left] as seen looking AT the face from outside.
            # Bedrock: -Z = north (the model's front), +X = east ... but
            # texture "east" is the viewer-left side when facing north.
            quads = {
                "north": [c[1, 1, 0], c[0, 1, 0], c[0, 0, 0], c[1, 0, 0]],
                "south": [c[0, 1, 1], c[1, 1, 1], c[1, 0, 1], c[0, 0, 1]],
                "east":  [c[1, 1, 1], c[1, 1, 0], c[1, 0, 0], c[1, 0, 1]],
                "west":  [c[0, 1, 0], c[0, 1, 1], c[0, 0, 1], c[0, 0, 0]],
                "up":    [c[0, 1, 0], c[1, 1, 0], c[1, 1, 1], c[0, 1, 1]],
                "down":  [c[0, 0, 1], c[1, 0, 1], c[1, 0, 0], c[0, 0, 0]],
            }

            uv = cube.get("uv")
            face_uvs = {}
            if isinstance(uv, dict):                      # per-face UV
                for fname, spec in uv.items():
                    if fname not in quads or not isinstance(spec, dict):
                        continue
                    u, v = spec.get("uv", [0, 0])
                    du, dv = spec.get("uv_size", [sx, sy])
                    face_uvs[fname] = (u, v, u + du, v + dv)
            elif isinstance(uv, list):                    # classic box UV
                u, v = uv
                sxi, syi, szi = int(round(sx)), int(round(sy)), int(round(sz))
                # cell order verified against nidoran's one-sided eye plates:
                # the first cell is the WEST face, the third is EAST
                face_uvs = {
                    "west":  (u, v + szi, u + szi, v + szi + syi),
                    "north": (u + szi, v + szi, u + szi + sxi, v + szi + syi),
                    "east":  (u + szi + sxi, v + szi,
                              u + szi + sxi + szi, v + szi + syi),
                    "south": (u + szi + sxi + szi, v + szi,
                              u + szi + sxi + szi + sxi, v + szi + syi),
                    "up":    (u + szi, v, u + szi + sxi, v + szi),
                    "down":  (u + szi + sxi, v + szi, u + szi + sxi + sxi, v),
                }
                if mirror:
                    face_uvs["east"], face_uvs["west"] = (
                        face_uvs["west"], face_uvs["east"])

            cube_faces = []
            for fname, quad in quads.items():
                fuv = face_uvs.get(fname)
                if not fuv:
                    continue
                u0, v0, u1, v1 = fuv
                if u0 == u1 or v0 == v1:
                    continue                                # zero-area UV
                uvq = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
                if isinstance(uv, list) and mirror and fname in (
                        "north", "south", "east", "west", "up", "down"):
                    uvq = [uvq[1], uvq[0], uvq[3], uvq[2]]
                cube_faces.append((quad, uvq))
            if cube_faces:
                corners = list(c.values())
                centroid = tuple(sum(p[i] for p in corners) / len(corners)
                                 for i in range(3))
                d0, d1, d2 = sorted((abs(sx), abs(sy), abs(sz)))
                faces.append({"centroid": centroid, "faces": cube_faces,
                              "volume": d0 * d1 * d2 + 1e-9,
                              "thin": d0 < 0.01, "area": d1 * d2,
                              "bone": bone["name"].lower()})
    if verbose:
        nf = sum(len(cb["faces"]) for cb in faces)
        print(f"  {len(faces)} cubes / {nf} faces, texture {tw}x{th}")
    return faces, tw, th


# ---------------------------------------------------------------- projection

def _persp_coeffs(src, dst):
    """PIL PERSPECTIVE coefficients mapping dst -> src (8 params)."""
    a = []
    b = []
    for (sx, sy), (dx, dy) in zip(src, dst):
        a.append([dx, dy, 1, 0, 0, 0, -sx * dx, -sx * dy])
        a.append([0, 0, 0, dx, dy, 1, -sy * dx, -sy * dy])
        b.append(sx)
        b.append(sy)
    # solve a * coeffs = b  (gaussian elimination, 8x8)
    n = 8
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-9:
            return None
        m[col], m[piv] = m[piv], m[col]
        d = m[col][col]
        m[col] = [x / d for x in m[col]]
        for r in range(n):
            if r != col and m[r][col]:
                f = m[r][col]
                m[r] = [x - f * y for x, y in zip(m[r], m[col])]
    return [m[i][n] for i in range(n)]


def prune_strays(cubes: list) -> list:
    """Drop far-away zero-thickness confetti - attack-prop plates (shadow
    claws, petal trails) the game only shows during moves. Deliberately
    narrow: real geometry like wing membranes has large face area and
    survives; anything with thickness always survives."""
    if len(cubes) <= 8:
        return cubes
    total_v = sum(cb["volume"] for cb in cubes) or 1.0
    cx = sum(cb["centroid"][0] * cb["volume"] for cb in cubes) / total_v
    cy = sum(cb["centroid"][1] * cb["volume"] for cb in cubes) / total_v
    cz = sum(cb["centroid"][2] * cb["volume"] for cb in cubes) / total_v
    dists = [math.dist(cb["centroid"], (cx, cy, cz)) for cb in cubes]
    by_dist = sorted(zip(dists, (cb["volume"] for cb in cubes)))
    acc = 0.0
    r_core = by_dist[-1][0]
    for dc, v in by_dist:
        acc += v
        if acc >= 0.90 * total_v:
            r_core = dc
            break
    # absolute floor: attack-prop trails sit 20-30 units out; body parts
    # (legs, fins, head leaves, antennae) sit within ~15 even on odd bodies
    limit = max(2.0 * r_core, 20.0) + 1e-6
    _FACE = ("eye", "pupil", "mouth", "nose", "muzzle", "ear", "whisker",
             "face", "horn", "tooth", "fang")

    def protected(cb):
        return any(w in cb.get("bone", "") for w in _FACE)

    kept = [cb for cb, dc in zip(cubes, dists)
            if not (dc > limit and cb["thin"] and cb["area"] <= 24
                    and not protected(cb))]
    return kept if kept else cubes


def _view(p):
    return rot_x(rot_y(p, YAW), PITCH)


def _shade(model_quad) -> float:
    """Minecraft-style directional shading from the model-space normal."""
    e1 = tuple(model_quad[1][i] - model_quad[0][i] for i in range(3))
    e2 = tuple(model_quad[3][i] - model_quad[0][i] for i in range(3))
    n = (e1[1] * e2[2] - e1[2] * e2[1],
         e1[2] * e2[0] - e1[0] * e2[2],
         e1[0] * e2[1] - e1[1] * e2[0])
    ax, ay, az = abs(n[0]), abs(n[1]), abs(n[2])
    if ay >= ax and ay >= az:
        return 1.0 if n[1] >= 0 else 0.60       # up / down
    if az >= ax:
        return 0.85                              # north / south
    return 0.70                                  # east / west


def render(cubes, tw, th, texture: Image.Image, size=CANVAS) -> Image.Image:
    """Z-buffer rasterizer: order-independent, so interpenetrating parts and
    touching plates composite correctly."""
    su = texture.width / tw
    sv = texture.height / th
    tex = np.asarray(texture, dtype=np.uint8)
    tex_h, tex_w = tex.shape[0], tex.shape[1]

    faces = []          # (view quad, src uv quad, shade, zbias)
    pts_all = []
    for cube in cubes:
        # SMALL thin plates are decals (eyes, markings) sitting exactly on a
        # surface - bias them slightly toward the camera so they win the
        # coplanar depth fight. Large thin plates (hair sheets, membranes)
        # get no bias, or they'd cover the surfaces they hang next to.
        zbias = (-0.05 if cube.get("thin") and cube.get("area", 99) <= 24
                 else 0.0)
        for quad, uvq in cube["faces"]:
            vpts = [_view(p) for p in quad]
            faces.append((vpts, uvq, _shade(quad), zbias))
            pts_all.extend(vpts)
    if not pts_all:
        return Image.new("RGBA", (size, size), (0, 0, 0, 0))
    xs = [p[0] for p in pts_all]
    ys = [p[1] for p in pts_all]
    scale = (size * 0.92) / max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
    offx = -(min(xs) + max(xs)) / 2 * scale + size / 2
    offy = (min(ys) + max(ys)) / 2 * scale + size / 2

    color = np.zeros((size, size, 4), dtype=np.uint8)
    zbuf = np.full((size, size), np.inf, dtype=np.float64)

    # pass 1: opaque texels with depth test; pass 2: translucent texels
    # blended far-to-near over the opaque result (ghost bodies, cores...)
    schedule = [(False, f) for f in faces] + \
               [(True, f) for f in sorted(
                   faces, key=lambda f: sum(p[2] for p in f[0]) / 4,
                   reverse=True)]
    for translucent_pass, (vpts, uvq, shade, zbias) in schedule:
        scr = np.array([(p[0] * scale + offx, -p[1] * scale + offy)
                        for p in vpts])
        zs = np.array([p[2] for p in vpts])
        minx = max(0, int(scr[:, 0].min()) - 1)
        miny = max(0, int(scr[:, 1].min()) - 1)
        maxx = min(size, int(scr[:, 0].max()) + 2)
        maxy = min(size, int(scr[:, 1].max()) + 2)
        if maxx - minx < 1 or maxy - miny < 1:
            continue
        gy, gx = np.mgrid[miny:maxy, minx:maxx]
        px = gx + 0.5
        py = gy + 0.5

        # inside test + interpolation via the two triangles of the quad
        inside = np.zeros(px.shape, dtype=bool)
        u_val = np.zeros(px.shape)
        v_val = np.zeros(px.shape)
        z_val = np.zeros(px.shape)
        src = np.array([(u * su, v * sv) for u, v in uvq])
        # inset UVs toward face centre ~1/3 texel against atlas bleed
        cuv = src.mean(axis=0)
        src = src + np.clip(cuv - src, [-0.35 * su, -0.35 * sv],
                            [0.35 * su, 0.35 * sv])
        for tri in ((0, 1, 2), (0, 2, 3)):
            a, b, c = (scr[i] for i in tri)
            det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(det) < 1e-9:
                continue
            w0 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / det
            w1 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / det
            w2 = 1.0 - w0 - w1
            m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6) & ~inside
            if not m.any():
                continue
            ua, va = src[tri[0]]
            ub, vb = src[tri[1]]
            uc, vc = src[tri[2]]
            u_val[m] = (w0 * ua + w1 * ub + w2 * uc)[m]
            v_val[m] = (w0 * va + w1 * vb + w2 * vc)[m]
            z_val[m] = (w0 * zs[tri[0]] + w1 * zs[tri[1]] + w2 * zs[tri[2]])[m]
            inside |= m
        if not inside.any():
            continue
        if zbias:
            z_val = z_val + zbias

        ui = np.clip(u_val.astype(np.int64), 0, tex_w - 1)
        vi = np.clip(v_val.astype(np.int64), 0, tex_h - 1)
        texel = tex[vi, ui]                       # (h, w, 4)
        zslice = zbuf[miny:maxy, minx:maxx]
        cslice = color[miny:maxy, minx:maxx]
        if translucent_pass:
            # blend semi-transparent texels over what's already drawn,
            # respecting opaque depth; faces arrive far-to-near
            a8 = texel[..., 3]
            win = inside & (a8 > 8) & (a8 < 250) & (z_val <= zslice + 1e-6)
            if not win.any():
                continue
            af = (a8[win].astype(np.float64) / 255.0)[..., None]
            src_rgb = texel[win, :3].astype(np.float64) * shade
            dst = cslice[win].astype(np.float64)
            out_rgb = src_rgb * af + dst[:, :3] * (1 - af)
            out_a = np.maximum(dst[:, 3:4], af * 255.0)
            cslice[win] = np.concatenate([out_rgb, out_a],
                                         axis=1).astype(np.uint8)
        else:
            opaque = texel[..., 3] >= 250
            # camera looks along -z: smaller view z is nearer. Ties go to the
            # later-drawn face (later bones = decals like eyes over the head)
            win = inside & opaque & (z_val <= zslice + 1e-7)
            if not win.any():
                continue
            shaded = texel.astype(np.float64)
            shaded[..., :3] *= shade
            cslice[win] = shaded[win].astype(np.uint8)
            zslice[win] = z_val[win]

    return Image.fromarray(color, "RGBA")


def _old_render(cubes, tw, th, texture: Image.Image, size=CANVAS) -> Image.Image:
    # scale texture UVs if the actual texture resolution differs
    su = texture.width / tw
    sv = texture.height / th

    # project everything into view space: view = pitch * yaw
    proj = []
    for cube in cubes:
        pfaces = [([_view(p) for p in quad], uvq)
                  for quad, uvq in cube["faces"]]
        proj.append({"centroid": _view(cube["centroid"]), "faces": pfaces})

    pts_all = [p for cb in proj for pts, _ in cb["faces"] for p in pts]
    if not pts_all:
        return Image.new("RGBA", (size, size), (0, 0, 0, 0))
    xs = [p[0] for p in pts_all]
    ys = [p[1] for p in pts_all]
    scale = (size * 0.92) / max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
    offx = -(min(xs) + max(xs)) / 2 * scale + size / 2
    offy = (min(ys) + max(ys)) / 2 * scale + size / 2

    def to_screen(p):
        return (p[0] * scale + offx, -p[1] * scale + offy)

    # cube-level painter's algorithm: camera looks along -Z (higher view z
    # is farther), so draw cubes far-to-near. Within a cube, cull the faces
    # whose OUTWARD normal points away from the camera - computed
    # geometrically against the cube centroid, so mirrored/negative-size
    # cubes can't flip it. This removes interior faces entirely, which is
    # what caused the "shredded" look on models made of touching plates.
    order = sorted(proj, key=lambda cb: cb["centroid"][2], reverse=True)

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for cb in order:
        cc = cb["centroid"]
        vis = []
        for pts, uvq in cb["faces"]:
            fc = tuple(sum(p[i] for p in pts) / 4 for i in range(3))
            e1 = tuple(pts[1][i] - pts[0][i] for i in range(3))
            e2 = tuple(pts[3][i] - pts[0][i] for i in range(3))
            n = (e1[1] * e2[2] - e1[2] * e2[1],
                 e1[2] * e2[0] - e1[0] * e2[2],
                 e1[0] * e2[1] - e1[1] * e2[0])
            out = tuple(fc[i] - cc[i] for i in range(3))
            if sum(n[i] * out[i] for i in range(3)) < 0:
                n = (-n[0], -n[1], -n[2])
            flat = all(abs(o) < 1e-6 for o in out)
            # camera direction is -z: visible when outward normal has z < 0
            if flat or n[2] < 1e-9:
                vis.append((fc[2], pts, uvq))
        vis.sort(key=lambda f: f[0], reverse=True)
        for _, pts, uvq in vis:
            scr = [to_screen(p) for p in pts]
            minx = max(0, int(min(p[0] for p in scr)) - 1)
            miny = max(0, int(min(p[1] for p in scr)) - 1)
            maxx = min(size, int(max(p[0] for p in scr)) + 2)
            maxy = min(size, int(max(p[1] for p in scr)) + 2)
            if maxx - minx < 1 or maxy - miny < 1:
                continue
            local = [(x - minx, y - miny) for x, y in scr]
            # inset UVs toward the face centre by ~a third of a texel so the
            # warp never samples the neighbouring atlas region (colour bleed)
            cu = sum(u for u, v in uvq) / 4 * su
            cv = sum(v for u, v in uvq) / 4 * sv
            eps_u, eps_v = 0.35 * su, 0.35 * sv
            src = []
            for u, v in uvq:
                x = u * su
                y = v * sv
                x += max(-eps_u, min(eps_u, cu - x))
                y += max(-eps_v, min(eps_v, cv - y))
                src.append((x, y))
            coeffs = _persp_coeffs(src, local)
            if not coeffs:
                continue
            patch = texture.transform((maxx - minx, maxy - miny),
                                      Image.Transform.PERSPECTIVE, coeffs,
                                      resample=Image.Resampling.NEAREST)
            canvas.alpha_composite(patch, (minx, miny))
    return canvas


# ---------------------------------------------------------------- discovery

_MODEL_RE = re.compile(r"assets/[^/]+/bedrock/pokemon/models/"
                       r"(?:[^/]+/)*?(\d+)_([^/]+)/([^/]+)\.geo\.json$")


def norm_species(name: str) -> str:
    return (name.lower().replace("_", "").replace("-", "").replace(" ", "")
            .replace(".", "").replace("'", ""))


# path inside any scanned archive -> the archive that provides it (first
# scanned wins). Lets split resource packs (model in one zip, textures in
# another) resolve cross-archive.
ASSET_JARS: dict[str, str] = {}
_ZIPS: dict[str, zipfile.ZipFile] = {}


def _zip(jar: str) -> zipfile.ZipFile:
    if jar not in _ZIPS:
        _ZIPS[jar] = zipfile.ZipFile(jar)
    return _ZIPS[jar]


def read_asset(path: str, prefer_jar: str | None = None) -> bytes | None:
    """Read an assets/ path from whichever scanned archive provides it."""
    if not path:
        return None
    for jar in ([prefer_jar] if prefer_jar else []) + \
               ([ASSET_JARS[path]] if path in ASSET_JARS else []):
        try:
            return _zip(jar).read(path)
        except (KeyError, zipfile.BadZipFile, FileNotFoundError):
            continue
    return None


def discover(jars: list[str]):
    """species id -> dict(geo/tex/shiny/anim/poser/resolvers paths).
    Asset lists aggregate across ALL archives (split resource packs put the
    model and its textures in different zips); scan order sets priority."""
    found: dict[str, dict] = {}
    models: dict[str, list] = {}
    texdirs: dict[str, list] = {}
    animdirs: dict[str, list] = {}
    poserdirs: dict[str, list] = {}
    resolverdirs: dict[str, list] = {}
    for jar in jars:
        try:
            zf = zipfile.ZipFile(jar)
        except zipfile.BadZipFile:
            continue
        names = zf.namelist()
        for n in names:
            if n.startswith("assets/") and (n.endswith(".png")
                                            or n.endswith(".json")):
                ASSET_JARS.setdefault(n, jar)
            if m := _MODEL_RE.match(n):
                if n.startswith("assets/") or "/assets/" not in n:
                    models.setdefault(norm_species(m.group(2)), []).append(
                        (m.group(3), n))
            if "/textures/pokemon/" in n and n.endswith(".png"):
                m2 = re.search(r"/textures/pokemon/(?:[^/]+/)*?\d+_([^/]+)/", n)
                if m2:
                    texdirs.setdefault(norm_species(m2.group(1)), []).append(n)
            if "/pokemon/animations/" in n and n.endswith(".animation.json"):
                m3 = re.search(r"/pokemon/animations/(?:[^/]+/)*?\d+_([^/]+)/", n)
                if m3:
                    animdirs.setdefault(norm_species(m3.group(1)), []).append(n)
            if "/pokemon/posers/" in n and n.endswith(".json"):
                m4 = re.search(r"/pokemon/posers/(?:[^/]+/)*?\d+_([^/]+)/", n)
                if m4:
                    poserdirs.setdefault(norm_species(m4.group(1)), []).append(n)
            if "/pokemon/resolvers/" in n and n.endswith(".json"):
                m5 = re.search(r"/pokemon/resolvers/(?:[^/]+/)*?\d+_([^/]+)/", n)
                if m5:
                    resolverdirs.setdefault(norm_species(m5.group(1)), []).append(n)
    for sp, cand in models.items():
        if True:
            base = sp
            texs = texdirs.get(sp, [])
            tex_jars = {ASSET_JARS.get(t) for t in texs}

            # prefer exact species geo, then male, then shortest name; and
            # prefer archives that also carry this species' textures (split
            # RP combos can otherwise pair a model with a mismatched skin)
            def rank(item):
                stem = norm_species(item[0])
                jar_ok = 0 if ASSET_JARS.get(item[1]) in tex_jars else 1
                if stem == base:
                    return (jar_ok, 0, len(item[0]))
                if stem == base + "male":
                    return (jar_ok, 1, len(item[0]))
                if "bias" in stem or "cosmetic" in stem:
                    return (jar_ok, 3, len(item[0]))
                return (jar_ok, 2, len(item[0]))
            cand.sort(key=rank)
            geo_path = cand[0][1]

            def pick_tex(shiny: bool):
                pool = [t for t in texs
                        if t.endswith("_shiny.png") == shiny
                        and "_emissive" not in t and "flame" not in t
                        and "sleep" not in t and "eye" not in t]
                if not pool:
                    return None
                stem = norm_species(os.path.basename(cand[0][1])
                                    .replace(".geo.json", ""))
                def trank(t):
                    tn = norm_species(os.path.basename(t)[:-4]
                                      .replace("shiny", ""))
                    if tn == base:
                        return (0, len(t))
                    if tn == stem:
                        return (1, len(t))
                    if tn == base + "male":
                        return (2, len(t))
                    return (3, len(t))
                pool.sort(key=trank)
                return pool[0]

            anims = animdirs.get(sp, [])
            geo_stem = norm_species(os.path.basename(geo_path)
                                    .replace(".geo.json", ""))
            anims.sort(key=lambda a: (
                0 if norm_species(os.path.basename(a)
                                  .replace(".animation.json", "")) in
                (sp, geo_stem) else 1, len(a)))
            posers = poserdirs.get(sp, [])
            posers.sort(key=lambda a: (
                0 if norm_species(os.path.basename(a)[:-5]) in (sp, geo_stem)
                else 1, len(a)))
            found[sp] = {"jar": ASSET_JARS.get(geo_path), "geo": geo_path,
                         "tex": pick_tex(False), "shiny": pick_tex(True),
                         "anim": anims[0] if anims else None,
                         "poser": posers[0] if posers else None,
                         "resolvers": sorted(resolverdirs.get(sp, []))}
    return found


def _rl_path(ref) -> str | None:
    """cobblemon:textures/pokemon/x.png -> assets/cobblemon/textures/pokemon/x.png
    Animated frame-list textures ({"frames": [...], "fps": n}) use frame 1."""
    if isinstance(ref, dict):
        frames = ref.get("frames")
        ref = frames[0] if isinstance(frames, list) and frames else None
    if not isinstance(ref, str) or ":" not in ref:
        return None
    ns, path = ref.split(":", 1)
    return f"assets/{ns}/{path}"


def load_texture_stack(entry: dict, shiny: bool) -> Image.Image | None:
    """Base texture + composited layers, as defined by the species resolver
    (the game's own texture selection). Falls back to name-based picking.
    All reads go through the cross-archive asset index."""
    base_tex = base_layers = shiny_tex = shiny_layers = None
    for rp in entry.get("resolvers", []):
        blob = read_asset(rp, entry.get("jar"))
        if blob is None:
            continue
        try:
            res = json.loads(blob.decode("utf-8-sig"))
        except Exception:
            continue
        for var in res.get("variations", []) or []:
            aspects = [str(a).lower() for a in (var.get("aspects") or [])]
            if not aspects:
                base_tex = var.get("texture") or base_tex
                if var.get("layers") is not None:
                    base_layers = var["layers"]
            elif aspects == ["shiny"]:
                shiny_tex = var.get("texture") or shiny_tex
                if var.get("layers") is not None:
                    shiny_layers = var["layers"]
    if shiny:
        base_ref = shiny_tex or base_tex
        layers = shiny_layers if shiny_layers is not None else base_layers
        if shiny_tex is None and shiny_layers is None:
            base_ref = None      # no shiny assets in resolver - use fallback
    else:
        base_ref, layers = base_tex, base_layers

    def read_img(path):
        blob = read_asset(path, entry.get("jar")) if path else None
        if blob is None:
            return None
        try:
            return Image.open(io.BytesIO(blob)).convert("RGBA")
        except Exception:
            return None

    img = read_img(_rl_path(base_ref))
    if img is None:
        img = read_img(entry["shiny"] if shiny else entry["tex"])
        if img is None and shiny:
            return None
    if img is None:
        return None
    for layer in layers or []:
        if not isinstance(layer, dict):
            continue
        lay = read_img(_rl_path(layer.get("texture")))
        if lay is None:
            continue
        if lay.size != img.size:
            lay = lay.resize(img.size, Image.Resampling.NEAREST)
        img = img.copy()
        if layer.get("translucent"):
            # the game renders these layers semi-transparent regardless of
            # texture alpha (spiritomb ghost, gastly gas) - cap the LAYER's
            # alpha only. Where the base is already opaque (slugma's lava
            # body) the result stays opaque with the layer tinted on top.
            r, g, b, a = lay.split()
            lay = Image.merge("RGBA", (r, g, b, a.point(lambda v: min(v, 140))))
        img.alpha_composite(lay)
    return img


# ---------------------------------------------------------------- main

def render_one(entry: dict, out_path: str, shiny: bool,
               verbose: bool = False) -> str:
    try:
        blob = read_asset(entry["geo"], entry.get("jar"))
        if blob is None:
            return "error (geo unreadable)"
        geo = json.loads(blob.decode("utf-8-sig"))
        texture = load_texture_stack(entry, shiny)
        if texture is None:
            return "no-texture"
        wanted = portrait_anims(entry.get("poser"), entry.get("jar"))
        pose = (load_pose(entry["anim"], wanted, entry.get("jar"))
                if entry.get("anim") else {})
        cubes, tw, th = build_faces(geo, pose, verbose)
        cubes = prune_strays(cubes)
        img = render(cubes, tw, th, texture)
        # autocrop to content and pad square so every portrait frames alike
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        side = max(img.width, img.height)
        pad = int(side * 0.06)
        square = Image.new("RGBA", (side + 2 * pad,) * 2, (0, 0, 0, 0))
        square.alpha_composite(img, (pad + (side - img.width) // 2,
                                     pad + (side - img.height) // 2))
        square = square.resize((FINAL, FINAL), Image.Resampling.LANCZOS)
        square.save(out_path)
        return "ok"
    except Exception as e:
        return f"error ({type(e).__name__}: {e})" if verbose else \
            f"error ({type(e).__name__})"


def main() -> None:
    only = norm_species(sys.argv[1]) if len(sys.argv) > 1 else None

    with open(os.path.join(ROOT, "data", "wikidata.json"),
              encoding="utf-8") as fh:
        species = set(json.load(fh)["species"].keys())

    mods_dir = os.path.join(PACK, "mods")
    jars = [os.path.join(mods_dir, f) for f in sorted(os.listdir(mods_dir))
            if f.endswith(".jar")]
    # Cobblemon first so its models win; content mods after
    jars.sort(key=lambda j: 0 if "Cobblemon-fabric" in j else 1)
    # model resource packs (ATMxMSD, MissingMons...) fill species the mods
    # don't model; scanned last so they never override mod models
    rp_dir = os.path.join(PACK, "resourcepacks")
    if os.path.isdir(rp_dir):
        jars += [os.path.join(rp_dir, f) for f in sorted(os.listdir(rp_dir))
                 if f.endswith(".zip") and not f.lower().startswith("z do not")]

    print("scanning jars for models...")
    found = discover(jars)
    targets = sorted(species & set(found.keys()))
    missing = sorted(species - set(found.keys()))
    print(f"{len(targets)} species have models; {len(missing)} without "
          f"(first few: {missing[:8]})")

    os.makedirs(os.path.join(OUT, "shiny"), exist_ok=True)
    ok = skip = err = 0
    todo = [s for s in targets if s == only] if only else targets
    for i, sp in enumerate(todo, 1):
        for shiny in (False, True):
            out_path = os.path.join(OUT, "shiny" if shiny else "", f"{sp}.png")
            if os.path.exists(out_path) and not only:
                skip += 1
                continue
            status = render_one(found[sp], out_path, shiny, verbose=bool(only))
            if status == "ok":
                ok += 1
            elif status == "no-texture":
                skip += 1
            else:
                err += 1
                if err <= 20 or only:
                    print(f"  {sp}{' shiny' if shiny else ''}: {status}")
        if i % 100 == 0:
            print(f"  ... {i}/{len(todo)}")
    print(f"done: {ok} rendered, {skip} skipped, {err} errors")


if __name__ == "__main__":
    main()
