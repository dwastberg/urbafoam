__version__ = "0.1.0"

import os
import sys
from pathlib import Path

import click

from .Config import load_config, save_config_file, get_or_update_config, merge_configs, get_value
from .DataIO import writeWindPoints, writeWindVectors
from .Enums import Quality
from .PostProcess import write_oriented_data, find_sample_points_with_data, normalize_oriented_data, orient_sample_date
from .SetupCase import setupCase


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
@click.option('-r', '--surround', type=click.Path())
@click.option('-h', '--height')
@click.option('-s', '--sample-points', type=click.Path())
@click.option('-z',type=float)
@click.option('-t','--modeltype')
@click.option('-p', type=int)
@click.option('-c', '--config', type=click.Path())
@click.argument('outdir', type=click.Path())
def setup(quality, config, wind_dir, model, surround, height, sample_points, z, modeltype, p, outdir):
    """
    Setup and Generate OpenFoam case files
    """
    if outdir is None:
        outdir = os.getcwd()
    outdir = Path(outdir).expanduser().absolute()
    print(outdir)
    config = load_config(config, outdir)

    if wind_dir is not None:
        wind_directions = wind_dir.split(',')
        try:
            wind_directions = [float(w.strip()) for w in wind_directions]
            get_or_update_config(config, "urbafoam.wind", "wind_directions", wind_directions, True)
        except:
            sys.exit(f"failed to parse wind directions {wind_dir}")

    if model is None:
        model = get_or_update_config(config, "urbafoam.models", "primary_buildings", None)
    if model is not None:
        model = Path(model).expanduser()
        if not model.is_file():
            raise FileNotFoundError(f"cannot find model {model}")

    if surround is None:
        surround = get_or_update_config(config, "urbafoam.models", "primary_buildings", None)
    if surround is not None:
        surround = Path(surround).expanduser()
        if not surround.is_file():
            raise FileNotFoundError(f"cannot find surrounding model {surround}")

    if height is not None:
        height_attr = get_or_update_config(config, "urbafoam.models", "height_attribute", height, True)
    else:
        height_attr = get_value(config, "urbafoam.models", "height_attribute")

    if z is not None:
        z0 = float(z)
    else:
        z0 = modeltype



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

    outdir = get_or_update_config(config, "", "out_dir", str(outdir))
    setupCase(model, surround, quality, z0, procs, sample_points, outdir, config)


@cli.command()
@click.option('-c', '--config', type=click.Path())
@click.option('-f', '--format')
@click.argument('casedir', type=click.Path())
def postprocess(config, format, casedir):
    """PostProcess and output CFD results from Urbafoam run"""
    print("postprocess")
    casedir = Path(casedir).expanduser()
    (casedir / 'results').mkdir(exist_ok=True)
    config = load_config(config, casedir)
    wind_directions = get_value(config, "urbafoam.wind", "wind_directions")
    sample_spacing = get_value(config, "urbafoam.postprocess", "sampleSpacing")
    Uref = get_value(config, "urbafoam.initalconditions", "Uref")
    get_speedup = get_or_update_config(config, "urbafoam.postprocess", "calcSpeedup", True)
    offset = get_value(config, "urbafoam.models", "offset")

    scale_vectors = get_or_update_config(config, "urbafoam.postprocess", "scaleVectorsBy", 2.0)

    known_formats = ('csv', 'json', 'geojson', 'shp', 'shape')
    if format is not None:
        format = format.replace('.', '')
        format = format.lower()
        format = get_or_update_config(config, "urbafoam.postprocess", "outputFormat", format, overwrite=True)
    else:
        format = get_or_update_config(config, "urbafoam.postprocess", "outputFormat", 'csv')

    if format == 'csv':
        file_ext = 'csv'
    elif format in ('shp', 'shape'):
        file_ext = 'shp'
    elif format in ('json', 'geojson'):
        file_ext = 'json'
    else:
        raise ValueError(f'output type {format} not recognized. Must be one of {known_formats}')

    WRITE = get_or_update_config(config, "urbafoam.debug", "write_postProcess", False)
    if WRITE:
        for w in wind_directions:
            write_oriented_data(casedir / str(w), 'samplePoints_2m')

    sample_height = get_value(config, "urbafoam.postprocess", "sampleHeights")
    normalized_data_collection = {}
    for s in sample_height:
        sample_name = f'samplePoints_{s}m'

        sample_points_with_data = find_sample_points_with_data(casedir, sample_name, sample_spacing, wind_directions,
                                                               write=WRITE)
        base_points, normalized_data = normalize_oriented_data(sample_points_with_data, casedir, wind_directions, Uref,
                                                               sample_name)
        normalized_data_collection[sample_name] = (base_points, normalized_data)

        writeWindPoints(base_points, normalized_data, wind_directions,
                        casedir / 'results' / f'{sample_name}_U_pts.{file_ext}', format=format,offset=offset)
        for w in wind_directions:
            data = orient_sample_date(casedir / str(w), sample_name, field='U', Uref=Uref)
            writeWindVectors(data, casedir / 'results' / f"windVectors_{sample_name}_{w}.{file_ext}", scale=scale_vectors,
                             format=format,offset=offset)
    save_config_file(casedir, config)
