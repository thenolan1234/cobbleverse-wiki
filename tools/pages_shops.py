"""Shops page: CobbleDollars merchants, the base Cobble Merchant and
what the bank buys from you. All prices come straight from the pack:
config/cobbledollars/*.json + the shopkeeper NPCs baked into the store
structure NBTs."""

from templates import page, esc, icon_img, slugify

_WHERE = {
    "store_workers": "Store",
    "store_workers_random": "Store (rotating)",
    "relic_store_workers": "Relic Store",
    "relic_store_workers_random": "Relic Store (rotating)",
    "farmers_market": "Farmers Market",
    "one_off": "Poké Mart",
}

_CSS = """
<style>
.shopgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));
  gap:12px;margin:14px 0}
.shopcard{border:1px solid var(--reef);border-radius:8px;background:var(--deep)}
.shopcard summary{cursor:pointer;padding:10px 12px;font-weight:600;
  display:flex;gap:8px;align-items:center;flex-wrap:wrap;list-style:none}
.shopcard summary::-webkit-details-marker{display:none}
.shopcard summary .meta{font-weight:400}
.shopcard table{width:100%;border-collapse:collapse;font-size:13px}
.shopcard td{padding:3px 12px;border-top:1px solid var(--reef)}
.shopcard td.price{text-align:right;white-space:nowrap;color:var(--amber)}
.shopcard td.stk{text-align:right;color:var(--dim);width:4ch}
.shopcard img.spr{vertical-align:-4px;margin-right:4px}
.selltable td.price{text-align:right;color:var(--amber)}
#shopq{width:100%;max-width:420px}
.nomatch{display:none!important}
</style>"""

_JS = r"""
<script>
(function(){
  const q = document.getElementById('shopq');
  const cards = [...document.querySelectorAll('.shopcard')];
  const hay = cards.map(c => c.textContent.toLowerCase());
  q.addEventListener('input', () => {
    const t = q.value.trim().toLowerCase();
    cards.forEach((c, i) => {
      const hit = !t || hay[i].includes(t);
      c.classList.toggle('nomatch', !hit);
      if(t && hit) c.open = true;
      else if(!t) c.open = false;
    });
  });
})();
</script>"""


def _offer_rows(offers, name_of) -> str:
    rows = []
    for o in offers:
        nm = name_of(o["item"])
        qty = f" ×{o['count']}" if o.get("count", 1) > 1 else ""
        stock = o.get("stock") or ""
        rows.append(
            f"<tr><td>{icon_img(o['item'], 18)}"
            f"<a href='items.html#{esc(o['item'])}'>{esc(nm)}</a>{qty}</td>"
            f"<td class='price'>${o['price']:,}</td>"
            f"<td class='stk'>{stock}</td></tr>")
    return "".join(rows)


def build_shops(shops: dict, name_of) -> str:
    merchants = shops.get("merchants", [])
    default = shops.get("default", [])
    bank = shops.get("bank", [])

    cards = []
    for m in merchants:
        where = " ".join(f"<span class='chip'>{esc(_WHERE.get(w, w))}</span>"
                         for w in m.get("where", []))
        addon = ("<span class='chip' style='color:var(--amber)'>add-on</span>"
                 if m.get("addon") else "")
        cards.append(f"""
<details class="shopcard" id="{slugify(m['name'])}">
  <summary>{esc(m['name'])}
    <span class="meta">{len(m['offers'])} items</span>{where}{addon}</summary>
  <table><tbody>{_offer_rows(m['offers'], name_of)}</tbody></table>
</details>""")

    default_html = []
    for cat in default:
        default_html.append(f"""
<details class="shopcard" id="base-{slugify(cat['category'])}">
  <summary>{esc(cat['category'])}
    <span class="meta">{len(cat['items'])} items · base merchant</span></summary>
  <table><tbody>{_offer_rows(
      [dict(i, stock=0, count=1) for i in cat['items']], name_of)}</tbody></table>
</details>""")

    sell_rows = "".join(
        f"<tr><td>{icon_img(e['item'], 18)}"
        f"<a href='items.html#{esc(e['item'])}'>{esc(name_of(e['item']))}</a></td>"
        f"<td class='price'>${e['price']:,}</td></tr>"
        for e in sorted(bank, key=lambda e: -e["price"]))

    n_offers = sum(len(m["offers"]) for m in merchants)
    body = f"""{_CSS}
<div class="padbox" style="max-width:1100px;margin:0 auto">
  <h1>Shops &amp; Economy</h1>
  <p class="note">{len(merchants)} named shopkeepers · {n_offers:,} offers ·
  {len(bank)} sellable items — prices read directly from the pack's
  CobbleDollars data. Earn money by defeating trainers and selling to the
  bank; see <a href="mechanics.html">Mechanics</a> for the money loop.</p>
  <p><input id="shopq" type="search"
     placeholder="Filter shops by merchant or item&hellip;" autocomplete="off"></p>

  <h2 id="shopkeepers">Named shopkeepers</h2>
  <p class="note">Found in the store buildings and Farmers Markets that
  generate in villages and towns. “Rotating” variants stock a random
  selection per store.</p>
  <div class="shopgrid">{''.join(cards)}</div>

  <h2 id="base-merchant">Base Cobble Merchant</h2>
  <p class="note">The default merchant inventory (also the Poké Mart
  fallback stock).</p>
  <div class="shopgrid">{''.join(default_html)}</div>

  <h2 id="selling">Selling to the bank</h2>
  <p class="note">Best sell prices first — this is the full list of what
  the bank buys.</p>
  <div class="shopcard" style="max-width:560px">
  <table class="selltable"><tbody>{sell_rows}</tbody></table>
  </div>
</div>
{_JS}"""
    return page("Shops", "shops.html", body)
