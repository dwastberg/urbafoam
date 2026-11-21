from pathlib import Path

import numpy as np
import pystache
from pystache.common import MissingTags

from .BlockMesh import setup_windtunnel
from .BuildingMesh import BuildingMesh
from .Config import save_config
from .Controls import setup_controls
from .DataConversion import make_building_mesh
from .Enums import Quality, MeshTypes
from .InitialConditions import setup_initial_conditions
from .Paths import case_dir_name
from .SamplePoints import generate_sample_points, setup_samplepoint
from .Scheme import setup_scheme
from .SnappyHexMesh import setup_snappy


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

    mesh_dir = out_dir / "data" / "building_mesh"
    mesh_dir.mkdir(exist_ok=True, parents=True)
    primary_mesh_path, crs = make_building_mesh(Path(models.primary_buildings), mesh_dir, models.height_attribute)
    if crs is not None and models.crs is None:
        models.crs = crs

    if models.surrounding_buildings is not None:
        surrounding_mesh_path, _ = make_building_mesh(Path(models.surrounding_buildings), mesh_dir,
                                                      models.height_attribute)
    else:
        surrounding_mesh_path = None

    buildingMesh = BuildingMesh()
    buildingMesh.load_mesh(primary_mesh_path, offset=models.offset, center_at_zero=False)
    models.offset = buildingMesh.offset

    if surrounding_mesh_path is not None:
        surroundingMesh = BuildingMesh(mesh_type=MeshTypes.SURROUNDING)
        surroundingMesh.load_mesh(surrounding_mesh_path, offset=buildingMesh.offset)
    else:
        surroundingMesh = None

    postprocess = config.postprocess
    if postprocess.samplePoints is not None:
        sample_points_file = Path(postprocess.samplePoints).expanduser()
        if not sample_points_file.is_file():
            raise FileNotFoundError(f"Can't find sample points file {sample_points_file}")
        sample_points = np.loadtxt(sample_points_file)
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
        case_data = {**windtunnel_data,
                     **snappy_data,
                     **setup_controls(config.controls),
                     **setup_initial_conditions(config.initial_conditions),
                     **setup_scheme(config.scheme),
                     **setup_samplepoint(sample_points, rot_matrix, buildingMesh.centerpoint, sampling_heights)}
        case_data['usePotentialFoam'] = quality == Quality.QUICK
        case_data['procCount'] = procs
        case_data['eachCaseParallel'] = procs > 1

        write_case_files(case_data, case_dir)

    save_config(config, out_dir, doc)
    create_run_all_cases_script(out_dir, config.wind.wind_directions)


def write_case_files(case_data, case_dir):
    template_dir = Path(__file__).parent / 'templates'
    case_files = [x for x in template_dir.glob('**/*') if x.is_file() and x.name[0] != '_']
    for c in case_files:
        with open(c, 'r') as src:
            content = src.read()
        content = pystache.render(content, case_data, missing_tags=MissingTags.strict)
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
