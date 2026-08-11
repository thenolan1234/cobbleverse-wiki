"""Team Builder: pick up to six Pokémon, see type coverage gaps and how
the team matches up against any upcoming RCT checkpoint trainer."""

from __future__ import annotations

import json

from templates import page, TYPE_COLORS

TYPES = ["normal", "fire", "water", "grass", "electric", "ice", "fighting",
         "poison", "ground", "flying", "psychic", "bug", "rock", "ghost",
         "dragon", "dark", "steel", "fairy"]

# attacker -> {defender: multiplier}, non-1 entries only (Gen 6+ chart)
TYPE_CHART = {
    "normal": {"rock": .5, "ghost": 0, "steel": .5},
    "fire": {"fire": .5, "water": .5, "grass": 2, "ice": 2, "bug": 2,
             "rock": .5, "dragon": .5, "steel": 2},
    "water": {"fire": 2, "water": .5, "grass": .5, "ground": 2, "rock": 2,
              "dragon": .5},
    "electric": {"water": 2, "electric": .5, "grass": .5, "ground": 0,
                 "flying": 2, "dragon": .5},
    "grass": {"fire": .5, "water": 2, "grass": .5, "poison": .5, "ground": 2,
              "flying": .5, "bug": .5, "rock": 2, "dragon": .5, "steel": .5},
    "ice": {"fire": .5, "water": .5, "grass": 2, "ice": .5, "ground": 2,
            "flying": 2, "dragon": 2, "steel": .5},
    "fighting": {"normal": 2, "ice": 2, "poison": .5, "flying": .5,
                 "psychic": .5, "bug": .5, "rock": 2, "ghost": 0, "dark": 2,
                 "steel": 2, "fairy": .5},
    "poison": {"grass": 2, "poison": .5, "ground": .5, "rock": .5,
               "ghost": .5, "steel": 0, "fairy": 2},
    "ground": {"fire": 2, "electric": 2, "grass": .5, "poison": 2,
               "flying": 0, "bug": .5, "rock": 2, "steel": 2},
    "flying": {"electric": .5, "grass": 2, "fighting": 2, "bug": 2,
               "rock": .5, "steel": .5},
    "psychic": {"fighting": 2, "poison": 2, "psychic": .5, "dark": 0,
                "steel": .5},
    "bug": {"fire": .5, "grass": 2, "fighting": .5, "poison": .5,
            "flying": .5, "psychic": 2, "ghost": .5, "dark": 2, "steel": .5,
            "fairy": .5},
    "rock": {"fire": 2, "ice": 2, "fighting": .5, "ground": .5, "flying": 2,
             "bug": 2, "steel": .5},
    "ghost": {"normal": 0, "psychic": 2, "ghost": 2, "dark": .5},
    "dragon": {"dragon": 2, "steel": .5, "fairy": 0},
    "dark": {"fighting": .5, "psychic": 2, "ghost": 2, "dark": .5,
             "fairy": .5},
    "steel": {"fire": .5, "water": .5, "electric": .5, "ice": 2, "rock": 2,
              "steel": .5, "fairy": 2},
    "fairy": {"fire": .5, "fighting": 2, "poison": .5, "dragon": 2,
              "dark": 2, "steel": .5},
}


def checkpoint_chains(mobs: dict, trainers: dict) -> dict:
    """Ordered checkpoint trainers per region, via requiresDefeats depth."""
    regions: dict[str, list] = {}
    for mid, mob in mobs.items():
        region = (mob.get("series") or [None])[0]
        if not region or mid not in trainers:
            continue
        regions.setdefault(region, []).append(mid)

    def depth(mid, mobs, memo):
        if mid in memo:
            return memo[mid]
        req = mobs.get(mid, {}).get("requiresDefeats") or []
        flat = [r for grp in req for r in (grp if isinstance(grp, list) else [grp])]
        memo[mid] = 0 if not flat else 1 + max(
            (depth(r, mobs, memo) for r in flat if r in mobs), default=0)
        return memo[mid]

    out = {}
    for region, ids in regions.items():
        memo: dict = {}
        ids.sort(key=lambda m: (depth(m, mobs, memo), m))
        chain = []
        for mid in ids:
            t = trainers[mid]
            team = [{"s": p["species"], "l": p["level"]}
                    for p in t.get("team", []) if p.get("species")]
            if team:
                chain.append({"id": mid, "n": t["name"],
                              "cap": max(p["l"] for p in team) + 5,
                              "team": team})
        if chain:
            out[region] = chain
    return out


TEAM_JS = r"""
const CHART = DATA.chart, TYPES = DATA.types, TC = DATA.typeColors;
const SP = DATA.species;
let team = [];
try { team = (JSON.parse(localStorage.getItem('cvteam') || '[]') || [])
  .filter(id => SP[id]).slice(0, 6); } catch(e){}

function eff(att, defTypes){
  let m = 1;
  for(const d of defTypes) m *= (CHART[att] && CHART[att][d] !== undefined)
    ? CHART[att][d] : 1;
  return m;
}
function chip(t, small){
  return `<span class="chip" style="border-color:${TC[t]};color:${TC[t]};` +
    (small ? 'font-size:10px;padding:1px 6px' : '') + `">${t}</span>`;
}
function sprite(id, size){
  return `<img src="renders/${id}.png" style="width:${size}px;height:${size}px;` +
    `image-rendering:auto" loading="lazy" onerror="this.remove()">`;
}
function save(){ localStorage.setItem('cvteam', JSON.stringify(team)); }

function renderSlots(){
  const el = document.getElementById('slots');
  el.innerHTML = team.map((id, i) => {
    const s = SP[id];
    return `<div class="slot" onclick="removeMon(${i})" title="Click to remove">
      ${sprite(id, 72)}<b>${s.name}</b>
      <div>${s.t.map(t => chip(t, true)).join('')}</div></div>`;
  }).join('') + (team.length < 6
    ? `<div class="slot empty">+ add via search</div>` : '');
}
window.removeMon = i => { team.splice(i, 1); save(); renderAll(); };

function renderDefense(){
  const el = document.getElementById('defense');
  if(!team.length){ el.innerHTML = '<p class="note">Add Pokémon to see the analysis.</p>'; return; }
  let rows = '';
  for(const att of TYPES){
    let weak = 0, resist = 0, cells = '';
    for(const id of team){
      const m = eff(att, SP[id].t);
      if(m > 1) weak++;
      if(m < 1) resist++;
      const bg = m === 0 ? 'var(--reef)' : m >= 4 ? '#c0392b' : m > 1 ? '#e67e22'
        : m < 1 ? '#27ae60' : 'transparent';
      const label = m === 0 ? '0' : m === .25 ? '¼' : m === .5 ? '½' : m;
      cells += `<td style="text-align:center;background:${bg}22;color:${
        m === 1 ? 'var(--dim)' : 'inherit'}">${m === 1 ? '·' : label}</td>`;
    }
    const gap = weak >= 2 && resist === 0;
    rows += `<tr${gap ? ' style="outline:1px solid #e67e22"' : ''}>` +
      `<td>${chip(att, true)}</td>${cells}` +
      `<td class="meta" style="text-align:center">${weak ? weak + '⚠' : ''}` +
      `${resist ? ' ' + resist + '🛡' : ''}${gap ? ' GAP' : ''}</td></tr>`;
  }
  const heads = team.map(id => `<th>${sprite(id, 28)}</th>`).join('');
  el.innerHTML = `<table class="tb"><thead><tr><th>attack</th>${heads}
    <th>w/r</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function renderOffense(){
  const el = document.getElementById('offense');
  if(!team.length){ el.innerHTML = ''; return; }
  const stabs = new Set();
  team.forEach(id => SP[id].t.forEach(t => stabs.add(t)));
  const uncovered = TYPES.filter(d => ![...stabs].some(a => eff(a, [d]) > 1));
  el.innerHTML = `<p>STAB types: ${[...stabs].map(t => chip(t, true)).join(' ')}</p>
    <p>${uncovered.length
      ? 'No super-effective STAB against: ' + uncovered.map(t => chip(t, true)).join(' ')
      : '<b>Full coverage</b> — every type can be hit super-effectively with STAB.'}</p>`;
}

function renderGym(){
  const region = document.getElementById('gregion').value;
  const sel = document.getElementById('gtrainer');
  const chain = DATA.gyms[region] || [];
  if(sel.dataset.region !== region){
    sel.innerHTML = chain.map((c, i) =>
      `<option value="${i}">${c.n} (cap ${c.cap})</option>`).join('');
    sel.dataset.region = region;
  }
  const c = chain[+sel.value || 0];
  const el = document.getElementById('gymout');
  if(!c){ el.innerHTML = ''; return; }
  let rows = '';
  for(const p of c.team){
    const s = SP[p.s];
    if(!s){ continue; }
    let best = null;
    for(const id of team){
      for(const a of SP[id].t){
        const m = eff(a, s.t);
        if(!best || m > best.m) best = {id, a, m};
      }
    }
    const threats = team.filter(id => s.t.some(a => eff(a, SP[id].t) > 1))
      .map(id => SP[id].name);
    rows += `<tr><td>${sprite(p.s, 40)} <b>${s.name}</b> <span class="meta">
      Lv ${p.l}</span></td><td>${s.t.map(t => chip(t, true)).join('')}</td>
      <td>${best && best.m > 1 ? `${SP[best.id].name} (${chip(best.a, true)} ×${best.m})`
        : best ? '<span class="meta">nothing super-effective</span>' : ''}</td>
      <td class="meta">${threats.length ? 'hits ' + threats.join(', ') : '—'}</td></tr>`;
  }
  el.innerHTML = `<table class="tb"><thead><tr><th>their team</th><th>types</th>
    <th>your best answer</th><th>their STAB threatens</th></tr></thead>
    <tbody>${rows}</tbody></table>
    <p class="note">Level cap while this checkpoint is active: <b>${c.cap}</b>
    (their strongest + 5).</p>`;
}

const q = document.getElementById('tq'), res = document.getElementById('tres');
const ids = Object.keys(SP).sort((a, b) => (SP[a].dex ?? 9999) - (SP[b].dex ?? 9999));
q.addEventListener('input', () => {
  const t = q.value.trim().toLowerCase();
  if(!t){ res.innerHTML = ''; return; }
  const hits = ids.filter(id => SP[id].name.toLowerCase().includes(t) ||
    id.includes(t)).slice(0, 12);
  res.innerHTML = hits.map(id => `<div class="hit" onclick="addMon('${id}')">
    ${sprite(id, 32)} ${SP[id].name}
    <span class="meta">#${SP[id].dex ?? '?'}</span>
    ${SP[id].t.map(x => chip(x, true)).join('')}</div>`).join('');
});
window.addMon = id => {
  if(team.length >= 6 || team.includes(id)) return;
  team.push(id); save(); q.value = ''; res.innerHTML = ''; renderAll();
};

function renderAll(){ renderSlots(); renderDefense(); renderOffense(); renderGym(); }
document.getElementById('gregion').addEventListener('change', renderGym);
document.getElementById('gtrainer').addEventListener('change', renderGym);
renderAll();
"""

_CSS = """
<style>
#slots{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}
.slot{border:1px solid var(--reef);border-radius:8px;padding:10px;width:110px;
  text-align:center;cursor:pointer;background:var(--deep)}
.slot.empty{color:var(--dim);cursor:default;display:flex;align-items:center;
  justify-content:center;min-height:110px}
#tres .hit{padding:5px 8px;cursor:pointer;border-radius:6px;display:flex;
  gap:8px;align-items:center}
#tres .hit:hover{background:var(--reef)}
table.tb{border-collapse:collapse;font-size:13px;margin:10px 0}
table.tb td,table.tb th{padding:4px 8px;border:1px solid var(--reef)}
#tq{width:100%;max-width:420px}
.tbcols{display:grid;grid-template-columns:auto 1fr;gap:26px;align-items:start}
@media(max-width:900px){.tbcols{grid-template-columns:1fr}}
</style>"""


def build_teambuilder(species: dict, mobs: dict, trainers: dict) -> str:
    sp = {}
    for sid, s in species.items():
        if not s.get("types"):
            continue
        sp[sid] = {"name": s["name"], "dex": s.get("dex"),
                   "t": [t for t in s["types"] if t in TYPES]}
    gyms = checkpoint_chains(mobs, trainers)
    payload = json.dumps({"species": sp, "chart": TYPE_CHART, "types": TYPES,
                          "typeColors": TYPE_COLORS, "gyms": gyms},
                         separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    region_opts = "".join(f'<option value="{r}">{r.title()}</option>'
                          for r in ("kanto", "johto", "hoenn", "sinnoh")
                          if r in gyms)
    body = f"""{_CSS}
<div class="padbox" style="max-width:1150px;margin:0 auto">
  <h1>Team Builder</h1>
  <p class="note">Build a team of six, spot defensive gaps, and check the
  matchup against your next checkpoint trainer. Teams save in your browser.</p>
  <p><input id="tq" type="search" placeholder="Add a Pokémon&hellip;"
     autocomplete="off"></p>
  <div id="tres"></div>
  <div id="slots"></div>
  <div class="tbcols">
    <div>
      <h2 id="defense-analysis">Defense</h2>
      <p class="note">How hard each attacking type hits your team
      (⚠ weak · 🛡 resists · GAP = 2+ weak with no resist).</p>
      <div id="defense"></div>
    </div>
    <div>
      <h2 id="offense-coverage">Offense</h2>
      <div id="offense"></div>
      <h2 id="gym-matchup">Checkpoint matchup</h2>
      <p>
        <select id="gregion">{region_opts}</select>
        <select id="gtrainer" data-region=""></select>
      </p>
      <div id="gymout"></div>
    </div>
  </div>
</div>
<script>const DATA={payload};
{TEAM_JS}</script>"""
    return page("Team Builder", "teambuilder.html", body)
