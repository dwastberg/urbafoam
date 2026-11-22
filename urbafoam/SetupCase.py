import logging
import warnings
from pathlib import Path

import numpy as np
import pystache
import shapely.affinity

from .BlockMesh import setup_windtunnel
from .BuildingMesh import BuildingMesh, foam_name
from .Config import save_config
from .Controls import setup_controls
from .DataConversion import (GROUND_TOLERANCE, MESH_FORMATS, crop_surroundings, footprint_outline,
                             load_building_model, repair_mesh, resolve_offset, sink_into_ground)
from .Enums import Quality, MeshTypes
from .InitialConditions import setup_initial_conditions
from .MeshEstimate import estimate_cells, parse_levels
from .Paths import case_dir_name
from .SamplePoints import generate_sample_points, setup_samplepoint
from .Scheme import setup_scheme
from .SnappyHexMesh import setup_snappy

logger = logging.getLogger(__name__)


def setupCase(config, out_dir, doc=None):
    """Generate one OpenFOAM case per wind direction in `out_dir` from a validated UrbafoamConfig.

    `doc` is the tomlkit document the config was read from, so comments survive when the resolved
    config is written back to `<out_dir>/urbafoam.toml`.
    """
    out_dir = Path(out_dir).expanduser()
    out_dir.mkdir(exist_ok=True, parents=True)
    models = config.models
    if models.primary_buildings is None:
        raise ValueError("no building model given: use --model or set primary_buildings in [models]")

    buildingMesh, surroundingMesh, crs = prepare_building_models(config)
    if crs is not None and models.crs is None:
        models.crs = crs
    mesh_dir = out_dir / "data" / "building_mesh"
    mesh_dir.mkdir(exist_ok=True, parents=True)
    for model in (buildingMesh, surroundingMesh):
        if model is not None:
            model.save(mesh_dir)

    postprocess = config.postprocess
    if postprocess.samplePoints is not None:
        sample_points_file = Path(postprocess.samplePoints).expanduser()
        if not sample_points_file.is_file():
            raise FileNotFoundError(f"Can't find sample points file {sample_points_file}")
        # given in model coordinates
        sample_points = np.loadtxt(sample_points_file, ndmin=2) + np.asarray(buildingMesh.offset)
    else:
        central_hull = buildingMesh.mesh_convex_hull(rotated=False).buffer(postprocess.sampleBuffer)
        sample_points = generate_sample_points(central_hull, postprocess.sampleSpacing)

    np.savetxt(out_dir / "sample_points.txt", sample_points)
    sampling_heights = postprocess.sampleHeights or [0]
    quality = config.quality_level
    procs = config.parallel.procs

    for w in config.wind.wind_directions:
        case_dir = out_dir / case_dir_name(w)
        rot_matrix = buildingMesh.rotate_and_save_mesh(w, case_dir)
        if surroundingMesh is not None:
            surroundingMesh.rotate_and_save_mesh(w, case_dir)
            surrounding_bounds = surroundingMesh.rotated_bounds
        else:
            surrounding_bounds = buildingMesh.rotated_bounds
        windtunnel_data = setup_windtunnel(config.windtunnel, quality, buildingMesh.rotated_bounds,
                                           surrounding_bounds, 0)
        snappy_data = setup_snappy(config.snappy, postprocess.sampleBuffer, windtunnel_data,
                                   [buildingMesh, surroundingMesh])
        check_mesh_size(w, windtunnel_data, snappy_data, [buildingMesh, surroundingMesh], config.snappy)
        if surroundingMesh is not None:
            _check_inside_domain(w, surroundingMesh.rotated_bounds, windtunnel_data)
        case_data = {**windtunnel_data,
                     **snappy_data,
                     **setup_controls(config.controls),
                     **setup_initial_conditions(config.initial_conditions),
                     **setup_scheme(config.scheme),
                     **setup_samplepoint(sample_points, rot_matrix, buildingMesh.centerpoint, sampling_heights)}
        case_data['usePotentialFoam'] = 'true' if quality == Quality.QUICK else 'false'
        case_data['procCount'] = procs

        write_case_files(case_data, case_dir)

    save_config(config, out_dir, doc)
    create_run_all_cases_script(out_dir, config.wind.wind_directions)


def finest_cell_near_buildings(config):
    """Size of the finest cells snappyHexMesh makes along the primary buildings (on their surfaces,
    in the analysis area or near the ground there), in m. Feature edges are left out: they are
    refined further only along the edges."""
    snappy = config.snappy
    level = max(parse_levels(snappy.PrimaryModelRefinementLevel)[0], snappy.CentralRefinement,
                max(snappy.verticalCentralRefinement))
    return config.windtunnel.cell_size / 2 ** level


def prepare_building_models(config):
    """Load the building models and make them ready for snappyHexMesh.

    Returns (primary BuildingMesh, surrounding BuildingMesh or None, CRS of the primary model or None).
    Both models are moved by the same offset (see ModelsConfig.offset), mesh models are repaired,
    footprints cleaned up, the buildings extended below the ground and the surroundings cropped.
    """
    models = config.models
    if models.min_feature_size == 'auto':
        min_feature = finest_cell_near_buildings(config)
    else:
        min_feature = models.min_feature_size

    primary_path = Path(models.primary_buildings)
    primary, crs = load_building_model(primary_path, models.height_attribute, min_feature)
    offset = resolve_offset(models.offset, primary)
    primary.apply_translation(offset)
    if primary_path.suffix.lower() in MESH_FORMATS:
        primary = repair_mesh(primary, primary_path.name)
    base = primary.bounds[0][2]
    if abs(base) > GROUND_TOLERANCE:
        warnings.warn(f"the ground of the domain is at z = 0, but the base of {primary_path.name} is at "
                      f"z = {base:.2f} after the offset {offset}: the buildings will be cut off or float")
    primary_height = primary.bounds[1][2]
    primary_outline = footprint_outline(primary)
    primary = sink_into_ground(primary)
    building_mesh = BuildingMesh(primary, primary_path.stem, MeshTypes.PRIMARY, offset)

    if models.surrounding_buildings is None:
        return building_mesh, None, crs
    surrounding_path = Path(models.surrounding_buildings)
    if models.surrounding_radius == 'auto':
        radius = max(config.windtunnel.inlet_buffer - 1, 1) * primary_height
    else:
        radius = models.surrounding_radius
    # footprints far away are dropped before they are extruded; keep_area is in model coordinates
    keep_area = shapely.affinity.translate(primary_outline.buffer(radius), -offset[0], -offset[1])
    surrounding, _ = load_building_model(surrounding_path, models.height_attribute, min_feature, keep_area)
    if surrounding is None:
        warnings.warn(f"no surrounding buildings within {radius:g} m of the primary model")
        return building_mesh, None, crs
    surrounding.apply_translation(offset)
    if surrounding_path.suffix.lower() in MESH_FORMATS:
        surrounding = repair_mesh(surrounding, surrounding_path.name)
    surrounding = crop_surroundings(surrounding, primary, radius)
    if surrounding is None:
        return building_mesh, None, crs
    surrounding = sink_into_ground(surrounding)

    name = surrounding_path.stem
    if foam_name(name) == building_mesh.name:  # both would be written to the same file and patch
        name += '_surrounding'
    return building_mesh, BuildingMesh(surrounding, name, MeshTypes.SURROUNDING, offset), crs


def check_mesh_size(wind_direction, windtunnel_data, snappy_data, building_models, snappy_cfg):
    cells = estimate_cells(windtunnel_data, snappy_data, building_models)
    logger.info(f"{case_dir_name(wind_direction)}: estimated mesh size {cells / 1e6:.2g} million cells")
    if cells > snappy_cfg.maxGlobalCells:
        warnings.warn(f"{case_dir_name(wind_direction)}: the mesh is estimated at {cells / 1e6:.2g} million cells, "
                      f"more than maxGlobalCells ({snappy_cfg.maxGlobalCells / 1e6:.2g} million). snappyHexMesh "
                      "will stop refining part way: raise [snappy] maxGlobalCells or use a coarser mesh.")
    return cells


def _check_inside_domain(wind_direction, bounds, windtunnel_data):
    (min_x, max_x), _, _ = bounds
    if min_x <= windtunnel_data['background_minx'] or max_x >= windtunnel_data['background_maxx']:
        warnings.warn(f"{case_dir_name(wind_direction)}: surrounding buildings reach the inlet or outlet of the "
                      "domain; reduce [models] surrounding_radius")


# OpenFOAM files, not HTML: values are inserted as they are. Missing values are an error.
_renderer = pystache.Renderer(escape=lambda value: value, missing_tags='strict')


def write_case_files(case_data, case_dir):
    """Render the case templates into `case_dir`.

    Most files are static OpenFOAM files that read their values with `#include "caseParameters"`
    and `$name`. The case specific values live in a few generated files: system/caseParameters,
    system/buildingModels, system/sampleSets, system/surfaceFeatureExtractDict and the files in
    0.orig/include.
    """
    template_dir = Path(__file__).parent / 'templates'
    case_files = [x for x in template_dir.glob('**/*') if x.is_file() and x.name[0] != '_']
    for c in case_files:
        with open(c, 'r') as src:
            content = src.read()
        content = _renderer.render(content, case_data)
        output_file = case_dir / c.relative_to(template_dir)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', newline='\n') as dst:
            dst.write(content)
        if content.strip().startswith('#!'):
            output_file.chmod(0o755)


def create_run_all_cases_script(out_dir, wind_directions):
    out_dir = Path(out_dir)
    out_string = "#!/bin/sh\n\n"

    for n, w in enumerate(wind_directions):
        out_string += f"{case_dir_name(w)}/Allclean -l;\n"
        out_string += f"{case_dir_name(w)}/Allrun;\n"

    with open(out_dir / "RunAllCases", 'w', newline='\n') as f:
        f.write(out_string)
    (out_dir / "RunAllCases").chmod(0o755)
