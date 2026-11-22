const {vtkActor, vtkMapper} = vtk.Rendering.Core;
const {vtkGenericRenderWindow} = vtk.Rendering.Misc;
const {vtkCubeSource, vtkArrowSource} = vtk.Filters.Sources;
const {vtkSTLReader} = vtk.IO.Geometry;
const {vtkXMLPolyDataReader} = vtk.IO.XML;

const el = id => document.getElementById(id);
const colors = {
  primary: [0.33, 0.62, 0.67], surroundings: [0.60, 0.69, 0.73],
  ground: [0.78, 0.80, 0.77], outer: [0.55, 0.68, 0.76],
  tunnel: [0.37, 0.47, 0.50], refinement: [0.84, 0.47, 0.19],
};

function notice(message, retry = false) {
  el('message').textContent = message;
  el('retry').hidden = !retry;
  el('notice').hidden = !message;
}

async function request(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || `Could not load ${url} (HTTP ${response.status})`);
  }
  return response;
}

function checkbox(parent, text, checked, change) {
  const label = document.createElement('label');
  const input = document.createElement('input');
  input.type = 'checkbox';
  input.checked = checked;
  input.onchange = () => change(input.checked);
  label.append(input, text);
  parent.append(label);
}

async function start() {
  const scene = await (await request('/api/setup')).json();
  el('case').textContent = `Case ${scene.name}`;
  const view = vtkGenericRenderWindow.newInstance({background: [0.92, 0.95, 0.96]});
  view.setContainer(el('viewport'));
  new ResizeObserver(() => view.resize()).observe(el('viewport'));
  const renderer = view.getRenderer();
  const render = () => {
    renderer.resetCameraClippingRange();
    view.getRenderWindow().render();
  };

  function actorFor(data, color) {
    const mapper = vtkMapper.newInstance({scalarVisibility: false});
    mapper.setInputData(data);
    const actor = vtkActor.newInstance();
    actor.setMapper(mapper);
    actor.getProperty().setColor(...color);
    actor.getProperty().setEdgeColor(0.16, 0.25, 0.27);
    renderer.addActor(actor);
    return actor;
  }

  function guide(label, actor, visible) {
    actor.setVisibility(visible);
    checkbox(el('guides'), label, visible, enabled => {
      actor.setVisibility(enabled);
      render();
    });
  }

  function outline(bounds, color) {
    const cube = vtkCubeSource.newInstance({generateLines: true, generateFaces: false});
    cube.setBounds(bounds);
    return actorFor(cube.getOutputData(), color);
  }

  guide('Wind tunnel', outline(scene.domain, colors.tunnel), true);
  guide('Central refinement box', outline(scene.refinement, colors.refinement), false);
  const arrow = actorFor(vtkArrowSource.newInstance().getOutputData(), colors.refinement);
  const [xmin, xmax, ymin, ymax, zmin, zmax] = scene.domain;
  arrow.setPosition(xmin, (ymin + ymax) / 2, zmin + (zmax - zmin) * 0.15);
  const length = (xmax - xmin) * 0.12;
  arrow.setScale(length, length, length);
  guide('Wind direction', arrow, true);

  const models = scene.models.map((item, i) => ({
    ...item, color: i ? colors.surroundings : colors.primary, visible: true, mode: 'setup',
  }));
  let patches = [];
  let mode = 'setup';
  let revision = 0;

  function show(layer) {
    const current = mode === 'mesh' ? patches : models;
    layer.actor?.setVisibility(current.includes(layer) && layer.visible);
  }

  async function load(layer) {
    if (!layer.pending && !layer.actor) {
      layer.pending = (async () => {
        const buffer = await (await request(layer.url)).arrayBuffer();
        const reader = (layer.mode === 'setup' ? vtkSTLReader : vtkXMLPolyDataReader).newInstance();
        reader.parseAsArrayBuffer(buffer);
        const data = reader.getOutputData();
        if (!data?.getNumberOfPoints()) throw new Error(`No geometry in ${layer.name}`);
        layer.actor = actorFor(data, layer.color);
        layer.actor.getProperty().setEdgeVisibility(layer.mode === 'mesh' && el('edges').checked);
        show(layer);
      })().finally(() => { layer.pending = null; });
    }
    await layer.pending;
  }

  async function select(next) {
    const version = ++revision;
    mode = next;
    const mesh = mode === 'mesh';
    el('setup').setAttribute('aria-pressed', String(!mesh));
    el('mesh').setAttribute('aria-pressed', String(mesh));
    el('edge-row').hidden = !mesh;
    el('layer-title').textContent = mesh ? 'Boundary patches' : 'Models';
    el('layers').replaceChildren();
    for (const layer of [...models, ...patches]) layer.actor?.setVisibility(false);
    render();
    notice(mesh ? 'Loading snapped boundary…' : 'Loading models…');
    try {
      if (mesh) {
        const items = await (await request('/api/mesh')).json();
        if (version !== revision) return;
        const previous = new Map(patches.map(layer => [layer.url, layer]));
        const nextPatches = items.map(item => {
          const model = models.find(m => m.name === item.name);
          const ground = item.name === 'ground';
          return previous.get(item.url) || {
            ...item, visible: Boolean(model || ground), mode,
            color: model?.color || (ground ? colors.ground : colors.outer),
          };
        });
        for (const old of patches) {
          if (!nextPatches.includes(old) && old.actor) renderer.removeActor(old.actor);
        }
        patches = nextPatches;
      }
      const layers = mesh ? patches : models;
      for (const layer of layers) {
        checkbox(el('layers'), layer.name, layer.visible, async enabled => {
          layer.visible = enabled;
          try {
            if (enabled) await load(layer);
            show(layer);
            render();
          } catch (error) {
            if (revision === version) notice(error.message, true);
          }
        });
      }
      await Promise.all(layers.filter(layer => layer.visible).map(load));
      if (revision !== version) return;
      layers.forEach(show);
      render();
      notice('');
    } catch (error) {
      if (revision === version) notice(error.message, true);
    }
  }

  function fitBuildings() {
    if (models[0].actor) renderer.resetCamera(models[0].actor.getBounds());
    else renderer.resetCamera(scene.refinement);
    render();
  }

  el('edges').onchange = () => {
    for (const patch of patches) patch.actor?.getProperty().setEdgeVisibility(el('edges').checked);
    render();
  };
  el('fit').onclick = fitBuildings;
  el('setup').onclick = () => select('setup');
  el('mesh').onclick = () => select('mesh');
  el('retry').onclick = () => select(mode);
  const camera = renderer.getActiveCamera();
  camera.setPosition(1, -1.6, 1);
  camera.setViewUp(0, 0, 1);
  await select('setup');
  fitBuildings();
  for (const id of ['fit', 'setup', 'mesh']) el(id).disabled = false;
}

start().catch(error => notice(error.message));
