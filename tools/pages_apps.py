"""Browser-style app pages: Pokédex, Items, Trainers.

Each page embeds its own trimmed JSON payload and a small vanilla-JS app,
following the interaction patterns of the original cobbleindex site.
"""

from __future__ import annotations

import json

from templates import page, esc, SHARED_JS, TYPE_COLORS, icon_img
from pages_articles import _safe


def _payload(data: dict) -> str:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")


def _script(js: str, payload: str) -> str:
    return f"<script>const DATA={payload};\n{SHARED_JS}\n{js}</script>"


# ================================================================ Pokédex

POKEDEX_JS = r"""
const TYPE_COLORS = DATA.typeColors;
const ids = Object.keys(DATA.species).sort((a, b) =>
  (DATA.species[a].dex ?? 9999) - (DATA.species[b].dex ?? 9999));
let current = null;

function rows(){
  const q = $('#q').value.trim().toLowerCase();
  const ty = $('#f-type').value, gen = $('#f-gen').value;
  const spawnOnly = $('#f-spawn').checked;
  const out = [];
  for(const id of ids){
    const s = DATA.species[id];
    if(q && !(s.name.toLowerCase().includes(q) || id.includes(q) ||
              String(s.dex) === q)) continue;
    if(ty && !s.types.includes(ty)) continue;
    if(gen && !s.labels.includes(gen)) continue;
    if(spawnOnly && !DATA.spawnsBy[id]) continue;
    out.push(id);
  }
  return out;
}

function renderList(){
  const hits = rows();
  const box = $('#results');
  if(!hits.length){ box.innerHTML = '<p class="empty">No Pokémon matches.</p>'; return; }
  box.innerHTML = hits.slice(0, 400).map(id => {
    const s = DATA.species[id];
    return `<div class="row" role="option" data-id="${id}"
        aria-selected="${id === current}" tabindex="0">
      ${spr(s.dex, 30)}
      <span class="nm">#${String(s.dex ?? '?').padStart(3,'0')} ${escHtml(s.name)}</span>
      <span class="ns">${s.types.join('/')}</span>
    </div>`;
  }).join('') + (hits.length > 400 ? `<p class="empty">…${hits.length - 400} more — refine the search.</p>` : '');
}

const typeChip = t => `<span class="type"><i style="background:${TYPE_COLORS[t] || '#888'}"></i>${t}</span>`;
const bucketChip = b => `<span class="badge b-${b}">${b || '?'}</span>`;
const itemLink = id => `<a class="chip" href="items.html#${encodeURIComponent(id)}">${itemIcon(id, 18)}${escHtml(DATA.names[id] || pretty(id))}</a>`;
const spr = (dex, s) => dex
  ? `<img class="spr" src="sprites/${dex}.png" style="width:${s}px;height:${s}px" alt="" loading="lazy" onerror="this.remove()">`
  : '';
const monLink = id => DATA.species[id]
  ? `<span class="chip" data-go="${id}">${spr(DATA.species[id].dex, 22)}${escHtml(DATA.species[id].name)}</span>`
  : `<span class="chip plain">${escHtml(pretty(id))}</span>`;

function biomeCell(sp){
  const parts = [];
  for(const b of sp.biomes || []){
    if(b.startsWith('#')){
      const tag = b.slice(1);
      const members = DATA.biomeTags[tag] || [];
      const label = pretty(tag);
      parts.push(members.length
        ? `<details class="biomes"><summary>${escHtml(label)} (${members.length})</summary>
             <div class="blist">${members.map(pretty).map(escHtml).join(', ')}</div></details>`
        : `<span>${escHtml(label)}</span>`);
    } else parts.push(`<span>${escHtml(pretty(b))}</span>`);
  }
  let html = parts.join(', ') || '<span class="meta">any biome</span>';
  if((sp.anti || []).length)
    html += `<div class="meta">not: ${sp.anti.map(b => pretty(b.replace('#',''))).map(escHtml).join(', ')}</div>`;
  return html;
}

function show(id){
  const s = DATA.species[id];
  if(!s){ return; }
  current = id;
  history.replaceState(null, '', '#' + id);
  renderList();

  const spawns = (DATA.spawnsBy[id] || []).slice()
    .sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0));
  const statTotal = Object.values(s.stats).reduce((a, b) => a + b, 0);
  const statRow = (k, label) => {
    const v = s.stats[k] ?? 0;
    return `<div class="k">${label}</div>
      <div class="bar"><i style="width:${Math.min(100, v / 180 * 100)}%"></i></div>
      <div class="v">${v}</div>`;
  };

  const heroSprites = `
    <div style="display:flex;gap:10px;flex-shrink:0">
      <figure style="margin:0;text-align:center">
        ${heroImg(id, s.dex, 140, false)}
        <figcaption class="meta" style="font-size:10px">normal</figcaption>
      </figure>
      <figure style="margin:0;text-align:center">
        ${heroImg(id, s.dex, 140, true)}
        <figcaption class="meta" style="font-size:10px;color:var(--amber)">✦ shiny</figcaption>
      </figure>
    </div>`;
  let html = `<div class="item-head" style="display:flex;gap:20px;align-items:center;flex-wrap:wrap">
    ${heroSprites}
    <div>
    <h2>#${String(s.dex ?? '?').padStart(3,'0')} ${escHtml(s.name)}</h2>
    <div style="margin-top:8px">${s.types.map(typeChip).join('')}
      ${s.labels.filter(l => !/^gen\d/.test(l)).map(l =>
        `<span class="badge" style="margin-left:4px">${escHtml(l.replace(/_/g,' '))}</span>`).join('')}
      ${s.addon ? '<span class="badge addon" style="margin-left:4px">add-on pack</span>' : ''}
    </div>
    ${s.implemented === false ? '<div class="tip">Marked not-implemented in the pack data — may be unobtainable.</div>' : ''}
    </div>
  </div>`;

  html += `<section class="blk"><h3>Base stats</h3>
    <div class="stats">
      ${statRow('hp','HP')}${statRow('attack','Atk')}${statRow('defence','Def')}
      ${statRow('special_attack','SpA')}${statRow('special_defence','SpD')}${statRow('speed','Spe')}
      <div class="k total" style="display:contents"><div class="k">Total</div><div></div><div class="v" style="color:var(--amber)">${statTotal}</div></div>
    </div>
    <p class="meta" style="margin-top:10px">
      catch rate ${s.catchRate ?? '?'} · ${s.maleRatio === -1 ? 'genderless'
        : s.maleRatio == null ? '' : (s.maleRatio * 100) + '% male'}
      · egg: ${(s.eggGroups || []).join(', ') || '?'}
      · abilities: ${(s.abilities || []).map(a => escHtml(String(a).replace('h:','hidden: '))).join(', ')}
    </p></section>`;

  if(spawns.length){
    html += `<section class="blk"><h3>Where it spawns (${spawns.length})</h3>
      <table class="data"><tr><th>Rarity</th><th>Lv</th><th>Weight</th><th>Where</th><th>Conditions</th></tr>`;
    for(const sp of spawns){
      const notes = [];
      if(sp.aspects) notes.push(escHtml(sp.aspects));
      if(sp.herd) notes.push('herd');
      if(sp.ctx && sp.ctx !== 'grounded') notes.push(escHtml(sp.ctx));
      for(const p of sp.presets || []){
        const t = DATA.presets[p];
        notes.push(t ? `${escHtml(p)} <span class="meta">(${escHtml(t)})</span>` : escHtml(p));
      }
      if(sp.cond) notes.push(escHtml(sp.cond));
      if(sp.wmult) notes.push(escHtml(sp.wmult));
      if(sp.addon) notes.push('<span class="badge addon">add-on</span>');
      html += `<tr>
        <td>${bucketChip(sp.bucket)}</td>
        <td>${escHtml(sp.level || '?')}</td>
        <td>${sp.weight ?? '?'}</td>
        <td>${biomeCell(sp)}</td>
        <td class="meta">${notes.join(' · ') || '—'}</td></tr>`;
    }
    html += `</table>
      <p class="meta">Rarity buckets are Cobblemon spawn pools: common &gt; uncommon &gt; rare &gt; ultra-rare.
      Weight is relative within the same bucket at a given spot.</p></section>`;
  } else {
    html += `<section class="blk"><h3>Where it spawns</h3>
      <p class="none">No natural spawn entry in the active pack data.</p>
      <p class="hint">It may come from evolution, fossils, raids, structures or an
      add-on region pack — check the sections below and the
      <a href="legendaries.html">Legendaries</a> page if applicable.</p></section>`;
  }

  const evoFrom = DATA.evoFrom[id] || [];
  if(s.evolutions.length || evoFrom.length){
    html += `<section class="blk"><h3>Evolution</h3>`;
    for(const e of evoFrom)
      html += `<div style="margin-bottom:6px">${monLink(e.from)} <span class="meta">→ this · ${escHtml(e.desc)}</span></div>`;
    for(const e of s.evolutions)
      html += `<div style="margin-bottom:6px"><span class="meta">this →</span> ${monLink(e.to)}
        <span class="meta">${escHtml(e.desc)}</span></div>`;
    html += `</section>`;
  }

  if(s.drops.length){
    html += `<section class="blk"><h3>Drops on defeat</h3><div>`;
    for(const d of s.drops){
      const odds = d.pct != null ? `${d.pct}%` : (d.range ? `${d.range}×` : '');
      html += `${itemLink(d.item)} <span class="meta">${odds}</span> &nbsp;`;
    }
    if(s.dropAmount != null) html += `<div class="meta" style="margin-top:6px">up to ${s.dropAmount} entr${s.dropAmount === 1 ? 'y' : 'ies'} roll per faint</div>`;
    html += `</div></section>`;
  }

  const fos = DATA.fossils.filter(f => f.result === id);
  if(fos.length){
    html += `<section class="blk"><h3>Fossil revival</h3>`;
    for(const f of fos)
      html += `<p>Revive from ${f.items.map(itemLink).join(' + ')} in the fossil machine.</p>`;
    html += `</section>`;
  }

  if(s.modifiedBy) html += `<p class="src">modified by ${s.modifiedBy.map(escHtml).join(', ')}</p>`;
  html += `<p class="src">data: ${escHtml(s.src)}</p>`;
  $('main').innerHTML = html;
  $('main').scrollTop = 0;
}

const refresh = debounce(renderList, 80);
$('#q').addEventListener('input', refresh);
for(const f of ['#f-type', '#f-gen', '#f-spawn'])
  $(f).addEventListener('change', renderList);
document.addEventListener('click', e => {
  const row = e.target.closest('.row'); if(row) return show(row.dataset.id);
  const chip = e.target.closest('[data-go]'); if(chip) return show(chip.dataset.go);
});
document.addEventListener('keydown', e => {
  const row = e.target.closest('.row');
  if(row && (e.key === 'Enter' || e.key === ' ')){ e.preventDefault(); show(row.dataset.id); }
  if(e.key === '/' && e.target !== $('#q')){ e.preventDefault(); $('#q').focus(); }
});
renderList();
hashSelect(show)();
"""


def build_pokedex(payload: dict, counts: dict) -> str:
    gens = [f"gen{i}" for i in range(1, 10)]
    type_opts = "".join(f'<option value="{t}">{t}</option>' for t in sorted(TYPE_COLORS))
    gen_opts = "".join(f'<option value="{g}">{g}</option>' for g in gens)
    body = f"""
<div class="wrap">
  <aside>
    <div class="padbox">
      <h1>Pokédex</h1>
      <p class="note">{counts['species']:,} species · {counts['spawns']:,} spawn entries,
      read from the pack's own data. Spawns reflect the COBBLEVERSE overrides,
      not vanilla Cobblemon.</p>
    </div>
    <div class="searchbox">
      <input id="q" type="search" placeholder="Search name / dex #&nbsp;&nbsp;/" autocomplete="off">
    </div>
    <div class="filters">
      <select id="f-type"><option value="">any type</option>{type_opts}</select>
      <select id="f-gen"><option value="">any gen</option>{gen_opts}</select>
      <label class="chk"><input type="checkbox" id="f-spawn">spawns</label>
    </div>
    <div id="results" role="listbox" aria-label="Species"></div>
  </aside>
  <main>
    <p class="splash">
      Pick a Pokémon to see <b>where it actually spawns in this pack</b> —
      biomes, rarity bucket, level range and conditions — plus base stats,
      drops, evolutions and fossil sources.<br><br>
      Spawn data comes from the pack's <code>spawn_pool_world</code> files with
      COBBLEVERSE's own overrides applied. Type <code>/</code> to search.
    </p>
  </main>
</div>
{_script(POKEDEX_JS, _payload(payload))}"""
    return page("Pokédex", "pokedex.html", body, full_height=True)


# ================================================================ Items

ITEMS_JS = r"""
let target = 1, current = null;
const ids = Object.keys(DATA.names).sort((a, b) =>
  (DATA.names[a] || a).localeCompare(DATA.names[b] || b));
const nameOf = id => DATA.names[id] || pretty(id);

function search(q){
  q = q.trim().toLowerCase();
  if(!q) return [];
  const starts = [], has = [];
  for(const id of ids){
    const n = nameOf(id).toLowerCase();
    if(n.startsWith(q) || id.toLowerCase().startsWith(q)) starts.push(id);
    else if(n.includes(q) || id.toLowerCase().includes(q)) has.push(id);
    if(starts.length > 80) break;
  }
  return starts.concat(has).slice(0, 80);
}

function renderList(hits){
  const box = $('#results');
  if(!hits.length){
    box.innerHTML = $('#q').value.trim()
      ? '<p class="empty">No item matches that.</p>'
      : '<p class="empty">Type to search 7,000+ items.</p>';
    return;
  }
  box.innerHTML = hits.map(id => `
    <div class="row" role="option" data-id="${escHtml(id)}"
         aria-selected="${id === current}" tabindex="0">
      ${itemIcon(id, 22)}
      <span class="nm">${escHtml(nameOf(id))}</span>
      <span class="ns">${escHtml(id.split(':')[0])}</span>
    </div>`).join('');
}

function recipeCard(r){
  const ing = r.i.map(x => x.id
    ? `<span class="chip" data-go="${escHtml(x.id)}">${itemIcon(x.id, 18)}${escHtml(nameOf(x.id))}</span>`
    : `<span class="chip tag" title="${escHtml((x.m || []).map(nameOf).join(', '))}">any ${escHtml(x.tag.split('/').pop())} (${x.n})</span>`
  ).join('');
  return `<div class="recipe">
    <div class="kind">${escHtml(r.t.replace(/_/g,' '))}${r.c > 1 ? ` ×${r.c}` : ''}${r.label ? ` → <b>${escHtml(r.label)}</b>` : ''}${r.addon ? ' · <span class="badge addon">add-on</span>' : ''}</div>
    <div class="ing">${ing}</div>
    <div class="src">${escHtml(r.src)}</div>
  </div>`;
}

function show(id){
  current = id;
  history.replaceState(null, '', '#' + encodeURIComponent(id));
  const q = $('#q').value;
  renderList(search(q).length ? search(q) : [id]);

  const drops = DATA.loot.filter(e => e.i === id).sort((a, b) => b.e - a.e);
  const makes = DATA.recipes.filter(r => r.o === id);
  const uses = DATA.recipes.filter(r =>
    r.i.some(x => x.id === id || (x.m && x.m.includes(id))));
  const mons = DATA.monDrops[id] || [];
  const evos = DATA.evoItems[id] || [];
  const sig = DATA.sigItems[id];
  const fos = DATA.fossils.filter(f => f.items.includes(id));

  let html = `<div class="item-head" style="display:flex;gap:16px;align-items:center">
      ${itemIcon(id, 52)}
      <div>
      <h2>${escHtml(nameOf(id))}</h2>
      <div class="id">${escHtml(id)}</div>
      ${DATA.tips[id] ? `<div class="tip">${escHtml(DATA.tips[id])}</div>` : ''}
      </div>
    </div>`;

  const needPlanner = drops.length || mons.length;
  if(needPlanner){
    html += `<div class="planner">
      <span class="lbl">I need</span>
      <input id="target" type="number" min="1" max="9999" value="${target}"
             aria-label="How many do you need">
      <span class="lbl">→ runs / kills needed per source, best first</span>
    </div>`;
  }

  if(mons.length){
    html += `<section class="blk"><h3>Dropped by Pokémon (${mons.length})</h3>`;
    const sorted = mons.slice().sort((a, b) => (b.pct ?? 100) - (a.pct ?? 100));
    for(const m of sorted.slice(0, 30)){
      const p = m.pct != null ? m.pct / 100 : 1;
      const kills = Math.ceil(target / p);
      const dex = DATA.speciesDex[m.sp];
      const im = dex ? `<img class="spr" src="sprites/${dex}.png" style="width:30px;height:30px;margin:-6px 4px -6px 0" alt="" loading="lazy" onerror="this.remove()">` : '';
      html += `<div class="drop">
        <div class="table">${im}<a href="pokedex.html#${m.sp}">${escHtml(m.name)}</a></div>
        <div class="runs">${kills}<small>kills</small></div>
        <div class="meta">${m.pct != null ? m.pct + '% per faint' : 'guaranteed'}${m.range ? ' · ' + m.range + ' each' : ''}</div>
      </div>`;
    }
    if(sorted.length > 30) html += `<p class="meta">…and ${sorted.length - 30} more (see Pokédex)</p>`;
    html += `</section>`;
  }

  if(drops.length){
    const best = drops[0].e;
    html += `<section class="blk"><h3>Loot tables (${drops.length})</h3>`;
    for(const d of drops.slice(0, 25)){
      const runs = d.e > 0 && !d.ref ? Math.ceil(target / d.e) : Infinity;
      html += `<div class="drop">
        <div class="table">${escHtml(d.t)}${d.ref ? ' <span class="badge">nested table</span>' : ''}${d.addon ? ' <span class="badge addon">add-on</span>' : ''}</div>
        <div class="runs">${isFinite(runs) ? runs : '—'}<small>runs</small></div>
        <div class="bar"><i style="width:${Math.max(2, (d.e / best) * 100)}%"></i></div>
        <div class="meta">${fmtPct(d.p)} of pool · ${fmtRange(d.r)} rolls ·
          ${fmtRange(d.n)} per hit · ${d.e.toFixed(3)} expected/open · ${escHtml(d.src)}${d.addon ? ' — replaces this table when the add-on is enabled' : ''}</div>
      </div>`;
    }
    if(drops.length > 25) html += `<p class="meta">…${drops.length - 25} weaker sources hidden</p>`;
    html += `</section>`;
  }

  if(makes.length){
    html += `<section class="blk"><h3>How to craft it</h3>` +
      makes.map(recipeCard).join('') + `</section>`;
  }

  if(fos.length){
    html += `<section class="blk"><h3>Fossil machine</h3><p>` + fos.map(f =>
      `Revives <a href="pokedex.html#${f.result}">${escHtml(f.resultName)}</a>`).join(' · ') +
      `</p></section>`;
  }
  if(sig){
    html += `<section class="blk"><h3>Gym signature item</h3>
      <p>Held by gym leader <a href="trainers.html#${sig.id}">${escHtml(sig.name)}</a> —
      the item marks their gym; see the <a href="trainers.html">Trainers</a> page.</p></section>`;
  }
  if(evos.length){
    html += `<section class="blk"><h3>Evolves Pokémon</h3><p>` +
      evos.map(e => {
        const dex = DATA.speciesDex[e];
        const im = dex ? `<img class="spr" src="sprites/${dex}.png" style="width:22px;height:22px" alt="" loading="lazy" onerror="this.remove()">` : '';
        return `<a class="chip" href="pokedex.html#${e}">${im}${escHtml(DATA.speciesNames[e] || pretty(e))}</a>`;
      }).join(' ') + `</p></section>`;
  }

  if(!drops.length && !makes.length && !mons.length && !fos.length){
    html += `<section class="blk"><p class="none">No recipe or drop source found for
      <b>${escHtml(nameOf(id))}</b> in the indexed pack data.</p>
      <p class="hint">Common reasons: sold in a CobbleDollars shop, given by an NPC,
      obtained from a mod's own code (not data files), or part of an
      <a href="world.html">add-on pack</a> that isn't enabled.</p></section>`;
  }

  if(uses.length){
    const outs = [...new Set(uses.map(r => r.o))];
    html += `<section class="blk"><h3>Used to make (${outs.length})</h3>` +
      outs.slice(0, 50).map(o =>
        `<span class="chip" data-go="${escHtml(o)}">${itemIcon(o, 18)}${escHtml(nameOf(o))}</span>`).join(' ') +
      (outs.length > 50 ? `<p class="meta">…${outs.length - 50} more</p>` : '') +
      `</section>`;
  }

  $('main').innerHTML = html;
  $('main').scrollTop = 0;
  const t = $('#target');
  if(t) t.addEventListener('input', e => {
    target = Math.max(1, parseInt(e.target.value || '1', 10));
    const pos = e.target.selectionStart;
    show(id);
    const nt = $('#target'); if(nt){ nt.focus(); nt.setSelectionRange(pos, pos); }
  });
}

$('#q').addEventListener('input', debounce(e => renderList(search(e.target.value)), 60));
document.addEventListener('click', e => {
  const row = e.target.closest('.row'); if(row) return show(row.dataset.id);
  const chip = e.target.closest('[data-go]'); if(chip) return show(chip.dataset.go);
});
document.addEventListener('keydown', e => {
  const row = e.target.closest('.row');
  if(row && (e.key === 'Enter' || e.key === ' ')){ e.preventDefault(); show(row.dataset.id); }
  if(e.key === '/' && e.target !== $('#q')){ e.preventDefault(); $('#q').focus(); }
});
renderList([]);
hashSelect(show)();
"""


def build_items(payload: dict, counts: dict) -> str:
    body = f"""
<div class="wrap">
  <aside>
    <div class="padbox">
      <h1>Item Index</h1>
      <p class="note">{counts['names']:,} items · {counts['recipes']:,} recipes ·
      {counts['loot']:,} loot entries · Pokémon drops included.
      Numbers are what the pack actually rolls.</p>
    </div>
    <div class="searchbox">
      <input id="q" type="search" placeholder="Search items&nbsp;&nbsp;/" autocomplete="off">
    </div>
    <div id="results" role="listbox" aria-label="Search results">
      <p class="empty">Type to search 7,000+ items.</p>
    </div>
  </aside>
  <main>
    <p class="splash">
      "Where do I actually get this?" — search any item to see
      <b>every source with real probabilities</b>: crafting recipes, loot
      tables, and <b>which Pokémon drop it</b>.<br><br>
      Set a target quantity and each source shows the expected number of
      runs or kills, cheapest first. Type <code>/</code> to search.
    </p>
  </main>
</div>
{_script(ITEMS_JS, _payload(payload))}"""
    return page("Items", "items.html", body, full_height=True)


# ================================================================ Spawn Finder

SPAWNS_JS = r"""
const ids = Object.keys(DATA.species).filter(id => DATA.spawnsBy[id])
  .sort((a, b) => (DATA.species[a].dex ?? 9999) - (DATA.species[b].dex ?? 9999));
let current = null;

// expand an entry's biome refs (#tags and plain ids) minus anti-biomes
function expandBiomes(sp){
  const out = new Set();
  for(const b of sp.biomes || []){
    if(b.startsWith('#')) (DATA.biomeTags[b.slice(1)] || []).forEach(x => out.add(x));
    else out.add(b);
  }
  if(!(sp.biomes || []).length) out.add('(any biome)');
  for(const b of sp.anti || []){
    if(b.startsWith('#')) (DATA.biomeTags[b.slice(1)] || []).forEach(x => out.delete(x));
    else out.delete(b);
  }
  return out;
}

// biome|bucket -> total weight and species set, computed once
const POOL = new Map();
for(const [sid, entries] of Object.entries(DATA.spawnsBy)){
  for(const sp of entries){
    if(sp.addon) continue;             // add-on packs aren't active by default
    for(const biome of expandBiomes(sp)){
      const key = biome + '|' + sp.bucket;
      let slot = POOL.get(key);
      if(!slot){ slot = { total: 0, species: new Set() }; POOL.set(key, slot); }
      slot.total += sp.weight || 0;
      slot.species.add(sid);
    }
  }
}

function renderList(){
  const q = $('#q').value.trim().toLowerCase();
  const legOnly = $('#f-leg').checked;
  const hits = [];
  for(const id of ids){
    const s = DATA.species[id];
    if(legOnly && !s.labels.some(l => l === 'legendary' || l === 'mythical' ||
                                      l === 'ultra_beast' || l === 'paradox')) continue;
    if(q && !(s.name.toLowerCase().includes(q) || id.includes(q))) continue;
    hits.push(id);
  }
  const box = $('#results');
  box.innerHTML = hits.slice(0, 400).map(id => {
    const s = DATA.species[id];
    return `<div class="row" role="option" data-id="${id}"
        aria-selected="${id === current}" tabindex="0">
      ${DATA.species[id].dex ? `<img class="spr" src="renders/${id}.png" style="width:30px;height:30px" alt="" loading="lazy" onerror="if(this.dataset.f){this.remove()}else{this.dataset.f=1;this.src='sprites/${s.dex}.png'}">` : ''}
      <span class="nm">${escHtml(s.name)}</span>
      <span class="ns">${(DATA.spawnsBy[id] || []).length}×</span>
    </div>`;
  }).join('') || '<p class="empty">No spawning species matches. Legendaries without natural spawns are summoned — see <a href="legendaries.html">Legendaries</a>.</p>';
}

function show(id){
  const s = DATA.species[id];
  if(!s) return;
  current = id;
  history.replaceState(null, '', '#' + id);
  renderList();
  const entries = DATA.spawnsBy[id] || [];

  // per-biome best odds: for each (entry, biome), share = weight / pool total
  const rows = [];
  for(const sp of entries){
    for(const biome of expandBiomes(sp)){
      const slot = POOL.get(biome + '|' + sp.bucket);
      const total = sp.addon ? null : (slot ? slot.total : sp.weight);
      rows.push({
        biome, bucket: sp.bucket, weight: sp.weight,
        share: total ? (sp.weight / total) : null,
        rivals: slot ? slot.species.size - 1 : 0,
        level: sp.level, cond: sp.cond, wmult: sp.wmult,
        presets: sp.presets, addon: sp.addon, src: sp.src,
      });
    }
  }
  // keep each biome's best share
  const best = new Map();
  for(const r of rows){
    const k = r.biome + '|' + r.bucket + (r.addon ? '|a' : '');
    if(!best.has(k) || (r.share ?? 0) > (best.get(k).share ?? 0)) best.set(k, r);
  }
  const sorted = [...best.values()].sort((a, b) => (b.share ?? 0) - (a.share ?? 0));

  let html = `<div class="item-head" style="display:flex;gap:18px;align-items:center">
    ${heroImg(id, s.dex, 96, false)}
    <div><h2>${escHtml(s.name)}</h2>
    <div class="meta" style="margin-top:6px">${entries.length} spawn entr${entries.length === 1 ? 'y' : 'ies'}
      · best places to camp, ranked by your share of the local spawn pool
      · <a href="pokedex.html#${id}">full Pokédex page</a></div></div></div>`;

  if(!sorted.length){
    html += `<p class="none">No active natural spawns.</p>
      <p class="hint">If this is a legendary, it's obtained another way — see
      <a href="legendaries.html">Legendaries</a>.</p>`;
  } else {
    const topShare = sorted[0].share ?? 0;
    html += `<section class="blk"><h3>Where to hunt (${sorted.length} biome options)</h3>
      <table class="data"><tr><th>Biome</th><th>Rarity</th><th>Share of pool</th>
      <th>Rivals</th><th>Lv</th><th>Conditions</th></tr>`;
    for(const r of sorted.slice(0, 40)){
      const shareTxt = r.share == null ? '—'
        : (r.share >= 0.1 ? (r.share * 100).toFixed(0) : (r.share * 100).toFixed(1)) + '%';
      const bar = r.share ? `<div class="bar" style="width:90px"><i style="width:${Math.max(3, r.share / (topShare || 1) * 100)}%"></i></div>` : '';
      const notes = [];
      for(const p of r.presets || []){
        const t = DATA.presets[p];
        notes.push(t ? `${escHtml(p)} <span class="meta">(${escHtml(t)})</span>` : escHtml(p));
      }
      if(r.cond) notes.push(escHtml(r.cond));
      if(r.wmult) notes.push(escHtml(r.wmult));
      if(r.addon) notes.push('<span class="badge addon">add-on pack</span>');
      html += `<tr>
        <td>${escHtml(pretty(r.biome))}${r.biome.startsWith('terralith') ? ' <span class="meta">(Terralith)</span>' : ''}</td>
        <td><span class="badge b-${r.bucket}">${r.bucket}</span></td>
        <td>${shareTxt}${bar}</td>
        <td class="meta">${r.rivals}</td>
        <td class="meta">${escHtml(r.level || '?')}</td>
        <td class="meta">${notes.join(' · ') || '—'}</td></tr>`;
    }
    if(sorted.length > 40) html += `</table><p class="meta">…${sorted.length - 40} weaker options hidden</p>`;
    else html += `</table>`;
    html += `<p class="hint">Share of pool = this Pokémon's spawn weight divided by
      the total weight of everything else that can roll in the same rarity bucket
      in that biome. Time/weather/light conditions aren't factored into rivals'
      eligibility, so treat shares as an optimistic ranking, not an exact rate.
      Higher share + fewer rivals = less junk between you and the target.</p></section>`;
  }
  $('main').innerHTML = html;
  $('main').scrollTop = 0;
}

$('#q').addEventListener('input', debounce(renderList, 80));
$('#f-leg').addEventListener('change', renderList);
document.addEventListener('click', e => {
  const row = e.target.closest('.row'); if(row) return show(row.dataset.id);
  const chip = e.target.closest('[data-go]'); if(chip) return show(chip.dataset.go);
});
document.addEventListener('keydown', e => {
  const row = e.target.closest('.row');
  if(row && (e.key === 'Enter' || e.key === ' ')){ e.preventDefault(); show(row.dataset.id); }
  if(e.key === '/' && e.target !== $('#q')){ e.preventDefault(); $('#q').focus(); }
});
renderList();
hashSelect(show)();
"""


def build_spawnfinder(payload: dict, counts: dict) -> str:
    legendaries = sorted(
        (sid for sid, s in payload["species"].items()
         if sid in payload["spawnsBy"]
         and any(l in ("legendary", "mythical", "ultra_beast", "paradox")
                 for l in s.get("labels", []))),
        key=lambda sid: payload["species"][sid].get("dex") or 9999)
    chips = "".join(
        f'<span class="chip" data-go="{esc(sid)}">'
        f'{esc(payload["species"][sid]["name"])}</span>'
        for sid in legendaries[:40])
    body = f"""
<div class="wrap">
  <aside>
    <div class="padbox">
      <h1>Spawn Finder</h1>
      <p class="note">Pick a target — get the exact biomes to camp, ranked by
      your real odds against everything else in the spawn pool. Built from the
      pack's {counts['spawns']:,} active spawn entries.</p>
    </div>
    <div class="searchbox">
      <input id="q" type="search" placeholder="Search species&nbsp;&nbsp;/" autocomplete="off">
    </div>
    <div class="filters">
      <label class="chk"><input type="checkbox" id="f-leg">legendaries &amp; co. only</label>
    </div>
    <div id="results" role="listbox" aria-label="Species"></div>
  </aside>
  <main>
    <p class="splash">
      The spawn isolator: choose a Pokémon and see <b>which biome gives you the
      best shot</b> — its spawn weight as a share of everything competing in
      the same rarity bucket there, with the conditions that gate it.<br><br>
      Naturally-spawning legendaries &amp; co. below; the rest are summoned —
      see <a href="legendaries.html">Legendaries</a>.
    </p>
    <section class="blk" style="padding:0 30px"><h3 style="font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--silt)">Naturally spawning legendaries, mythicals, ultra beasts &amp; paradox</h3>
    <div>{chips}</div></section>
  </main>
</div>
{_script(SPAWNS_JS, _payload(payload))}"""
    return page("Spawn Finder", "spawns.html", body, full_height=True)


# ================================================================ Trainers

TRAINERS_JS = r"""
let current = null;
const ids = Object.keys(DATA.trainers).sort((a, b) =>
  DATA.trainers[a].name.localeCompare(DATA.trainers[b].name));
const nameOf = id => DATA.names[id] || pretty(id);

function seriesOf(id){
  const mob = DATA.mobs[id];
  return mob && mob.series && mob.series.length ? mob.series : [];
}

function rows(){
  const q = $('#q').value.trim().toLowerCase();
  const se = $('#f-series').value;
  const out = [];
  for(const id of ids){
    const t = DATA.trainers[id];
    if(se && !seriesOf(id).includes(se)) continue;
    if(q && !(t.name.toLowerCase().includes(q) || id.includes(q) ||
              t.team.some(m => (m.species || '').includes(q)))) continue;
    out.push(id);
  }
  return out;
}

function renderList(){
  const hits = rows();
  const box = $('#results');
  if(!hits.length){ box.innerHTML = '<p class="empty">No trainer matches.</p>'; return; }
  box.innerHTML = hits.slice(0, 400).map(id => {
    const t = DATA.trainers[id];
    const lv = t.team.length ? Math.max(...t.team.map(m => m.level || 0)) : '';
    return `<div class="row" role="option" data-id="${escHtml(id)}"
       aria-selected="${id === current}" tabindex="0">
      <img class="spr" src="renders/trainers/${escHtml(id)}.png" style="width:26px;height:26px"
        alt="" loading="lazy" onerror="this.remove()">
      <span class="nm">${escHtml(t.name)}</span>
      <span class="ns">${t.team.length}× lv≤${lv}</span>
    </div>`;
  }).join('') + (hits.length > 400 ? `<p class="empty">…${hits.length - 400} more</p>` : '');
}

function show(id){
  const t = DATA.trainers[id];
  if(!t) return;
  current = id;
  history.replaceState(null, '', '#' + encodeURIComponent(id));
  renderList();
  const mob = DATA.mobs[id];

  let html = `<div class="item-head" style="display:flex;gap:18px;align-items:center">
    <img class="spr" src="renders/trainers/${escHtml(id)}.png" style="width:110px;height:110px"
      alt="" onerror="this.remove()">
    <div><h2>${escHtml(t.name)}</h2>
    <div class="id">${escHtml(id)}</div>
    <div style="margin-top:8px">${seriesOf(id).map(s =>
      `<span class="badge">${escHtml((DATA.series[s] || {}).title || s)}</span> `).join('')}</div>
    </div>
  </div>`;

  if(mob){
    const bits = [];
    if(mob.biomes && mob.biomes.length)
      bits.push(`<b>spawn biomes:</b> ${mob.biomes.map(b => escHtml(pretty(b.replace('#','')))).join(', ')}`);
    if(mob.signatureItem)
      bits.push(`<b>signature item:</b> <a class="chip" href="items.html#${encodeURIComponent(mob.signatureItem)}">${itemIcon(mob.signatureItem, 18)}${escHtml(nameOf(mob.signatureItem))}</a>`);
    if(mob.maxDefeats != null && mob.maxDefeats >= 0)
      bits.push(`<b>can be beaten:</b> ${mob.maxDefeats}×`);
    if(mob.spawnWeightFactor === 0)
      bits.push(`<b>does not spawn naturally</b> — found via structure or summon`);
    if(bits.length)
      html += `<section class="blk"><h3>Encounter</h3><p>${bits.join(' · ')}</p></section>`;
  }

  if(t.team.length){
    html += `<section class="blk"><h3>Team (${t.team.length})</h3>`;
    for(const m of t.team){
      const sp = (m.species || '').toLowerCase();
      const dex = DATA.speciesDex[sp];
      const im = heroImg(sp, dex, 44, !!m.shiny);
      const link = DATA.speciesNames[sp]
        ? `<a href="pokedex.html#${sp}">${escHtml(DATA.speciesNames[sp])}</a>`
        : escHtml(pretty(sp));
      html += `<div class="mon">
        <span class="sp">${im}${link}${m.shiny ? ' ✦' : ''}</span>
        <span class="lv">Lv ${m.level ?? '?'}</span>
        ${m.ability ? `<span class="kv">ability <b>${escHtml(m.ability)}</b></span>` : ''}
        ${m.nature ? `<span class="kv">nature <b>${escHtml(m.nature)}</b></span>` : ''}
        ${m.heldItem ? `<span class="kv">holds <b>${escHtml(pretty(m.heldItem))}</b></span>` : ''}
        ${m.moves && m.moves.length ? `<span class="moves">${m.moves.map(v => `<code>${escHtml(v)}</code>`).join('')}</span>` : ''}
      </div>`;
    }
    html += `</section>`;
  }

  if(t.bag && t.bag.length){
    html += `<section class="blk"><h3>Battle bag</h3><p>` + t.bag.map(b =>
      `<span class="chip plain">${itemIcon(b.item, 18)}${escHtml(nameOf(b.item))} ×${b.qty}</span>`).join(' ') + `</p></section>`;
  }
  const rules = Object.entries(t.rules || {});
  if(rules.length){
    html += `<section class="blk"><h3>Battle rules</h3><p class="meta">` +
      rules.map(([k, v]) => `${escHtml(k)}: ${escHtml(JSON.stringify(v))}`).join(' · ') + `</p></section>`;
  }
  html += `<p class="src">data: ${escHtml(t.src)}</p>`;
  $('main').innerHTML = html;
  $('main').scrollTop = 0;
}

$('#q').addEventListener('input', debounce(renderList, 80));
$('#f-series').addEventListener('change', renderList);
document.addEventListener('click', e => {
  const row = e.target.closest('.row'); if(row) return show(row.dataset.id);
});
document.addEventListener('keydown', e => {
  const row = e.target.closest('.row');
  if(row && (e.key === 'Enter' || e.key === ' ')){ e.preventDefault(); show(row.dataset.id); }
  if(e.key === '/' && e.target !== $('#q')){ e.preventDefault(); $('#q').focus(); }
});
renderList();
hashSelect(show)();
"""


def _trainers_guide_html(guide: dict | None, names: dict) -> str:
    """Render the curated gym/series guide as the page's initial view."""
    if not guide:
        return ('<p class="splash">Every trainer battle in the pack, read '
                'from the trainer data itself. Search or filter to begin.</p>')
    out = ['<div class="item-head"><h2>Gyms &amp; Trainers</h2></div>',
           _safe(guide.get("intro", "")),
           f'<section class="blk"><h3>How trainer battles work</h3>'
           f'{_safe(guide.get("mechanics", ""))}</section>']
    for s in guide.get("series", []):
        out.append(f'<section class="blk"><h3>{esc(s.get("title"))} series</h3>')
        if s.get("note"):
            out.append(f'<div class="hint" style="margin-bottom:10px">{_safe(s["note"])}</div>')
        gyms = s.get("gyms", [])
        if gyms:
            out.append('<table class="data"><tr><th>Gym Leader</th><th>Lv</th>'
                       '<th>Badge</th><th>Signature item</th><th>Biomes</th></tr>')
            for g in gyms:
                badge = g.get("badge")
                sig = g.get("signatureItem")
                badge_cell = (f'{icon_img(badge, 20)} <a href="items.html#{esc(badge)}">'
                              f'{esc(names.get(badge) or badge.split(":")[-1].replace("_", " ").title())}</a>'
                              if badge else "—")
                sig_cell = (f'{icon_img(sig, 20)} <a href="items.html#{esc(sig)}">'
                            f'{esc(names.get(sig) or sig.split(":")[-1].replace("_", " ").title())}</a>'
                            if sig else "—")
                biomes = ", ".join(
                    b.split(":")[-1].replace("_", " ").title()
                    for b in (g.get("biomes") or [])) or "—"
                out.append(
                    f'<tr><td><img class="spr" src="renders/trainers/'
                    f'{esc(g["trainerId"])}.png" style="width:30px;height:30px;'
                    f'margin:-6px 6px -6px 0" alt="" loading="lazy" '
                    f'onerror="this.remove()">'
                    f'<a href="#{esc(g["trainerId"])}">{esc(g["name"])}</a></td>'
                    f'<td>{esc(g.get("levels") or "?")}</td>'
                    f'<td>{badge_cell}</td><td>{sig_cell}</td>'
                    f'<td class="meta">{esc(biomes)}</td></tr>')
            out.append("</table>")
        elites = s.get("elite") or []
        if elites:
            chips = " ".join(
                f'<a class="chip" href="#{esc(e["trainerId"])}">{esc(e["name"])}'
                f'{" · Lv " + esc(e["levels"]) if e.get("levels") else ""}</a>'
                for e in elites)
            out.append(f'<p><b>Elite Four:</b> {chips}</p>')
        champ = s.get("champion")
        if champ and champ.get("trainerId"):
            out.append(f'<p><b>Champion:</b> <a class="chip" '
                       f'href="#{esc(champ["trainerId"])}">{esc(champ.get("name") or "?")}'
                       f'{" · Lv " + esc(champ["levels"]) if champ.get("levels") else ""}</a></p>')
        out.append("</section>")
    return "".join(out)


def build_trainers(payload: dict, counts: dict, guide: dict | None = None) -> str:
    opts = "".join(
        f'<option value="{esc(sid)}">{esc(s.get("title") or sid)}</option>'
        for sid, s in sorted(payload["series"].items()))
    guide_html = _trainers_guide_html(guide, payload.get("names", {}))
    body = f"""
<div class="wrap">
  <aside>
    <div class="padbox">
      <h1>Trainers</h1>
      <p class="note">{counts['trainers']:,} trainer teams from Radical Cobblemon
      Trainers + the COBBLEVERSE trainer pack — full movesets, held items and
      battle rules, plus the gym guide. Pick a trainer to see their team;
      the guide below returns on reload.</p>
    </div>
    <div class="searchbox">
      <input id="q" type="search" placeholder="Search trainer / species&nbsp;&nbsp;/" autocomplete="off">
    </div>
    <div class="filters">
      <select id="f-series"><option value="">any series</option>{opts}</select>
    </div>
    <div id="results" role="listbox" aria-label="Trainers"></div>
  </aside>
  <main>{guide_html}</main>
</div>
{_script(TRAINERS_JS, _payload(payload))}"""
    return page("Trainers", "trainers.html", body, full_height=True)
