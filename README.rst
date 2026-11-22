
Urbafoam
========
A tool for generating and post processing OpenFOAM cases for urban wind analysis. The generated cases
target OpenFOAM v2606 from https://www.openfoam.com/ (the ESI-OpenCFD release; on macOS
`OpenFOAM.app <https://github.com/gerlero/openfoam-app>`_ works). They are not compatible with the
OpenFOAM.org (Foundation) releases. You must have OpenFOAM installed and working to use this, and run
the generated scripts from an OpenFOAM environment. Urbafoam is primarily designed for doing quick indicative studies of urban wind comfort
and will make certain assumptions and take certain shortcuts to speed up the simulation, and while these should
work in the general case they might not always be correct in your case. If you're going to be using the results for something important you should get someone that knows CFD to look it over


Installation

Urbafoam is managed with `uv <https://docs.astral.sh/uv/>`_ and needs Python 3.11 or newer:

    uv sync
    uv run urbafoam --help

Quick start

    urbafoam setup --quality (quick|normal) --model /path/to/buildings.stl outdir

where `buildings.stl` is a 3d model of the buildings you want to run your wind simulation on.
The model can be a 3D mesh (stl, obj, ply, off, glb/gltf) or building footprints (shp, geojson, gpkg)
with a height attribute (``--height``, default ``height``). Footprints are extruded and merged into one
watertight mesh, and their coordinate reference system is kept for the post-processing output.
Surrounding buildings (``--surround``) are meshed more coarsely than the primary model.

Urbafoam prepares the models for meshing (the settings are in the ``[models]`` section of ``urbafoam.toml``):

* The ground is a plane at height 0, at the base of the primary model. Models in map coordinates are
  moved next to the origin (``offset``), and the results are moved back to the coordinates of the model.
* 3D meshes are repaired: holes filled, triangles oriented outwards and overlapping parts merged.
  Parts that stay open are reported, as snappyHexMesh can leave cells inside them.
* Footprints are cleaned up at the finest cell size near the buildings (``min_feature_size``): gaps
  between neighbouring buildings narrower than half of it are closed, and smaller courtyards and buildings removed.
* Buildings are extended 1 m below the ground, so they cut through it.
* Surrounding buildings further than ``surrounding_radius`` from the primary model are left out, and
  so are those that overlap the primary model.

Watertight, error free models still give the best results.

This will generate set of files and folders in `outdir` with default settings.

The file `urbafoam.toml` contains the settings for the simulations, with every default written out.
To change any of them you can edit this file (comments are kept) and rerun

    urbafoam setup outdir

and it will regenerate the case base on the changes you've made.
Your out directory will also contain a directory for each wind direction and a script RunAllCases
runs the simulation for all the wind directions.

Each wind direction is a standard OpenFOAM case. Its settings are collected in ``system/caseParameters``
(domain, mesh refinement, solver controls, number of processes) and ``0.orig/include/ABLConditions``
(wind profile and roughness), which the other OpenFOAM files read. Edit these to change a single
case, or edit ``urbafoam.toml`` and rerun ``urbafoam setup`` to regenerate all of them.

Each case is run with ``./Allrun``, or one stage at a time with ``./Allrun mesh``, ``./Allrun solve`` and
``./Allrun sample``. It runs in parallel when ``nProcs`` is above 1 and stops at the first step that
fails (see the ``log.*`` files). The mesh stage ends with ``checkMesh`` and warns if the mesh fails its
quality checks or snappyHexMesh stopped refining at ``maxGlobalCells``. ``urbafoam setup`` prints an
estimate of the mesh size of each case, and warns when it is above ``maxGlobalCells``.

Before running RunAllCases it's a good idea to cd into one of the wind directions and run ``./Allrun mesh``,
which loads and meshes the .stl file.
If this runs without error you can use `paraview` to view the resulting mesh.  If it looks good you can run RunAllCases
to run the whole simulation

Once all the cases have run successfully you can run

    urbafoam postprocess outdir

to postprocess the cases and get the wind speedup results as csv, geojson, shp or gpkg (``--format``).

Development

    uv run pytest

The regression tests compare a full setup/postprocess run against ``tests/golden``. After an intended
change in output, regenerate it with ``uv run python -m tests.make_golden`` and review the diff.





