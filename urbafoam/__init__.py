__version__ = "0.1.0"

import os
import sys
from enum import Enum, auto
from pathlib import Path

import click
import numpy as np
import pystache
from pystache.common import MissingTags


class MeshTypes(Enum):
    PRIMARY = auto()
    SURROUNDING = auto()
    TERRAIN = auto()


class Quality(Enum):
    QUICK = auto()
    NORMAL = auto()


class ModelType(Enum):
    DENSE_URBAN = auto()
    URBAN = auto()
    SUBURB = auto()
    FOREST = auto()
    PARK = auto()
    FIELD = auto()
    WATER = auto()


from .Mesh import Mesh
from .BlockMesh import setup_windtunnel
from .SnappyHexMesh import setup_snappy
from .Controls import setup_controls
from .InitialConditions import setup_initial_conditions
from .Scheme import setup_scheme
from .SamplePoints import generate_sample_points, setup_samplepoint
from .Config import load_config, save_config_file, get_or_update_config, merge_configs, get_value
from .PostProcess import write_oriented_data, find_sample_points_with_data, normalize_oriented_data, orient_sample_date
from .DataIO import writeWindPoints, writeWindVectors


@click.group()
def cli():
    """
    Tool for generating and postprocessing OpenFoam cases for analysing urban wind comfort
    """
    pass


@cli.command()
@click.option('-q', '--quality')
@click.option('-w', '--wind-dir')
@click.option('-m', '--model', type=click.Path())
@click.option('-p', type=int)
@click.option('-c', '--config', type=click.Path())
@click.argument('outdir', type=click.Path())
def setup(quality, config, wind_dir, model, p, outdir):
    """
    Setup and Generate OpenFoam case files
    """
    print(outdir)
    config = load_config(config, outdir)

    if wind_dir is not None:
        wind_directions = wind_dir.split(',')
        try:
            wind_directions = [float(w.strip()) for w in wind_directions]
            get_or_update_config(config, "urbafoam.wind", "wind_directions", wind_directions, True)
        except:
            print("failed to parse wind directions", wind_dir)
            sys.exit(1)

    if model is None:
        primary_building_model = get_or_update_config(config, "urbafoam.models", "primaty_buildings", None)
    else:
        primary_building_model = get_or_update_config(config, "urbafoam.models", "primaty_buildings", model, True)
    assert primary_building_model is not None and os.path.isfile(
        primary_building_model), "cannot find building model %s" % model

    if quality is None:
        quality = get_or_update_config(config, "", "quality", 'quick')
    else:
        if quality in ('normal', 'n', 'N', 'Normal', 'quick', 'q', 'Quick', 'Q'):
            quality = get_or_update_config(config, "", "quality", quality, overwrite=True)
        else:
            print(f"unknown quality {quality}, must be eithet '(q)uick' or '(n)ormal'")
            sys.exit(1)

    if quality in ('normal', 'n', 'N', 'Normal'):
        quality = Quality.NORMAL

    elif quality in ('quick', 'q', 'Quick', 'Q'):
        quality = Quality.QUICK

    if p is None:
        procs = get_or_update_config(config, "urbafoam.parallel", "procs", os.cpu_count() // 2)
    else:
        procs = get_or_update_config(config, "urbafoam.parallel", "procs", p, overwrite=True)

    out_dir = get_or_update_config(config, "", "out_dir", outdir)

    setupCase(model, quality, procs, outdir, config)


@cli.command()
@click.option('-c', '--config', type=click.Path())
@click.argument('casedir', type=click.Path())
def postprocess(config, casedir):
    """PostProcess and output CFD results from Urbafoam run"""
    print("postprocess")
    casedir = Path(casedir).expanduser()
    (casedir / 'results').mkdir(exist_ok=True)
    config = load_config(config, casedir)
    wind_directions = get_value(config, "urbafoam.wind", "wind_directions")
    sample_spacing = get_value(config, "urbafoam.postprocess", "sampleSpacing")
    Uref = get_value(config,"urbafoam.initalconditions","Uref")
    get_speedup = get_or_update_config(config, "urbafoam.postprocess", "calcSpeedup", True)
    scale_vectors = get_or_update_config(config, "urbafoam.postprocess", "scaleVectorsBy", 2.0)
    WRITE = get_or_update_config(config, "urbafoam.debug", "write_postProcess", False)
    if WRITE:
        for w in wind_directions:
            write_oriented_data(casedir / str(w), 'samplePoints_2m')

    sample_height = get_value(config,"urbafoam.postprocess","sampleHeights")
    normalized_data_collection = {}
    for s in sample_height:
        sample_name = f'samplePoints_{s}m'

        sample_points_with_data = find_sample_points_with_data(casedir, sample_name, sample_spacing, wind_directions,
                                                           write=WRITE)
        base_points, normalized_data = normalize_oriented_data(sample_points_with_data, casedir, wind_directions, Uref,
                                                             sample_name)
        normalized_data_collection[sample_name] = (base_points, normalized_data)

        writeWindPoints(base_points, normalized_data, wind_directions, casedir / 'results' / f'{sample_name}_U_pts.json', format='geojson')
        for w in wind_directions:
            data = orient_sample_date(casedir / str(w), sample_name, field='U', Uref=Uref)
            writeWindVectors(data, casedir / 'results' / f"windVectors_{sample_name}_{w}.json", scale=scale_vectors, format='geojson')
    save_config_file(casedir, config)


def setupCase(building_model, quality, procs, out_dir, config):
    buildingMesh = Mesh()
    buildingMesh.load_mesh(building_model)
    out_dir = Path(out_dir).expanduser()
    out_dir.mkdir(exist_ok=True, parents=True)
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
        out_string += f"{str(w)}/Allrun;\n"

    with open(out_dir / "RunAllCases", 'w', newline='\n') as f:
        f.write(out_string)
