import os
from pathlib import Path

import numpy as np
import pystache
from pystache.common import MissingTags

from .BlockMesh import setup_windtunnel
from .BuildingMesh import BuildingMesh
from .Config import save_config_file, get_or_update_config, get_value, set_value
from .Controls import setup_controls
from .DataConversion import make_building_mesh
from .Enums import Quality, MeshTypes, modelTypeLookup
from .InitialConditions import setup_initial_conditions
from .SamplePoints import generate_sample_points, setup_samplepoint
from .Scheme import setup_scheme
from .SnappyHexMesh import setup_snappy


def setupCase(primary_model, surrounding_model, quality, z0, procs, sample_points, out_dir, config):
    out_dir = Path(out_dir).expanduser()
    out_dir.mkdir(exist_ok=True, parents=True)

    mesh_dir = out_dir / "data" / "building_mesh"
    mesh_dir.mkdir(exist_ok=True, parents=True)
    height_attr = get_value(config, "urbafoam.models", "height_attribute")
    primary_mesh_path = make_building_mesh(primary_model, mesh_dir,
                                       height_attr)
    if primary_mesh_path is None:
        raise IOError(f"Could not load {primary_model}")

    if surrounding_model is not None:
        surrounding_mesh_path = make_building_mesh(surrounding_model,mesh_dir, height_attr)
        if surrounding_mesh_path is None:
            raise IOError(f"Could not load {surrounding_model}")
    else:
        surrounding_mesh_path = None

    model_offset = get_or_update_config(config,"urbafoam.models", "offset", [0.0, 0.0, 0.0])
    buildingMesh = BuildingMesh()
    buildingMesh.load_mesh(primary_mesh_path, offset=model_offset, center_at_zero=False)
    set_value(config, "urbafoam.models", "offset", buildingMesh.offset)

    if surrounding_mesh_path is not None:
        surroundingMesh = BuildingMesh(mesh_type=MeshTypes.SURROUNDING)
        surroundingMesh.load_mesh(surrounding_mesh_path,offset=buildingMesh.offset)
    else:
        surroundingMesh = None

    sample_buffer = get_or_update_config(config, "urbafoam.postprocess", "sampleBuffer", 10)
    sample_points = get_or_update_config(config,"urbafoam.postprocess","samplePoints",sample_points)
    if sample_points is not None:
        sample_points = Path(sample_points).expanduser()
        if not sample_points.is_file():
            IOError(f"Can't find {sample_points} ")
        sample_points = np.loadtxt(sample_points)
    else:
        sample_spacing = get_or_update_config(config, "urbafoam.postprocess", "sampleSpacing", 1.0)
        central_hull = buildingMesh.mesh_convex_hull(rotated=False)
        central_hull = central_hull.buffer(sample_buffer)
        sample_points = generate_sample_points(central_hull, sample_spacing)

    np.savetxt(out_dir / "sample_points.txt", sample_points)
    sampling_heights = get_or_update_config(config, "urbafoam.postProcess", "sampleHeights", [2, 10])
    if not sampling_heights:
        sampling_heights = [0]
    if z0 is None:
        z0 = get_or_update_config(config,"urbafoam.initalConditions","z0",'urban')
    if not isinstance(z0,float):
        z0 = z0.lower()
        if z0 not in modelTypeLookup:
            raise ValueError(f'surrounding type {z0} not recognized, use one of {list(modelTypeLookup.keys())}')
        set_value(config,"urbafoam.initalConditions","z0",z0)
        z0 = modelTypeLookup[z0]
    else:
        set_value(config, "urbafoam.initalConditions", "z0", z0)


    wind_directions = get_or_update_config(config, "urbafoam.wind", "wind_directions", [270])

    for w in wind_directions:
        if w.is_integer():
            case_dir_name = str(int(w))
        else:
            case_dir_name = str(w)
        case_dir = out_dir / case_dir_name
        rot_matrix = buildingMesh.rotate_and_save_mesh(w, case_dir)
        if surroundingMesh is not None:
            surroundingMesh.rotate_and_save_mesh(w,case_dir)
            surrounding_bounds = surroundingMesh.rotated_bounds
        else:
            surrounding_bounds = buildingMesh.rotated_bounds
        windtunnel_data = setup_windtunnel(config, buildingMesh.rotated_bounds, surrounding_bounds, quality, case_dir, 0)
        snappy_data = setup_snappy(config, windtunnel_data, [buildingMesh, surroundingMesh], quality)
        control_data = setup_controls(config, quality)
        initial_condition = setup_initial_conditions(config, z0, buildingMesh.rotated_bounds)
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
        os.chmod(out_dir / "RunAllCases", 0o755)
