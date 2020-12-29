import os
from pathlib import Path

import numpy as np
import pystache
from pystache.common import MissingTags

from .BlockMesh import setup_windtunnel
from .BuildingMesh import BuildingMesh
from .Config import save_config_file, get_or_update_config, get_value
from .Controls import setup_controls
from .DataConversion import make_building_mesh
from .Enums import ModelType, Quality
from .InitialConditions import setup_initial_conditions
from .SamplePoints import generate_sample_points, setup_samplepoint
from .Scheme import setup_scheme
from .SnappyHexMesh import setup_snappy


def setupCase(building_model, quality, procs, out_dir, config):
    out_dir = Path(out_dir).expanduser()
    out_dir.mkdir(exist_ok=True, parents=True)

    mesh_dir = out_dir / "data" / "building_mesh"
    mesh_dir.mkdir(exist_ok=True, parents=True)
    building_model = Path(building_model)
    building_model = make_building_mesh(building_model, mesh_dir,
                                        height_attr=get_value(config, "urbafoam.models", "height_attribute"))

    buildingMesh = BuildingMesh()

    buildingMesh.load_mesh(building_model)

    sample_buffer = get_or_update_config(config, "urbafoam.postprocess", "sampleBuffer", 10)
    sample_spacing = get_or_update_config(config, "urbafoam.postprocess", "sampleSpacing", 1.0)

    central_hull = buildingMesh.mesh_convex_hull(rotated=False)
    central_hull = central_hull.buffer(sample_buffer)
    sample_points = generate_sample_points(central_hull, sample_spacing)
    np.savetxt(out_dir / "sample_points.txt", sample_points)
    sampling_heights = get_or_update_config(config, "urbafoam.postProcess", "sampleHeights", [2, 10])

    wind_directions = get_or_update_config(config, "urbafoam.wind", "wind_directions", [270])

    for w in wind_directions:
        case_dir = out_dir / str(w)
        rot_matrix = buildingMesh.rotate_and_save_mesh(w, case_dir)
        windtunnel_data = setup_windtunnel(config, buildingMesh.rotated_bounds, quality, case_dir, 0)
        snappy_data = setup_snappy(config, windtunnel_data, [buildingMesh], quality)
        control_data = setup_controls(config, quality)
        initial_condition = setup_initial_conditions(config, ModelType.URBAN, buildingMesh.rotated_bounds)
        scheme_data = setup_scheme(config)
        sample_point_data = setup_samplepoint(sample_points, rot_matrix, buildingMesh.centerpoint, sampling_heights)

        case_data = {**windtunnel_data,
                     **snappy_data,
                     **control_data,
                     **initial_condition,
                     **scheme_data,
                     **sample_point_data}

        if quality == Quality.QUICK:
            case_data['usePotentialFoam'] = True
        else:
            case_data['usePotentialFoam'] = False

        case_data['procCount'] = procs
        case_data['eachCaseParallel'] = procs > 1

        write_case_files(case_data, case_dir)

    save_config_file(out_dir, config)
    create_run_all_cases_script(out_dir, wind_directions)


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
            st = os.stat(output_file)
            os.chmod(output_file, 0o755)


def create_run_all_cases_script(out_dir, wind_directions):
    out_dir = Path(out_dir)
    out_string = "#!/bin/sh\n\n"

    for n, w in enumerate(wind_directions):
        out_string += f"{str(w)}/Allclean -l;\n"
        out_string += f"{str(w)}/Allrun;\n"

    with open(out_dir / "RunAllCases", 'w', newline='\n') as f:
        f.write(out_string)
