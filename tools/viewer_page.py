"""The interactive 3D structure viewer page (viewer.html)."""

from templates import page

VIEWER_BODY = r"""
<div style="display:flex;flex-direction:column;height:calc(100vh - 45px)">
  <div style="display:flex;gap:14px;align-items:center;padding:10px 18px;
              border-bottom:1px solid var(--reef);flex-wrap:wrap">
    <h1 id="vtitle" style="font-size:16px">3D Structure Viewer</h1>
    <span class="meta">drag to rotate · scroll to zoom · right-drag to pan</span>
    <label class="meta" style="display:flex;align-items:center;gap:8px;
                               margin-left:auto;min-width:260px;flex:0 1 380px">
      roof slice
      <input id="yslice" type="range" min="0" max="1" value="1" step="1"
             style="flex:1;accent-color:var(--tide)">
      <span id="ylabel" style="min-width:5ch;color:var(--tide)">—</span>
    </label>
    <button id="vreset" class="chip" style="cursor:pointer">reset view</button>
    <a id="vback" class="chip" href="structures.html">← all structures</a>
  </div>
  <div id="vwrap" style="flex:1;min-height:0;position:relative">
    <canvas id="vcanvas" style="width:100%;height:100%;display:block"></canvas>
    <div id="vmsg" class="meta" style="position:absolute;top:12px;left:16px"></div>
  </div>
</div>
<script src="lib/three.min.js"></script>
<script src="lib/OrbitControls.js"></script>
<script>
(function(){
  const params = new URLSearchParams(location.search);
  const slug = (params.get('s') || '').replace(/[^a-z0-9-]/g, '');
  const mon = (params.get('p') || '').replace(/[^a-z0-9-]/g, '');
  const msg = document.getElementById('vmsg');
  if(!slug && !mon){ msg.textContent = 'Nothing selected — pick a structure or Pokémon.'; return; }
  document.getElementById('vtitle').textContent =
    (mon || slug).replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  if(mon){
    document.getElementById('vback').href = 'pokedex.html#' + mon;
    document.getElementById('vback').textContent = '← Pokédex page';
    document.querySelector('label.meta').style.display = 'none';  // no roof slice
    const btn = document.createElement('button');
    btn.className = 'chip'; btn.style.cursor = 'pointer';
    btn.id = 'vshiny'; btn.textContent = '✦ shiny';
    document.getElementById('vreset').before(btn);
  }
  msg.textContent = 'Loading…';

  const canvas = document.getElementById('vcanvas');
  const renderer = new THREE.WebGLRenderer({canvas, antialias: true, alpha: true});
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, 2, 0.1, 4000);
  const controls = new THREE.OrbitControls(camera, canvas);
  controls.enableDamping = true;
  window.__v = {renderer, scene, camera, controls};

  function resize(){
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);

  const SHADE = {top: 1.0, bottom: 0.5, px: 0.62, nx: 0.62, pz: 0.8, nz: 0.8};

  const dataUrl = mon ? 'models3d/' + mon + '.json' : 'voxels/' + slug + '.json';
  fetch(dataUrl)
    .then(r => { if(!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(d => mon ? buildMon(d) : build(d))
    .catch(e => { msg.textContent = 'Could not load 3D data (' + e.message +
      '). The 3D viewer needs the site served over http (it works on the hosted wiki).'; });

  function fail(e){
    msg.textContent = 'Viewer error: ' + (e && e.message ? e.message : e);
  }

  function buildMon(d){
    const loader = new THREE.TextureLoader();
    let shiny = false;
    const textures = {};
    function texFor(isShiny, cb){
      const key = isShiny ? 'shiny' : 'normal';
      if(textures[key]) return cb(textures[key]);
      loader.load('models3d/' + mon + (isShiny ? '_shiny' : '') + '.png', t => {
        t.magFilter = THREE.NearestFilter;
        t.minFilter = THREE.NearestFilter;
        t.flipY = true;
        textures[key] = t;
        cb(t);
      }, undefined, () => cb(null));
    }
    const nf = d.s.length;
    const pos = new Float32Array(nf * 6 * 3);
    const uv = new Float32Array(nf * 6 * 2);
    const col = new Float32Array(nf * 6 * 3);
    const order = [0, 1, 2, 0, 2, 3];
    let pi = 0, ui = 0, ci = 0;
    for(let f = 0; f < nf; f++){
      const shade = d.s[f];
      for(const k of order){
        const p = (f * 4 + k) * 3, q = (f * 4 + k) * 2;
        pos[pi++] = d.p[p]; pos[pi++] = d.p[p + 1]; pos[pi++] = d.p[p + 2];
        uv[ui++] = d.u[q] / d.tw;
        uv[ui++] = 1 - d.u[q + 1] / d.th;
        col[ci++] = shade; col[ci++] = shade; col[ci++] = shade;
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    geo.computeBoundingBox();
    const bb = geo.boundingBox;
    const mat = new THREE.MeshBasicMaterial({vertexColors: true,
      side: THREE.DoubleSide, transparent: true, alphaTest: 0.05});
    const mesh = new THREE.Mesh(geo, mat);
    const cx = (bb.min.x + bb.max.x) / 2, cy = (bb.min.y + bb.max.y) / 2,
          cz = (bb.min.z + bb.max.z) / 2;
    mesh.position.set(-cx, -cy, -cz);
    scene.add(mesh);
    texFor(false, t => { if(t){ mat.map = t; mat.needsUpdate = true; } });
    const sb = document.getElementById('vshiny');
    if(sb) sb.addEventListener('click', () => {
      shiny = !shiny;
      sb.style.background = shiny ? 'var(--reef)' : '';
      texFor(shiny, t => { if(t){ mat.map = t; mat.needsUpdate = true; } });
    });
    const span = Math.max(bb.max.x - bb.min.x, bb.max.y - bb.min.y,
                          bb.max.z - bb.min.z);
    const dist = span * 1.6 + 8;
    function resetView(){
      camera.position.set(dist * 0.65, dist * 0.4, -dist * 0.65);
      controls.target.set(0, 0, 0);
      controls.update();
    }
    document.getElementById('vreset').addEventListener('click', resetView);
    resetView();
    resize();
    msg.textContent = nf.toLocaleString() + ' faces';
    (function animate(){
      requestAnimationFrame(animate);
      if(canvas.clientWidth && (canvas.width !== canvas.clientWidth ||
                                canvas.height !== canvas.clientHeight))
        resize();
      controls.update();
      renderer.render(scene, camera);
    })();
  }

  function build(data){
    // block-texture atlas is optional: fall back to avg-color faces
    new THREE.TextureLoader().load('voxels/atlas.png?v=__ATLASV__', t => {
      t.magFilter = THREE.NearestFilter;
      t.minFilter = THREE.NearestFilter;
      t.generateMipmaps = false;
      try { buildScene(data, t); } catch(e){ fail(e); }
    }, undefined, () => {
      try { buildScene(data, null); } catch(e){ fail(e); }
    });
  }

  function buildScene(data, atlas){
    const bin = atob(data.blocks);
    const n = bin.length / 6;
    const bx = new Uint16Array(n), bz = new Uint16Array(n);
    const by = new Uint8Array(n), bs = new Uint8Array(n);
    for(let i = 0; i < n; i++){
      const o = i * 6;
      bx[i] = bin.charCodeAt(o) | (bin.charCodeAt(o + 1) << 8);
      bz[i] = bin.charCodeAt(o + 2) | (bin.charCodeAt(o + 3) << 8);
      by[i] = bin.charCodeAt(o + 4);
      bs[i] = bin.charCodeAt(o + 5);
    }
    const [SX, SY, SZ] = data.size;
    if(SX * SY * SZ > 1.5e8)
      throw new Error('structure too large (' + SX + 'x' + SY + 'x' + SZ + ')');
    const pal = data.palette;
    // textured only if every palette entry has atlas indices AND the loaded
    // sheet actually covers them (a stale cached atlas may be shorter)
    let textured = !!atlas && pal.every(p => p.a);
    if(textured){
      const maxTile = Math.max(...pal.map(p => Math.max(p.a[0], p.a[1])));
      if(((maxTile / 32) | 0) * 16 + 16 > atlas.image.height) textured = false;
    }
    const AW = textured ? atlas.image.width : 1,
          AH = textured ? atlas.image.height : 1;

    // occupancy grid of opaque blocks: face culling + ambient occlusion
    const occ = new Uint8Array(SX * SY * SZ);
    const solid = (x, y, z) =>
      (x >= 0 && y >= 0 && z >= 0 && x < SX && y < SY && z < SZ &&
       occ[(x * SZ + z) * SY + y]) ? 1 : 0;
    for(let i = 0; i < n; i++)
      if(pal[bs[i]].o) occ[(bx[i] * SZ + bz[i]) * SY + by[i]] = 1;

    // per-vertex ambient occlusion; corner flags list each face's quad
    // corners as (min|max, min|max) along its two in-plane axes
    const AOF = [0.5, 0.72, 0.87, 1.0];
    const F00 = [[0, 0], [0, 1], [1, 1], [1, 0]],
          F01 = [[0, 0], [1, 0], [1, 1], [0, 1]];
    function aos(sample, flags){
      const out = [0, 0, 0, 0];
      for(let k = 0; k < 4; k++){
        const da = flags[k][0] ? 1 : -1, db = flags[k][1] ? 1 : -1;
        const s1 = sample(da, 0), s2 = sample(0, db);
        out[k] = AOF[s1 && s2 ? 0 : 3 - s1 - s2 - sample(da, db)];
      }
      return out;
    }
    // tile-local texture corners: sides show texture top at block top
    const UV_TOP = F00.map(([a, b]) => [a, b]),
          UV_BOT = F01.map(([a, b]) => [a, b]),
          UV_PX = F01.map(([a, b]) => [b, 1 - a]),
          UV_NX = F00.map(([a, b]) => [b, 1 - a]),
          UV_PZ = F01.map(([a, b]) => [a, 1 - b]),
          UV_NZ = F00.map(([a, b]) => [a, 1 - b]);

    // build one merged geometry per Y layer -> slicing = visibility toggles
    const layers = new Map();
    function layer(y){
      let L = layers.get(y);
      if(!L){ L = {pos: [], col: [], uv: []}; layers.set(y, L); }
      return L;
    }
    function quad(L, verts, rgb, shade, tile, av, uvc){
      let idx = [0, 1, 2, 0, 2, 3];
      // flip the quad diagonal toward the darker corner pair so AO
      // interpolates without the classic diagonal banding
      if(av && av[0] + av[2] > av[1] + av[3]) idx = [1, 2, 3, 1, 3, 0];
      const u0 = textured ? (tile % 32) * 16 : 0,
            v0 = textured ? ((tile / 32) | 0) * 16 : 0;
      for(const k of idx){
        L.pos.push(verts[k][0], verts[k][1], verts[k][2]);
        const f = shade * (av ? av[k] : 1);
        if(textured){
          L.col.push(f, f, f);
          L.uv.push((u0 + 0.35 + uvc[k][0] * 15.3) / AW,
                    1 - (v0 + 0.35 + uvc[k][1] * 15.3) / AH);
        } else {
          L.col.push(rgb[0] / 255 * f, rgb[1] / 255 * f, rgb[2] / 255 * f);
        }
      }
    }
    for(let i = 0; i < n; i++){
      const x = bx[i], y = by[i], z = bz[i], p = pal[bs[i]];
      const L = layer(y);
      const at = p.a ? p.a[0] : 0, as = p.a ? p.a[1] : 0;
      // top face: never culled, so slicing always shows a solid skin;
      // covered tops skip AO (their occluders vanish when sliced away)
      quad(L, [[x,y+1,z],[x,y+1,z+1],[x+1,y+1,z+1],[x+1,y+1,z]], p.t,
           SHADE.top, at,
           solid(x, y + 1, z) ? null
             : aos((da, db) => solid(x + da, y + 1, z + db), F00), UV_TOP);
      if(!solid(x, y - 1, z))
        quad(L, [[x,y,z],[x+1,y,z],[x+1,y,z+1],[x,y,z+1]], p.t,
             SHADE.bottom, at,
             aos((da, db) => solid(x + da, y - 1, z + db), F01), UV_BOT);
      if(!solid(x + 1, y, z))
        quad(L, [[x+1,y,z],[x+1,y+1,z],[x+1,y+1,z+1],[x+1,y,z+1]], p.s,
             SHADE.px, as,
             aos((da, db) => solid(x + 1, y + da, z + db), F01), UV_PX);
      if(!solid(x - 1, y, z))
        quad(L, [[x,y,z],[x,y,z+1],[x,y+1,z+1],[x,y+1,z]], p.s,
             SHADE.nx, as,
             aos((da, db) => solid(x - 1, y + da, z + db), F00), UV_NX);
      if(!solid(x, y, z + 1))
        quad(L, [[x,y,z+1],[x+1,y,z+1],[x+1,y+1,z+1],[x,y+1,z+1]], p.s,
             SHADE.pz, as,
             aos((da, db) => solid(x + da, y + db, z + 1), F01), UV_PZ);
      if(!solid(x, y, z - 1))
        quad(L, [[x,y,z],[x,y+1,z],[x+1,y+1,z],[x+1,y,z]], p.s,
             SHADE.nz, as,
             aos((da, db) => solid(x + da, y + db, z - 1), F00), UV_NZ);
    }
    const group = new THREE.Group();
    const mat = textured
      ? new THREE.MeshBasicMaterial({vertexColors: true, map: atlas,
          alphaTest: 0.5, side: THREE.DoubleSide})
      : new THREE.MeshBasicMaterial({vertexColors: true,
          side: THREE.DoubleSide});
    const layerMeshes = [];
    for(const [y, L] of layers){
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(L.pos, 3));
      geo.setAttribute('color', new THREE.Float32BufferAttribute(L.col, 3));
      if(textured)
        geo.setAttribute('uv', new THREE.Float32BufferAttribute(L.uv, 2));
      const mesh = new THREE.Mesh(geo, mat);
      mesh.userData.y = y;
      group.add(mesh);
      layerMeshes.push(mesh);
    }
    group.position.set(-SX / 2, -SY / 2, -SZ / 2);
    scene.add(group);

    const slider = document.getElementById('yslice');
    const ylabel = document.getElementById('ylabel');
    slider.max = SY - 1;
    slider.value = SY - 1;
    ylabel.textContent = 'Y ' + (SY - 1);
    slider.addEventListener('input', () => {
      const v = +slider.value;
      ylabel.textContent = 'Y ' + v;
      for(const m of layerMeshes) m.visible = m.userData.y <= v;
    });

    const dist = Math.max(SX, SY, SZ) * 1.7 + 10;
    function resetView(){
      camera.position.set(dist * 0.7, dist * 0.55, dist * 0.7);
      controls.target.set(0, 0, 0);
      controls.update();
    }
    document.getElementById('vreset').addEventListener('click', resetView);
    resetView();
    resize();
    msg.textContent = n.toLocaleString() + ' blocks · ' +
      SX + '×' + SY + '×' + SZ;
    (function animate(){
      requestAnimationFrame(animate);
      // self-heal sizing: hidden/late-layout tabs report 0x0 until visible
      if(canvas.clientWidth && (canvas.width !== canvas.clientWidth ||
                                canvas.height !== canvas.clientHeight))
        resize();
      controls.update();
      renderer.render(scene, camera);
    })();
  }
})();
</script>
"""


def build_viewer() -> str:
    # cache-bust the atlas by its tile count: the sheet is append-only, so
    # the count changes exactly when the image content does
    import json as _json
    import os as _os
    meta = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                         "..", "voxels", "atlas_meta.json")
    try:
        with open(meta) as fh:
            atlas_v = str(_json.load(fh)["count"])
    except OSError:
        atlas_v = "0"
    body = VIEWER_BODY.replace("__ATLASV__", atlas_v)
    return page("3D Viewer", "structures.html", body, full_height=True)
