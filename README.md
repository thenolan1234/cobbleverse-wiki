# COBBLEVERSE Wiki

An unofficial, offline wiki for the **COBBLEVERSE** modpack (Cobblemon 1.7.3 ·
Minecraft 1.21.1 · Fabric), generated entirely from the pack's own data files —
mod jars, datapacks and configs. Nothing is copied from other wikis; the
numbers on these pages are what the installed pack actually rolls.

**To read the wiki: open [`index.html`](index.html) in any browser.**
Everything works offline from the filesystem — no server needed.

## Pages

| Page | What's on it |
|---|---|
| `index.html` | Home — overview, stats, where to start |
| `progression.html` | Badge order, level caps, elite four, champion, per region |
| `pokedex.html` | Every species: real spawn biomes/buckets/levels, stats, drops, evolutions |
| `spawns.html` | Spawn Finder — best biomes to camp for a target, ranked by pool share |
| `tips.html` | Tips & tricks distilled from community guide videos (credited) |
| `items.html` | Every item: recipes, loot tables **and Pokémon drops**, with a farming planner |
| `trainers.html` | Every trainer team: levels, movesets, held items, how they're encountered |
| `legendaries.html` | The concrete acquisition method for each legendary |
| `mechanics.html` | CobbleDollars, TMs, raids, breeding, megas — the pack's systems |
| `world.html` | Worldgen, structures, and the optional Johto/Hoenn/Sinnoh add-on packs |
| `key-items.html` | Badges, gym signature items, evolution items |
| `mods.html` | All mods, categorized |

## Regenerating after a pack update

Requires Python 3.10+ (no dependencies):

```bash
python tools/extract.py       # reads the pack, writes data/wikidata.json
python tools/build_site.py    # renders every *.html page
python tools/fetch_sprites.py # (optional) fetch sprites for newly added dex numbers
```

Images come from three generated folders, all offline:

- `renders/` (+ `renders/shiny/`) — **3D portraits rendered from Cobblemon's
  own Bedrock models and textures** by `tools/render_models.py`, posed with
  each species' idle animation. These are the hero images on Pokédex pages
  and trainer team cards.
- `renders/trainers/` — trainer NPC portraits rendered from their Minecraft
  skins (shipped in the pack's RCT resource pack) by
  `tools/render_trainers.py`, shown on trainer pages, gym tables, search
  results and hover cards.
- `renders/structures/` — isometric renders of the pack's structure NBT
  files (legendary monuments, leagues, raid dens, centers) by
  `tools/render_structures.py` (needs `nbtlib`), shown on the Structures
  page.
- `sprites/` (+ `sprites/shiny/`) — 96×96 official 2D game sprites from the
  PokéAPI sprites repository, used as small inline images and as the fallback
  for species Cobblemon has no model for. Pokémon © Nintendo / Game Freak.
- `icons/` — item icons extracted from the pack's own jars (and the vanilla
  client jar) by `tools/extract_item_icons.py`, shown next to items across
  every page.

`extract.py` defaults to the local COBBLEVERSE install path; pass
`--pack "<profile folder>"` to point elsewhere. It only ever *reads* the pack.

## Sharing with friends

The wiki is fully self-contained: zip this folder (or use the prebuilt
`COBBLEVERSE-Wiki.zip` one level up) and send it — they unzip and open
`index.html`. No install, no internet needed. The `tools/` and `data/`
folders are only needed for regeneration and can be excluded to shrink it.

## How it works

- `tools/extract.py` — parses jars/datapacks: recipes, loot tables, item &
  biome tags, lang files, Cobblemon species / spawn pools / species additions,
  fossils, RCT trainers/mobs/series, and the pack's advancement trees.
  It applies Minecraft's datapack override semantics (a datapack file at the
  same `data/` path replaces a mod's file), so COBBLEVERSE's spawn/loot
  overhauls are reflected correctly. Optional packs in `datapacks/extra` are
  indexed separately and flagged as add-ons.
- `tools/build_site.py` (+ `templates.py`, `pages_apps.py`, `pages_articles.py`)
  — renders the static pages. The three browser pages embed their data as JSON
  and run as small self-contained JS apps.
- `content/*.json` — curated guide text (progression, legendaries, mechanics…)
  written against the extracted data. `build_site.py` renders whatever is
  present and shows a placeholder for anything missing.
- `data/wikidata.json` — the intermediate index (regenerated any time).

Based on the **cobbleindex** tooling concept (index a pack's own data and
answer "where do I get this?" with real probabilities), extended with
Cobblemon-specific domains.

## Credits

COBBLEVERSE by the LumyVerse team · Cobblemon by the Cobblemon team ·
Radical Cobblemon Trainers (RCT) content as shipped in the pack.
This is a fan-made local reference; it distributes no pack assets beyond
extracted metadata.
