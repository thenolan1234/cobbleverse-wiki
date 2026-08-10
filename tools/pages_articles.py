"""Article-style pages: home, progression, legendaries, mods, generic guides."""

from __future__ import annotations

import re

from templates import page, esc, icon_img, slugify

_SCRIPT_RE = re.compile(r"<\s*/?\s*script[^>]*>", re.I)
_EVENT_RE = re.compile(r"\son\w+\s*=", re.I)


def _safe(body: str) -> str:
    """Guide bodies come from generation agents - allow simple HTML only."""
    body = _SCRIPT_RE.sub("", body or "")
    body = _EVENT_RE.sub(" data-x=", body)
    return body


def _sections_html(content: dict) -> str:
    out = []
    for s in content.get("sections", []):
        out.append(f"<section><h2 id='{slugify(s.get('heading', ''))}'>"
                   f"{esc(s.get('heading'))}</h2>"
                   f"{_safe(s.get('body', ''))}</section>")
    return "".join(out)


PENDING = ("<div class='callout warn'>This guide hasn't been generated yet. "
           "Re-run <code>tools/build_site.py</code> after the content step.</div>")


def build_guide(slug: str, fallback_title: str, content: dict | None,
                subtitle: str = "") -> str:
    if not content:
        body = (f"<div class='article'><h1>{esc(fallback_title)}</h1>"
                f"<p class='sub'>{esc(subtitle)}</p>{PENDING}</div>")
        return page(fallback_title, slug, body)
    body = f"""<div class="article">
<h1>{esc(content.get('title') or fallback_title)}</h1>
<p class="sub">{esc(subtitle)}</p>
{_safe(content.get('intro', ''))}
{_sections_html(content)}
</div>"""
    return page(content.get("title") or fallback_title, slug, body)


# ---------------------------------------------------------------- progression

_KIND_LABEL = {"badge": "badge", "elite": "elite four", "champion": "champion",
               "legendary": "legendary", "item": "key item", "other": ""}


def build_progression(content: dict | None, names: dict) -> str:
    if not content:
        return build_guide("progression.html", "Progression", None,
                           "Badges, regions and the road to champion")
    parts = [f"<h1>{esc(content.get('title') or 'Progression')}</h1>",
             '<p class="sub">Badges, regions and the road to champion — '
             'reconstructed from the pack’s advancement and trainer data</p>',
             _safe(content.get("intro", ""))]
    if content.get("levelCapNote"):
        parts.append(f"<div class='callout'>{_safe(content['levelCapNote'])}</div>")
    for region in content.get("regions", []):
        parts.append(f"<section><h2 id='{slugify(region.get('title', ''))}'>"
                     f"{esc(region.get('title'))}</h2>")
        if region.get("note"):
            parts.append(_safe(region["note"]))
        for m in region.get("milestones", []):
            kind = m.get("kind", "other")
            klabel = _KIND_LABEL.get(kind, kind)
            kindchip = (f"<span class='kind {kind}-k'>{esc(klabel)}</span>"
                        if klabel else "<span class='kind'>step</span>")
            icon = m.get("icon")
            iconname = names.get(icon) if icon else None
            title = esc(m.get("title"))
            if m.get("trainerId"):
                title = (f"<a href='trainers.html#{esc(m['trainerId'])}'>"
                         f"{title}</a>")
            ico = ""
            if icon:
                label = esc(iconname or icon.split(":")[-1].replace("_", " ").title())
                ico = (f" <a class='ico' href='items.html#{esc(icon)}'>"
                       f"{icon_img(icon, 18)} {label}</a>")
            parts.append(f"""<div class="mile">{kindchip}
  <div><h4>{title}{ico}</h4><p>{esc(m.get('desc'))}</p></div></div>""")
        parts.append("</section>")
    body = "<div class='article'>" + "".join(parts) + "</div>"
    return page("Progression", "progression.html", body)


# ---------------------------------------------------------------- legendaries

def build_legendaries(content: dict | None, species: dict) -> str:
    if not content:
        return build_guide("legendaries.html", "Legendaries", None,
                           "How every legendary is obtained in this pack")
    parts = ["<h1>Legendaries</h1>",
             "<p class='sub'>How every legendary and mythical is actually "
             "obtained in COBBLEVERSE</p>",
             _safe(content.get("intro", ""))]
    for leg in content.get("legendaries", []):
        name = leg.get("name", "?")
        sp = leg.get("species")
        title = esc(name)
        if sp and sp in species:
            title = f"<a href='pokedex.html#{esc(sp)}'>{title}</a>"
        parts.append(f"<section><h2 id='{slugify(name)}'>{title}</h2>"
                     f"{_safe(leg.get('method', ''))}")
        items = leg.get("keyItems") or []
        if items:
            chips = " ".join(
                f"<a class='chip' href='items.html#{esc(i)}'>"
                f"{esc(i.split(':')[-1].replace('_', ' ').title())}</a>"
                for i in items)
            parts.append(f"<p>Key items: {chips}</p>")
        parts.append("</section>")
    parts.append(_sections_html(content))    # appended guide sections, if any
    body = "<div class='article'>" + "".join(parts) + "</div>"
    return page("Legendaries", "legendaries.html", body)


# ---------------------------------------------------------------- mods

def build_mods(content: dict | None) -> str:
    if not content:
        return build_guide("mods.html", "Mod List", None, "Every mod in the pack")
    parts = ["<h1>Mod List</h1>",
             "<p class='sub'>Every mod in the pack, grouped by what it does "
             "for you</p>",
             _safe(content.get("intro", ""))]
    for cat in content.get("categories", []):
        parts.append(f"<section><h2>{esc(cat.get('name'))}</h2>"
                     "<table class='data'><tr><th>Mod</th><th>What it does</th></tr>")
        for m in cat.get("mods", []):
            parts.append(f"<tr><td><b>{esc(m.get('name'))}</b>"
                         f"<div class='meta'>{esc(m.get('file'))}</div></td>"
                         f"<td>{esc(m.get('summary'))}</td></tr>")
        parts.append("</table></section>")
    body = "<div class='article'>" + "".join(parts) + "</div>"
    return page("Mods", "mods.html", body)


# ---------------------------------------------------------------- videos

_KIND_LABEL = {"video": "video", "channel": "channel",
               "playlist": "playlist", "website": "website"}


def build_videos(content: dict | None) -> str:
    if not content:
        return build_guide("videos.html", "Community Guides", None,
                           "Video guides, creators and tools from the community")
    parts = ["<h1>Community Guides</h1>",
             "<p class='sub'>Video guides, creators and tools from the "
             "community — the one page of this wiki that links to the "
             "internet</p>",
             _safe(content.get("intro", ""))]
    for sec in content.get("sections", []):
        parts.append(f"<section><h2 id='{slugify(sec.get('heading', ''))}'>"
                     f"{esc(sec.get('heading'))}</h2>")
        if sec.get("note"):
            parts.append(f"<p class='meta'>{esc(sec['note'])}</p>")
        parts.append("<div class='cards'>")
        for e in sec.get("entries", []):
            kind = _KIND_LABEL.get(e.get("kind", ""), "")
            topics = " · ".join(e.get("topics", [])[:4])
            meta_bits = [b for b in (e.get("creator"), kind, topics) if b]
            parts.append(
                f"<a class='card' href='{esc(e.get('url'))}' target='_blank' "
                f"rel='noopener'>"
                f"<h3>{esc(e.get('title'))}</h3>"
                f"<p><b style='color:var(--foam)'>{esc(' · '.join(meta_bits[:2]))}</b>"
                f"{(' — ' + esc(topics)) if topics else ''}</p>"
                f"<p>{esc(e.get('note', ''))}</p></a>")
        parts.append("</div></section>")
    parts.append("<div class='callout'>Links were verified when this page was "
                 "generated, but videos and channels move — if one dies, search "
                 "the title on YouTube. Nothing on this page is affiliated with "
                 "the wiki.</div>")
    body = "<div class='article'>" + "".join(parts) + "</div>"
    return page("Community Guides", "videos.html", body)


# ---------------------------------------------------------------- structures

_STRUCT_CATS = [
    ("Legendary monuments", lambda e: e["ns"] == "legendarymonuments"
        or "legendary/" in e["rel"] or e["slug"] in
        ("newmoon-island", "temple-of-sinnoh", "crown-spire")),
    ("Leagues & gyms", lambda e: any(w in e["rel"] for w in
        ("league", "gym", "elite"))),
    ("Raid dens", lambda e: e["ns"] == "cobblemonraiddens"),
    ("Caves & coves", lambda e: "cove" in e["slug"] or "cave" in e["slug"]),
    ("Ruins & fossil sites", lambda e: e["rel"].startswith(("ruins/",
                                                            "fossils/"))),
    ("Towns, centers & villages", lambda e: e["ns"] in ("bca", "cobblemon")
        or "center" in e["rel"] or "village" in e["rel"]),
    ("Other structures", lambda e: True),
]


_GYMS = {"brock", "misty", "ltsurge", "erika", "koga", "sabrina", "blaine",
         "giovanni"}
_STRUCT_GUIDE = {
    "stark-mountain": "legendaries.html#heatran",
    "eternatus-cocoon": "legendaries.html#eternatus",
    "firescourge-shrine": "legendaries.html#treasures-of-ruin",
    "grasswither-shrine": "legendaries.html#treasures-of-ruin",
    "groundblight-shrine": "legendaries.html#treasures-of-ruin",
    "icerend-shrine": "legendaries.html#treasures-of-ruin",
    "giratina-island": "legendaries.html#giratina",
    "turnback-cave-example": "legendaries.html#giratina",
    "newmoon-island": "legendaries.html#darkrai",
    "temple-of-sinnoh": "legendaries.html#arceus",
    "crown-spire": "legendaries.html#calyrex-glastrier-spectrier",
    "crown-cemetery": "legendaries.html#calyrex-glastrier-spectrier",
    "dawn-tower": "legendaries.html#necrozma",
    "dusk-tower": "legendaries.html#necrozma",
    "lake-guardians-lake-acuity": "legendaries.html#uxie-mesprit-azelf",
    "lake-guardians-lake-valor": "legendaries.html#uxie-mesprit-azelf",
    "lake-guardians-lake-verity": "legendaries.html#uxie-mesprit-azelf",
    "team-rocket-tower": "legendaries.html#mewtwo",
    "team-rocket-tower-shiny": "legendaries.html#mewtwo",
    "mythical-mew": "legendaries.html#mew",
    "ash": "legendaries.html#finding-kanto-legendary-structures",
    "kanto-league": "progression.html#gen-1-kanto",
    "mega-site": "mechanics.html#mega-evolution-mega-showdown",
    "megaroid": "mechanics.html#mega-evolution-mega-showdown",
}


def _guide_url(e, leg_anchors):
    slug = e["slug"]
    if slug in _STRUCT_GUIDE:
        return _STRUCT_GUIDE[slug]
    base = slug.replace("-shiny", "")
    if base in _GYMS:
        return f"trainers.html#kanto_{base}"
    toks = slug.split("-")
    for tok in toks:
        if tok in leg_anchors:
            return f"legendaries.html#{tok}"
    for anchor in leg_anchors:
        if any(tok in anchor.split("-") for tok in toks if len(tok) > 3):
            return f"legendaries.html#{anchor}"
    if "raid" in slug:
        return "mechanics.html#raid-dens"
    if slug.startswith("fossils"):
        return "mechanics.html#fossils-and-resurrection"
    if "fishing" in slug:
        return "mechanics.html#fishing-with-pok-rods"
    if "cove" in slug or slug.startswith("ruins"):
        return "world.html"
    if any(w in slug for w in ("village", "center", "pokecenter", "store",
                               "market", "lodge", "pokemart")) \
            or e["ns"] == "bca":
        return "world.html"
    return None


def build_structures(inv: list, have: set, species: dict,
                     legendaries: dict | None = None) -> str:
    leg_anchors = {slugify(l["name"]) for l in
                   (legendaries or {}).get("legendaries", []) if l.get("name")}
    cats: dict[str, list] = {}
    for e in inv:
        if e["slug"] not in have:
            continue
        for cname, pred in _STRUCT_CATS:
            if pred(e):
                cats.setdefault(cname, []).append(e)
                break
    parts = ["<h1>Structures</h1>",
             "<p class='sub'>Isometric renders of the structures that "
             "generate in this pack, built block-for-block from the pack's "
             "own structure files — know what you're looking for before you "
             "go hunting.</p>"]
    for cname, _ in _STRUCT_CATS:
        entries = cats.get(cname)
        if not entries:
            continue
        entries.sort(key=lambda e: -e["size"])
        parts.append(f"<section><h2 id='{slugify(cname)}'>{esc(cname)}</h2>"
                     "<div class='structgrid'>")
        for e in entries:
            name = e["rel"].split("/")[-1].replace("_", " ").replace("-", " ").title()
            links = ""
            for cand in ([e["slug"].replace("-", "")] +
                         e["slug"].split("-")):
                if cand in species:
                    links = (f" · <a href='spawns.html#{esc(cand)}'>spawns</a>"
                             f" · <a href='pokedex.html#{esc(cand)}'>dex</a>")
                    break
            full = f"renders/structures/{esc(e['slug'])}.png"
            guide = _guide_url(e, leg_anchors)
            click = esc(guide) if guide else full
            target = "" if guide else " target='_blank' rel='noopener'"
            glink = (f" · <a href='{esc(guide)}'>guide</a>" if guide else "")
            parts.append(
                f"<figure><a href='{click}'{target}>"
                f"<img src='{full}' loading='lazy' alt='{esc(name)}'></a>"
                f"<figcaption><b>{esc(name)}</b>"
                f"<span class='meta'> · {esc(e['ns'])}{glink}{links}"
                f" · <a href='{full}' target='_blank' rel='noopener'>full "
                f"size</a></span></figcaption></figure>")
        parts.append("</div></section>")
    parts.append("<div class='callout'>Renders show every block in the "
                 "structure files with hidden faces removed — multi-piece "
                 "structures like Giratina Island are stitched from their "
                 "grid pieces. In-world generation adds terrain around what "
                 "you see here. Click any render for full size.</div>")
    body = "<div class='article' style='max-width:1180px'>" + "".join(parts) + "</div>"
    return page("Structures", "structures.html", body)


# ---------------------------------------------------------------- home

def build_home(counts: dict, contents: dict) -> str:
    prog = contents.get("progression") or {}
    start = _safe(prog.get("intro", "")) if prog else ""
    cards = [
        ("progression.html", "Progression",
         "Badge order, level caps, elite four and champion for every region."),
        ("pokedex.html", "Pokédex",
         f"All {counts['species']:,} species — real spawn biomes, rarity, levels, drops and evolutions."),
        ("items.html", "Item Index",
         f"{counts['names']:,} items — every recipe, loot table and Pokémon drop, with a farming planner."),
        ("trainers.html", "Trainers",
         f"{counts['trainers']:,} trainer teams with movesets — scout every gym fight."),
        ("legendaries.html", "Legendaries",
         "Monuments, fossils, DNA — the concrete method for each legendary."),
        ("mechanics.html", "Mechanics",
         "CobbleDollars, TMs, raids, breeding, mega evolution — the pack's systems."),
        ("world.html", "World & Regions",
         "World generation, structures, and the optional Johto / Hoenn / Sinnoh packs."),
        ("key-items.html", "Key Items",
         "Badges, signature items, evolution items — what matters and where it's from."),
        ("mods.html", "Mod List", "All mods, grouped by what they do."),
    ]
    cards_html = "".join(
        f"<a class='card' href='{href}'><h3>{esc(t)}</h3><p>{esc(d)}</p></a>"
        for href, t, d in cards)
    body = f"""<div class="article">
<h1>COBBLEVERSE Wiki</h1>
<p class="sub">An unofficial, data-exact wiki for the COBBLEVERSE modpack
(Cobblemon 1.7.3 · Minecraft 1.21.1 · Fabric) — generated from the pack's own
jars, datapacks and configs, so the numbers are what your game actually rolls.</p>

<div class="statrow">
  <div class="stat"><div class="n">{counts['species']:,}</div><div class="l">species</div></div>
  <div class="stat"><div class="n">{counts['spawns']:,}</div><div class="l">spawn entries</div></div>
  <div class="stat"><div class="n">{counts['recipes']:,}</div><div class="l">recipes</div></div>
  <div class="stat"><div class="n">{counts['loot']:,}</div><div class="l">loot entries</div></div>
  <div class="stat"><div class="n">{counts['trainers']:,}</div><div class="l">trainers</div></div>
  <div class="stat"><div class="n">{counts['mods']}</div><div class="l">mods</div></div>
</div>

<section><h2>Your first hour</h2>
<ul>
<li><b>Choose your starter</b> — the pack greets you with
<i>"COBBLEVERSE: Press C to Start!"</i>; press <code>C</code> and pick your
first Pokémon.</li>
<li><b>Craft a Trainer Card</b> (paper + glass pane + name tag + redstone) and
keep it in your inventory — wild trainers only spawn around players carrying
one. It also shows your level cap and next required trainer.</li>
<li><b>Mind the level cap</b> — your Pokémon stop gaining XP at the cap
(effectively 25 at the start). Beating each gym leader raises it; the full
ladder is on <a href="progression.html">Progression</a>.</li>
<li><b>Find Brock</b> — craft his signature
<a href="items.html#lumymon:onyx_stone">Onyx Stone</a>, put it in a
<a href="items.html#lumymon:kanto_cartography_table">Kanto Cartography
Table</a>, and follow the treasure map to his gym in the plains. The
<a href="trainers.html#kanto_brock">Trainers page</a> shows his exact team
before you walk in.</li>
<li><b>Earn money</b> by beating trainers and selling to Cobble Merchants
(<a href="mechanics.html">CobbleDollars</a>) — Poké Balls, TMs and healing
items add up fast.</li>
</ul>
{start}
<div class="callout">The one rule of COBBLEVERSE: your level cap is gated
behind gym badges, and gym leaders spawn in strict order — knowing the badge
ladder on <a href="progression.html">Progression</a> is knowing the game.</div>
</section>

<section><h2>Browse</h2>
<div class="cards">{cards_html}</div></section>

<section><h2>About this wiki</h2>
<p>Every page is generated by the scripts in <code>tools/</code> from the pack's
own data files — spawn pools, loot tables, recipes, species definitions, trainer
teams and advancement trees. Nothing is copied from other wikis and nothing is
hand-guessed; if the pack updates, re-run
<code>python tools/extract.py</code> then <code>python tools/build_site.py</code>
to refresh every page. Sources are cited at the bottom of each entry.</p>
<p class="meta">COBBLEVERSE is by the LumyVerse team; Cobblemon by the Cobblemon
team. This is a fan-made offline reference generated from local pack files.
Pokémon sprites are from the PokéAPI sprites repository (Pokémon © Nintendo /
Game Freak), fetched once by <code>tools/fetch_sprites.py</code> for personal
offline use.</p>
</section>
</div>"""
    return page("Home", "index.html", body)
