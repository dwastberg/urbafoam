# Urbafoam

Urbafoam generates and post-processes OpenFOAM cases for urban wind analysis. The generated cases
target OpenFOAM v2606 (the ESI-OpenCFD release), available from [OpenFOAM.com](https://www.openfoam.com/).
On macOS, [OpenFOAM.app](https://github.com/gerlero/openfoam-app) works. The generated cases are
incompatible with the OpenFOAM Foundation releases from OpenFOAM.org. Install OpenFOAM and run the
generated scripts from an OpenFOAM environment.

Urbafoam is designed for quick, indicative studies of urban wind comfort. It makes simplifying
assumptions to speed up simulations, and their applicability depends on the case. Have someone with
CFD expertise review the results before relying on them for important decisions.

## Installation

Urbafoam uses [uv](https://docs.astral.sh/uv/) and requires Python 3.11 or newer.

```sh
uv sync
uv run urbafoam --help
```

## Quick start

```sh
uv run urbafoam setup --quality quick --model /path/to/buildings.stl outdir
```

The quality preset can be `quick` or `normal`. The model can be a 3D mesh (STL, OBJ, PLY, OFF,
GLB/GLTF) or building footprints (SHP, GeoJSON, GPKG) with a height attribute (`--height`,
default `height`). Footprints are extruded and merged into one
watertight mesh, and their coordinate reference system is kept for the post-processing output.
Surrounding buildings (`--surround`) are meshed more coarsely than the primary model.

### Model preparation

The `[models]` section of `urbafoam.toml` controls how Urbafoam prepares models for meshing.

- The ground is a plane at height 0, at the base of the primary model. Models in map coordinates are
  moved next to the origin (`offset`), and the results are moved back to the coordinates of the model.
- Urbafoam repairs 3D meshes by filling holes, orienting triangles outwards, and merging overlapping
  parts. It reports parts that stay open, as `snappyHexMesh` can leave cells inside them.
- Urbafoam cleans up footprints at the finest cell size near the buildings (`min_feature_size`). It
  closes gaps between neighbouring buildings narrower than half that size and removes smaller
  courtyards and buildings.
- Buildings are extended 1 m below the ground, so they cut through it.
- Urbafoam omits surrounding buildings further than `surrounding_radius` from the primary model
  and those that overlap the primary model.

Watertight, error-free models give the best results.

### Configuring and running cases

Setup generates a directory for each wind direction in `outdir`, along with a `RunAllCases` script
that runs the simulations for all wind directions.

The file `urbafoam.toml` contains all the simulation settings, with every default written out.
Edit the file and rerun setup to regenerate the cases. Setup preserves the comments.

```sh
uv run urbafoam setup outdir
```

Each wind direction is a standard OpenFOAM case. Its settings are collected in `system/caseParameters`
(domain, mesh refinement, solver controls, number of processes) and `0.orig/include/ABLConditions`
(wind profile and roughness), which the other OpenFOAM files read. Edit these to change a single
case, or edit `urbafoam.toml` and rerun setup to regenerate all of them.

Run each case with `./Allrun`, or run one stage at a time with `./Allrun mesh`, `./Allrun solve`,
and `./Allrun sample`. The script runs in parallel when `nProcs` is above 1 and stops at the first
step that fails. See the `log.*` files for details. Add `-v` or `--verbose` (for example,
`./Allrun -v solve`) to print each step's log to the terminal while it runs. The mesh stage ends
with `checkMesh` and warns if the mesh fails its quality checks or `snappyHexMesh` stops refining
at `maxGlobalCells`. Setup prints an estimate of the mesh size of each case and warns when it is
above `maxGlobalCells`.

The `[snappy]` preset refines the outer domain to level 1 in `quick` and level 2 in `normal`.
The central ground bands extend to 3 m and 12 m, with levels `[4, 3]` in `quick` and `[5, 3]`
in `normal`. `resolveFeatureAngle` defaults to 30 degrees to help snapping capture building
corners. It also controls where the higher surface refinement level applies when the minimum and
maximum levels differ.

Set `addLayers = true` to request `SurfaceLayers` layers on the ground and building walls.
Layers are disabled by default. When rerunning setup with the same preset, values in the saved
config take precedence over its defaults.

Before running `RunAllCases`, open one of the wind-direction directories and run `./Allrun mesh`
to load and mesh the STL file. Inspect the resulting mesh with the optional browser preview or
ParaView. If it looks good, run `./RunAllCases` from `outdir`.

### Optional browser preview

Install the viewer once from the repository root and open a generated wind-direction case.

```sh
npm --prefix urbafoam/preview ci
uv run urbafoam preview outdir/270
```

The **Setup** tab opens immediately after case generation. It displays the case-local building
surfaces, wind tunnel, wind direction and optional central refinement box. Drag to orbit,
Shift-drag to pan, or scroll to zoom. Use **Fit to buildings** to return to the primary model.

For the **Snappy mesh** tab, launch the preview from an OpenFOAM environment and run
`./Allrun mesh` in the case directory. Select the tab (or **Retry** if it was already open)
to inspect the snapped boundary. The camera stays in place as you switch tabs. Toggle
individual patches and face edges to compare the snapped surfaces with the setup geometry.

The viewer uses `foamToVTK` on demand and serves boundary geometry on localhost. Parallel
cases use the processor count recorded by `snappyHexMesh`. Temporary exports are discarded
when the preview closes. Use `--no-browser` to print the URL without launching a browser.
The other Urbafoam commands work without npm or the viewer dependencies.

### Post-processing

After all cases have run successfully, run the following command to calculate wind speedup.
Use `--format` to select `csv`, `geojson`, `shp`, or `gpkg` output.

```sh
uv run urbafoam postprocess outdir
```

## Development

```sh
uv run pytest
```

The regression tests compare a full setup and post-processing run against `tests/golden`. After an
intended change in output, regenerate the reference files with
`uv run python -m tests.make_golden` and review the diff.
