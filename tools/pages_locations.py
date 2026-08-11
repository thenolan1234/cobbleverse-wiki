"""Locations page: interior guides for the pack's dungeon structures
(Team Rocket/Galactic buildings, Radio Tower, Wishing Weald...)."""

from __future__ import annotations

import os

from templates import page, esc

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

_CSS = """
<style>
.locimg{max-width:100%;border:1px solid var(--reef);border-radius:8px}
.locmeta{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:6px 0}
table.loctr{border-collapse:collapse;font-size:13px;margin:10px 0}
table.loctr td,table.loctr th{padding:4px 10px;border:1px solid var(--reef)}
.locsec{max-width:960px;margin:0 auto 34px auto}
.locbox{border:1px solid var(--reef);border-radius:8px;padding:10px 14px;
  margin:10px 0;background:var(--deep)}
</style>"""


def _trainer_rows(trainers: list) -> str:
    rows = []
    for t in trainers:
        link = (f"<a href='trainers.html#{esc(t['id'])}'>{esc(t['name'])}</a>"
                if t.get("id") else esc(t.get("name", "?")))
        rows.append(f"<tr><td>{link}</td>"
                    f"<td style='text-align:right'>{t.get('level', '?')}</td>"
                    f"<td>{t.get('note', '')}</td></tr>")
    return "".join(rows)


def build_locations(content: dict, d: dict) -> str:
    parts = [_CSS, '<div class="padbox locsec"><h1>Location Guides</h1>',
             content.get("intro", ""), "</div>"]
    for loc in content.get("locations", []):
        slug = loc["slug"]
        struct = loc.get("structSlug", "")
        img_path = os.path.join(ROOT, "renders", "structures",
                                f"{struct}.png")
        img = ""
        if struct and os.path.exists(img_path):
            img = (f'<p><a href="viewer.html?s={esc(struct)}" '
                   f'title="Open in 3D viewer">'
                   f'<img class="locimg" src="renders/structures/'
                   f'{esc(struct)}.png" loading="lazy" alt="{esc(loc["name"])}">'
                   f'</a><br><span class="meta">click to explore in 3D '
                   f'(slice the roof off to see the rooms)</span></p>')
        trainers = ""
        if loc.get("trainers"):
            trainers = (
                "<h3>Trainers inside</h3><table class='loctr'>"
                "<thead><tr><th>trainer</th><th>level</th><th>notes</th>"
                "</tr></thead><tbody>"
                + _trainer_rows(loc["trainers"]) + "</tbody></table>")
        parts.append(f"""
<div class="padbox locsec" id="{esc(slug)}">
  <h2>{esc(loc['name'])}</h2>
  <div class="locmeta">
    <span class="chip">{esc(loc.get('region', ''))}</span>
    <span class="chip">recommended level {esc(str(loc.get('recommendedLevel', 'any')))}</span>
  </div>
  {loc.get('overview', '')}
  {img}
  <div class="locbox"><b>Finding it:</b> {loc.get('locate', '')}</div>
  {trainers}
  <h3>Loot &amp; collectibles</h3>
  {loc.get('loot', '')}
  <h3>Walkthrough</h3>
  {loc.get('walkthrough', '')}
</div>""")
    return page("Locations", "locations.html", "".join(parts))
