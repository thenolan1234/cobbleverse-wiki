#!/usr/bin/env python3
"""One-off content fixes from the verification/critique pass (2026-08-09).

Applies the reconciliations the completeness critic called out: consistent
gym-locating flow, qualified trainer counts, effective starting level cap,
unified add-on install instructions, Terralith prerequisites, the Poke Radar
recipe correction, Resurrection Machine naming, and new riding/fishing
mechanics sections. Safe to re-run (each patch no-ops once applied).
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(HERE, "..", "content")


def load(name):
    with open(os.path.join(CONTENT, name), encoding="utf-8") as fh:
        return json.load(fh)


def save(name, data):
    with open(os.path.join(CONTENT, name), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)


def rep(label, text, old, new):
    if old in text:
        print(f"  ok  {label}")
        return text.replace(old, new)
    if new in text:
        print(f"  --  {label} (already applied)")
    else:
        print(f"  !!  {label} NOT FOUND")
    return text


# ---------------------------------------------------------------- legendaries
leg = load("legendaries.json")
leg["intro"] = rep(
    "poke radar recipe", leg["intro"],
    "crafted from iron, redstone and blue stained glass around a",
    "crafted from iron and redstone around a")
save("legendaries.json", leg)

# ---------------------------------------------------------------- trainers guide
tg = load("trainers_guide.json")
tg["intro"] = rep(
    "trainer count qualifier", tg["intro"],
    "over 350 named trainers spawn in the world",
    "about 380 named story trainers spawn in the world (the RCT mod also "
    "bundles roughly 1,300 more for its optional Radical Red, Unbound and "
    "BDSP side series)")
tg["mechanics"] = rep(
    "gym-finding flow", tg["mechanics"],
    "<li>Bring it to a <b>Map Trader</b> (found in Cobblemon town buildings "
    "such as the Lodge and taverns, and in Brock's gym) with an empty "
    "<b>map</b>: the trade returns an exploration map pointing at that "
    "leader's gym structure.</li>",
    "<li>Insert it into the matching region <b>Cartography Table</b> — a "
    "cheap craft (the <a href=\"items.html#lumymon:kanto_cartography_table\">"
    "Kanto Cartography Table</a> is planks + Poké Ball + paper) — to receive "
    "a treasure map marking that leader's gym. A <b>Map Trader</b> block in "
    "Cobblemon town buildings (Lodge, taverns) trades the same maps for an "
    "empty map, as an alternative while exploring.</li>")
tg["mechanics"] = rep(
    "effective starting cap", tg["mechanics"],
    "You start with a cap of 20.",
    "You start with an effective cap of <b>25</b> — the configured floor of "
    "20 never binds, because the cap tracks your next required trainer.")
for s in tg["series"]:
    if s["id"] == "hoenn":
        s["note"] = rep(
            "hoenn pat link", s.get("note", ""),
            "Pat (trainers.html#hoenn_pat)",
            "<a href=\"trainers.html#hoenn_pat\">Pat</a>")
        if "Terralith" not in s["note"]:
            s["note"] += (" <b>Requires Terralith:</b> most Hoenn gyms and "
                          "the league generate only in Terralith biomes, so "
                          "enable <code>Terralith-DP.zip</code> alongside the "
                          "Hoenn pack — see <a href=\"world.html\">World &amp; "
                          "Regions</a>.")
            print("  ok  hoenn terralith note")
    if s["id"] == "sinnoh" and "Terralith" not in (s.get("note") or ""):
        s["note"] = (s.get("note") or "") + (
            " <b>Requires Terralith:</b> Sinnoh's gyms and league sit almost "
            "entirely in Terralith biomes (Volcanic Peaks, Glacial Chasm, "
            "Desert Oasis…), so enable <code>Terralith-DP.zip</code> alongside "
            "the Sinnoh pack — see <a href=\"world.html\">World &amp; "
            "Regions</a>.")
        print("  ok  sinnoh terralith note")
save("trainers_guide.json", tg)

# ---------------------------------------------------------------- mods
mods = load("mods.json")
mods["intro"] = rep(
    "mods trainer count qualifier", mods["intro"],
    "drawn from Radical Red, Unbound, and Brilliant Diamond/Shining Pearl;",
    "drawn from Radical Red, Unbound, and Brilliant Diamond/Shining Pearl "
    "(about 380 of them are wired into the COBBLEVERSE story series — the "
    "rest belong to those optional side series);")
save("mods.json", mods)

# ---------------------------------------------------------------- progression
prog = load("progression.json")
prog["levelCapNote"] = rep(
    "starting cap 25", prog["levelCapNote"],
    "the pack sets <code>initialLevelCap = 20</code> (the mod default is 15).",
    "effectively <b>25</b> — the cap always tracks the next required key "
    "trainer (their ace's level + 5), which for Brock means 20 + 5. The "
    "configured <code>initialLevelCap = 20</code> is a floor that never "
    "binds in Kanto.")
INSTALL = ("into the profile's <code>datapacks</code> folder (game closed, "
           "then relaunch — see <a href=\"world.html\">World &amp; Regions</a> "
           "for the exact steps)")
for r in prog["regions"]:
    note = r.get("note") or ""
    if r["id"] == "johto":
        note = rep("johto install", note,
                   "into the world's <code>datapacks</code> folder and reload",
                   INSTALL)
    if r["id"] in ("hoenn", "sinnoh"):
        note = rep(f"{r['id']} install", note,
                   "into the world's <code>datapacks</code> folder to "
                   "activate it",
                   INSTALL + " to activate it")
        if "Terralith" not in note:
            note += (" <b>Requires Terralith:</b> this region's gyms and "
                     "league generate in Terralith biomes — enable "
                     "<code>Terralith-DP.zip</code> as well.")
            print(f"  ok  {r['id']} terralith note")
    r["note"] = note
save("progression.json", prog)

# ---------------------------------------------------------------- mechanics
mech = load("mechanics.json")
for s in mech["sections"]:
    s["body"] = rep(
        "resurrection naming", s["body"],
        "Cobblemon's Restoration Machine revives",
        "Cobblemon's Resurrection Machine (built from the Restoration Tank "
        "block) revives") if "Restoration Machine revives" in s["body"] else s["body"]
headings = [s["heading"] for s in mech["sections"]]
if "Pokémon Riding" not in headings:
    mech["sections"].append({
        "heading": "Pokémon Riding",
        "body": "<p>Cobblemon 1.7 lets you ride many Pokémon — land, water "
                "and air mounts depending on the species, each with its own "
                "ride stats (the data ships per-species ride settings, and "
                "Cobblemon's advancement line includes riding a Pokémon and "
                "maxing ride stats). Send out a rideable Pokémon and mount it "
                "from its interaction menu. A water or air mount is the "
                "practical answer to ocean gyms and the far-flung Terralith "
                "biomes the later regions use.</p>"})
    print("  ok  riding section")
if not any("Fishing" in h for h in headings):
    mech["sections"].append({
        "heading": "Fishing with Poké Rods",
        "body": "<p>Poké Rod fishing is a first-class catch method. Each rod "
                "is made in a <b>smithing table</b>: a fishing rod + a "
                "<a href=\"items.html#cobblemon:pokerod_smithing_template\">"
                "Pokérod Smithing Template</a> + the Poké Ball whose look you "
                "want (49 rod variants exist, one per ball). Fishing with "
                "berry bait biases what bites — the pack ships dozens of "
                "bait effects — and reels in water Pokémon plus treasure, "
                "including the Gold Bottle Cap odds noted under Hyper "
                "Training. CobbleNav's FishingNav screen shows what you can "
                "hook where you're standing.</p>"})
    print("  ok  fishing section")
save("mechanics.json", mech)

print("content patch complete.")
