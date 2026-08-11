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
  const msg = document.getElementById('vmsg');
  if(!slug){ msg.textContent = 'No structure selected — pick one from the Structures page.'; return; }
  document.getElementById('vtitle').textContent =
    slug.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  msg.textContent = 'Loading…';

  const canvas = document.getElementById('vcanvas');
  const renderer = new THREE.WebGLRenderer({canvas, antialias: true, alpha: true});
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, 2, 0.1, 4000);
  const controls = new THREE.OrbitControls(camera, canvas);
  controls.enableDamping = true;

  function resize(){
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);

  const SHADE = {top: 1.0, bottom: 0.5, px: 0.62, nx: 0.62, pz: 0.8, nz: 0.8};

  fetch('voxels/' + slug + '.json')
    .then(r => { if(!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(build)
    .catch(e => { msg.textContent = 'Could not load voxel data (' + e.message +
      '). The 3D viewer needs the site served over http (it works on the hosted wiki).'; });

  function build(data){
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
    const pal = data.palette;
    // occupancy of opaque blocks for face culling
    const occ = new Set();
    for(let i = 0; i < n; i++)
      if(pal[bs[i]].o) occ.add(bx[i] + '|' + by[i] + '|' + bz[i]);

    // build one merged geometry per Y layer -> slicing = visibility toggles
    const layers = new Map();
    function layer(y){
      let L = layers.get(y);
      if(!L){ L = {pos: [], col: []}; layers.set(y, L); }
      return L;
    }
    function quad(L, verts, rgb, shade){
      const r = rgb[0] / 255 * shade, g = rgb[1] / 255 * shade,
            b = rgb[2] / 255 * shade;
      const idx = [0, 1, 2, 0, 2, 3];
      for(const k of idx){
        L.pos.push(verts[k][0], verts[k][1], verts[k][2]);
        L.col.push(r, g, b);
      }
    }
    for(let i = 0; i < n; i++){
      const x = bx[i], y = by[i], z = bz[i], p = pal[bs[i]];
      const L = layer(y);
      // top face: never culled, so slicing always shows a solid skin
      quad(L, [[x,y+1,z],[x,y+1,z+1],[x+1,y+1,z+1],[x+1,y+1,z]], p.t, SHADE.top);
      if(!occ.has(x + '|' + (y-1) + '|' + z))
        quad(L, [[x,y,z],[x+1,y,z],[x+1,y,z+1],[x,y,z+1]], p.t, SHADE.bottom);
      if(!occ.has((x+1) + '|' + y + '|' + z))
        quad(L, [[x+1,y,z],[x+1,y+1,z],[x+1,y+1,z+1],[x+1,y,z+1]], p.s, SHADE.px);
      if(!occ.has((x-1) + '|' + y + '|' + z))
        quad(L, [[x,y,z],[x,y,z+1],[x,y+1,z+1],[x,y+1,z]], p.s, SHADE.nx);
      if(!occ.has(x + '|' + y + '|' + (z+1)))
        quad(L, [[x,y,z+1],[x+1,y,z+1],[x+1,y+1,z+1],[x,y+1,z+1]], p.s, SHADE.pz);
      if(!occ.has(x + '|' + y + '|' + (z-1)))
        quad(L, [[x,y,z],[x,y+1,z],[x+1,y+1,z],[x+1,y,z]], p.s, SHADE.nz);
    }
    const group = new THREE.Group();
    const mat = new THREE.MeshBasicMaterial({vertexColors: true, side: THREE.DoubleSide});
    const layerMeshes = [];
    for(const [y, L] of layers){
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(L.pos, 3));
      geo.setAttribute('color', new THREE.Float32BufferAttribute(L.col, 3));
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
      controls.update();
      renderer.render(scene, camera);
    })();
  }
})();
</script>
"""


def build_viewer() -> str:
    return page("3D Viewer", "structures.html", VIEWER_BODY, full_height=True)
