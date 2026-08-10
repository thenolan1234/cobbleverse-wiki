"""Shared page shell, CSS and JS helpers for the Cobbleverse wiki.

Visual language extends the cobbleindex site_builder ocean theme.
"""

from __future__ import annotations

import html

NAV_ITEMS = [
    ("index.html", "Home"),
    ("progression.html", "Progression"),
    ("pokedex.html", "Pokédex"),
    ("spawns.html", "Spawn Finder"),
    ("items.html", "Items"),
    ("trainers.html", "Trainers"),
    ("legendaries.html", "Legendaries"),
    ("mechanics.html", "Mechanics"),
    ("world.html", "World"),
    ("key-items.html", "Key Items"),
    ("tips.html", "Tips"),
    ("mods.html", "Mods"),
    ("videos.html", "Videos"),
]


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


CSS = """
:root{
  --abyss:#0b1a20; --shelf:#12262e; --reef:#1a3540; --deep:#081318;
  --foam:#dcecef; --tide:#5ad1c8; --amber:#f0a840; --coral:#e8735c;
  --silt:#7fa3ae; --moss:#8fd18b;
}
*{box-sizing:border-box}
html{scrollbar-color:var(--reef) var(--abyss)}
html,body{margin:0;min-height:100%}
body{
  background:var(--abyss); color:var(--foam);
  font:15px/1.55 ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  -webkit-font-smoothing:antialiased;
}
h1,h2,h3,h4,.display{
  font-family:"Space Grotesk",ui-sans-serif,system-ui,sans-serif;
  font-weight:600; letter-spacing:-.02em; margin:0;
}
a{color:var(--tide);text-decoration:none}
a:hover{text-decoration:underline}
code{background:var(--shelf);border:1px solid var(--reef);border-radius:3px;
  padding:1px 5px;font-size:12.5px}

/* ---- top nav ---- */
nav.top{
  display:flex;align-items:baseline;gap:2px;flex-wrap:wrap;
  padding:10px 18px;border-bottom:1px solid var(--reef);
  background:var(--deep);position:sticky;top:0;z-index:50;
}
nav.top .brand{
  font-family:"Space Grotesk",sans-serif;font-weight:600;font-size:16px;
  color:var(--amber);margin-right:14px;letter-spacing:.02em;
}
nav.top .brand small{color:var(--silt);font-weight:400;font-size:11px;margin-left:6px}
nav.top a.item{
  padding:4px 10px;border-radius:3px;font-size:12.5px;color:var(--foam);
}
nav.top a.item:hover{background:var(--shelf);text-decoration:none}
nav.top a.item[aria-current=page]{background:var(--reef);color:var(--tide)}

/* ---- article pages ---- */
.article{max-width:880px;margin:0 auto;padding:34px 26px 80px}
.article h1{font-size:30px;margin-bottom:6px}
.article .sub{color:var(--silt);font-size:13px;margin-bottom:26px}
.article section{margin:26px 0}
.article h2{
  font-size:19px;color:var(--amber);margin-bottom:10px;
  border-bottom:1px solid var(--reef);padding-bottom:6px;
}
.article p{margin:9px 0}
.article ul{margin:8px 0;padding-left:22px}
.article li{margin:4px 0}
.callout{
  background:var(--shelf);border:1px solid var(--reef);
  border-left:2px solid var(--tide);padding:12px 15px;border-radius:3px;
  margin:14px 0;font-size:13.5px;
}
.callout.warn{border-left-color:var(--amber)}

/* ---- home cards ---- */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px;margin:18px 0}
.card{
  background:var(--shelf);border:1px solid var(--reef);border-radius:4px;
  padding:15px 16px;display:block;color:var(--foam);
}
.card:hover{border-color:var(--tide);text-decoration:none}
.card h3{font-size:15px;color:var(--tide);margin-bottom:5px}
.card p{margin:0;font-size:12.5px;color:var(--silt);line-height:1.5}
.statrow{display:flex;gap:22px;flex-wrap:wrap;margin:16px 0}
.stat .n{font-family:"Space Grotesk",sans-serif;font-size:24px;font-weight:600;color:var(--tide)}
.stat .l{font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--silt)}

/* ---- browser (sidebar+detail) pages ---- */
.wrap{display:grid;grid-template-columns:330px 1fr;height:calc(100vh - 45px)}
@media(max-width:840px){.wrap{grid-template-columns:1fr;height:auto}}
aside{border-right:1px solid var(--reef);display:flex;flex-direction:column;min-height:0}
.padbox{padding:14px 16px 10px}
.padbox h1{font-size:17px}
.padbox p.note{margin:5px 0 0;color:var(--silt);font-size:11px;line-height:1.5}
.searchbox{padding:0 16px 8px}
input[type=search]{
  width:100%;padding:8px 11px;background:var(--shelf);color:var(--foam);
  border:1px solid var(--reef);border-radius:3px;font:inherit;font-size:13px;
}
input[type=search]:focus,select:focus{outline:2px solid var(--tide);outline-offset:-1px}
.filters{display:flex;gap:6px;padding:0 16px 10px;flex-wrap:wrap}
.filters select,.filters label.chk{
  background:var(--shelf);color:var(--foam);border:1px solid var(--reef);
  border-radius:3px;font:inherit;font-size:11.5px;padding:4px 6px;
}
.filters label.chk{display:flex;align-items:center;gap:5px;cursor:pointer}
#results{overflow-y:auto;flex:1;padding:0 8px 18px;min-height:0}
.row{
  padding:5px 10px;border-radius:3px;cursor:pointer;
  display:flex;justify-content:space-between;gap:8px;align-items:center;
}
.row:hover{background:var(--shelf)}
.row[aria-selected=true]{background:var(--reef)}
.row .nm{font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}
.row .ns{font-size:10px;color:var(--silt);flex-shrink:0}
img.spr{image-rendering:pixelated;vertical-align:middle;flex-shrink:0}
.chip img.spr{margin:-3px 3px -3px -2px}
.mon img.spr{margin:-6px 2px -6px -4px}
.empty{color:var(--silt);font-size:12px;padding:10px}
main{overflow-y:auto;padding:24px 30px 70px;min-width:0}
@media(max-width:840px){main{padding:18px 14px 60px}}
.item-head{border-bottom:1px solid var(--reef);padding-bottom:14px;margin-bottom:20px}
.item-head h2{font-size:26px}
.id{color:var(--tide);font-size:12px;margin-top:4px;word-break:break-all}
.tip{color:var(--silt);font-size:13px;margin-top:8px;font-style:italic}
section.blk{margin-bottom:28px}
section.blk>h3{
  font-size:11px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--silt);margin-bottom:10px;
}
.splash{color:var(--silt);max-width:56ch;font-size:13.5px;line-height:1.8}
.splash b{color:var(--foam);font-weight:400}

/* chips */
.chip{
  display:inline-block;background:var(--deep);border:1px solid var(--reef);
  border-radius:3px;padding:3px 8px;font-size:12px;cursor:pointer;color:var(--foam);
  margin:0 4px 4px 0;
}
a.chip:hover{border-color:var(--tide);color:var(--tide);text-decoration:none}
.chip.tag{border-style:dashed;color:var(--silt);cursor:default}
.chip.plain{cursor:default}
.src{font-size:10.5px;color:var(--silt);margin-top:6px}
.badge{
  display:inline-block;border-radius:3px;padding:1px 7px;font-size:10.5px;
  letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--reef);
}
.badge.addon{color:var(--amber);border-color:var(--amber)}
.b-common{color:var(--silt)} .b-uncommon{color:var(--tide)}
.b-rare{color:var(--amber)} .b-ultra-rare{color:var(--coral)}

/* pokemon type chips: colored dot + text (identity never color-alone) */
.type{
  display:inline-flex;align-items:center;gap:6px;background:var(--deep);
  border:1px solid var(--reef);border-radius:3px;padding:2px 9px 2px 7px;
  font-size:12px;text-transform:capitalize;margin-right:5px;
}
.type i{width:9px;height:9px;border-radius:50%;display:inline-block}

/* stat meters */
.stats{display:grid;grid-template-columns:auto 1fr auto;gap:4px 10px;max-width:420px;align-items:center}
.stats .k{font-size:11px;color:var(--silt);text-transform:uppercase;letter-spacing:.08em;white-space:nowrap}
.stats .bar{height:6px;background:var(--reef);border-radius:3px;overflow:hidden}
.stats .bar i{display:block;height:100%;background:var(--tide);border-radius:3px}
.stats .v{font-size:12px;text-align:right;min-width:3ch}
.stats .total .v,.stats .total .k{color:var(--amber)}

/* generic data tables */
table.data{border-collapse:collapse;width:100%;font-size:12.5px;margin:6px 0}
table.data th{
  text-align:left;color:var(--silt);font-weight:400;font-size:10.5px;
  text-transform:uppercase;letter-spacing:.1em;padding:5px 10px 5px 0;
  border-bottom:1px solid var(--reef);
}
table.data td{padding:6px 10px 6px 0;border-bottom:1px solid var(--shelf);vertical-align:top}
details.biomes{display:inline-block}
details.biomes summary{cursor:pointer;color:var(--tide);font-size:12px;list-style:none}
details.biomes summary::after{content:" \\25be"}
details.biomes[open] summary::after{content:" \\25b4"}
details.biomes .blist{color:var(--silt);font-size:11.5px;max-width:52ch;padding:4px 0}
.meta{font-size:11.5px;color:var(--silt)}
.bar{height:3px;background:var(--reef);border-radius:2px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--tide)}
.drop{
  display:grid;grid-template-columns:1fr auto;gap:3px 16px;
  padding:10px 0;border-bottom:1px solid var(--shelf);
}
.drop .table{font-size:13px;word-break:break-all}
.drop .runs{
  font-family:"Space Grotesk",sans-serif;font-size:19px;font-weight:600;
  color:var(--amber);white-space:nowrap;text-align:right;line-height:1.2;
}
.drop .runs small{display:block;font-size:9.5px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--silt);font-weight:400}
.drop .meta{grid-column:1/-1}
.drop .bar{grid-column:1/-1;height:3px;background:var(--reef);border-radius:2px;overflow:hidden}
.drop .bar i{display:block;height:100%;background:var(--tide)}
.planner{
  background:var(--shelf);border:1px solid var(--reef);border-left:2px solid var(--amber);
  padding:12px 15px;margin-bottom:16px;display:flex;align-items:center;
  gap:11px;flex-wrap:wrap;font-size:13px;
}
.planner input{
  width:64px;padding:5px 7px;background:var(--abyss);color:var(--amber);
  border:1px solid var(--reef);border-radius:3px;font:inherit;font-weight:600;
  text-align:center;
}
.planner .lbl{color:var(--silt)}
.recipe{
  background:var(--shelf);border:1px solid var(--reef);border-radius:3px;
  padding:11px 14px;margin-bottom:8px;
}
.recipe .kind{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--silt)}
.recipe .ing{margin-top:7px}
.none{color:var(--coral);font-size:13px}
.none b{color:var(--foam)}
.hint{color:var(--silt);font-size:12px;margin-top:6px;line-height:1.6}

/* trainer team cards */
.mon{
  background:var(--shelf);border:1px solid var(--reef);border-radius:3px;
  padding:10px 13px;margin-bottom:8px;
  display:flex;flex-wrap:wrap;gap:4px 16px;align-items:baseline;
}
.mon .sp{font-family:"Space Grotesk",sans-serif;font-size:15px;font-weight:600}
.mon .lv{color:var(--amber);font-size:13px}
.mon .kv{font-size:11.5px;color:var(--silt)}
.mon .kv b{color:var(--foam);font-weight:400}
.mon .moves{width:100%;font-size:11.5px;color:var(--silt)}
.mon .moves code{margin-right:4px}

/* milestone list (progression) */
.mile{
  display:grid;grid-template-columns:auto 1fr;gap:2px 14px;
  padding:10px 0;border-bottom:1px solid var(--shelf);
}
.mile .kind{
  font-size:10px;letter-spacing:.1em;text-transform:uppercase;
  padding:2px 8px;border:1px solid var(--reef);border-radius:3px;height:fit-content;
  white-space:nowrap;margin-top:2px;
}
.mile .kind.badge-k{color:var(--amber);border-color:var(--amber)}
.mile .kind.elite-k{color:var(--coral)}
.mile .kind.champion-k{color:var(--coral);border-color:var(--coral)}
.mile .kind.legendary-k{color:var(--tide);border-color:var(--tide)}
.mile .kind.item-k{color:var(--moss)}
.mile h4{font-size:14.5px}
.mile p{margin:2px 0 0;font-size:12.5px;color:var(--silt)}
.mile .ico{font-size:11px;color:var(--silt)}
footer.gen{
  border-top:1px solid var(--reef);color:var(--silt);font-size:11px;
  padding:14px 18px;text-align:center;
}
footer.gen a{color:var(--silt);text-decoration:underline}
"""

TYPE_COLORS = {
    "normal": "#A8A878", "fire": "#F08030", "water": "#6890F0",
    "grass": "#78C850", "electric": "#F8D030", "ice": "#98D8D8",
    "fighting": "#C03028", "poison": "#A040A0", "ground": "#E0C068",
    "flying": "#A890F0", "psychic": "#F85888", "bug": "#A8B820",
    "rock": "#B8A038", "ghost": "#705898", "dragon": "#7038F8",
    "dark": "#705848", "steel": "#B8B8D0", "fairy": "#EE99AC",
}

# Small JS library shared by the browser pages.
SHARED_JS = r"""
const $ = s => document.querySelector(s);
const escHtml = s => String(s ?? '').replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function pretty(id){
  return String(id ?? '').split(':').pop().split('/').pop()
    .replace(/_/g,' ').replace(/\b\w/g, c => c.toUpperCase());
}
function fmtPct(p){
  const v = p * 100;
  return v >= 10 ? v.toFixed(0)+'%' : v >= 1 ? v.toFixed(1)+'%' : v.toFixed(2)+'%';
}
function fmtRange(a){ return a[0] === a[1] ? String(a[0]) : `${a[0]}-${a[1]}`; }
function debounce(fn, ms){
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}
function hashSelect(showFn){
  const go = () => {
    const h = decodeURIComponent(location.hash.slice(1));
    if(h) showFn(h);
  };
  window.addEventListener('hashchange', go);
  return go;
}
function iconPath(id){
  const k = String(id).indexOf(':');
  if(k < 0) return null;
  return 'icons/' + id.slice(0, k) + '/' + id.slice(k + 1).replace(/\//g, '__') + '.png';
}
function itemIcon(id, s){
  const p = iconPath(id);
  return p ? `<img class="spr" src="${p}" style="width:${s}px;height:${s}px" alt="" loading="lazy" onerror="this.remove()">` : '';
}
// 3D model render with 2D sprite fallback
function heroImg(sid, dex, s, shiny){
  const fb = dex ? `sprites/${shiny ? 'shiny/' : ''}${dex}.png` : '';
  return `<img class="spr" src="renders/${shiny ? 'shiny/' : ''}${sid}.png"
    style="width:${s}px;height:${s}px" alt="" loading="lazy" data-fb="${fb}"
    onerror="if(this.dataset.fb){this.src=this.dataset.fb;this.dataset.fb='';}else{this.remove();}">`;
}
"""


def icon_img(item_id: str, size: int) -> str:
    """Python-side item icon tag (same path convention as the JS helper)."""
    if not item_id or ":" not in item_id:
        return ""
    ns, name = item_id.split(":", 1)
    safe = name.replace("/", "__")
    return (f'<img class="spr" src="icons/{esc(ns)}/{esc(safe)}.png" '
            f'style="width:{size}px;height:{size}px" alt="" loading="lazy" '
            f'onerror="this.remove()">')


def page(title: str, active: str, body: str, extra_head: str = "",
         subtitle: str = "", full_height: bool = False) -> str:
    nav = []
    for href, label in NAV_ITEMS:
        cur = ' aria-current="page"' if href == active else ""
        nav.append(f'<a class="item" href="{href}"{cur}>{label}</a>')
    footer = "" if full_height else (
        '<footer class="gen">Generated from the pack’s own data files by '
        '<code>tools/</code> in this folder · COBBLEVERSE · '
        'Cobblemon 1.7.3 · MC 1.21.1</footer>')
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · COBBLEVERSE Wiki</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600&display=swap" rel="stylesheet">
<style>{CSS}</style>{extra_head}
</head><body>
<nav class="top"><span class="brand">COBBLEVERSE<small>wiki</small></span>{''.join(nav)}</nav>
{body}
{footer}
</body></html>"""
