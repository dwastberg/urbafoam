__version__ = "0.1.0"

import logging
from pathlib import Path

import click
from pydantic import ValidationError

from .Config import ConfigError, load_config, save_config
from .DataIO import output_extension, writeWindPoints, writeWindVectors
from .Paths import case_dir_name
from .PostProcess import write_oriented_data, find_sample_points_with_data, normalize_oriented_data, orient_sample_date
from .SetupCase import setupCase

logger = logging.getLogger(__name__)

_existing_file = click.Path(exists=True, dir_okay=False, path_type=Path)


def _load(config_file, case_dir, quality=None):
    try:
        return load_config(config_file, case_dir, quality=quality)
    except ConfigError as e:
        raise click.ClickException(str(e)) from e


def _parse_wind_directions(ctx, param, value):
    if value is None:
        return None
    try:
        directions = [float(w) for w in value.split(',')]
    except ValueError:
        raise click.BadParameter(f"expected comma separated numbers, e.g. '0,90,180,270', got '{value}'")
    return [int(w) if w.is_integer() else w for w in directions]


@click.group()
def cli():
    """
    Tool for generating and postprocessing OpenFoam cases for analysing urban wind comfort
    """
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger(__name__).setLevel(logging.INFO)


@cli.command()
@click.option('-q', '--quality', type=click.Choice(['quick', 'q', 'normal', 'n'], case_sensitive=False))
@click.option('-w', '--wind-dir', callback=_parse_wind_directions, help="Comma separated wind directions in degrees")
@click.option('-m', '--model', type=_existing_file, help="Building model: stl/obj/ply or footprints (shp/geojson/gpkg)")
@click.option('-r', '--surround', type=_existing_file, help="Model of the surrounding buildings")
@click.option('-h', '--height', help="Height attribute of building footprints")
@click.option('-s', '--sample-points', type=_existing_file)
@click.option('-z', type=float, help="Terrain roughness length z0 in m")
@click.option('-t', '--modeltype', help="Terrain type, e.g. urban or suburb (ignored if -z is given)")
@click.option('-p', type=click.IntRange(min=1), help="Number of processes per case")
@click.option('-c', '--config', type=_existing_file)
@click.argument('outdir', type=click.Path(file_okay=False, path_type=Path))
def setup(quality, config, wind_dir, model, surround, height, sample_points, z, modeltype, p, outdir):
    """
    Setup and Generate OpenFoam case files
    """
    outdir = outdir.expanduser().absolute()
    logger.info(f"Setting up cases in {outdir}")
    cfg, doc = _load(config, outdir, quality=quality)

    try:
        if wind_dir is not None:
            cfg.wind.wind_directions = wind_dir
        if model is not None:
            cfg.models.primary_buildings = str(model.expanduser().absolute())
        if surround is not None:
            cfg.models.surrounding_buildings = str(surround.expanduser().absolute())
        if height is not None:
            cfg.models.height_attribute = height
        if z is not None:
            cfg.initial_conditions.z0 = z
        elif modeltype is not None:
            cfg.initial_conditions.z0 = modeltype
        if p is not None:
            cfg.parallel.procs = p
        if sample_points is not None:
            cfg.postprocess.samplePoints = str(sample_points.expanduser().absolute())
    except ValidationError as e:
        raise click.ClickException(str(e)) from e

    try:
        setupCase(cfg, outdir, doc)
    except ValueError as e:
        raise click.ClickException(str(e)) from e


@cli.command()
@click.option('-c', '--config', type=_existing_file)
@click.option('-f', '--format', help="Output format: csv, geojson, shp or gpkg")
@click.argument('casedir', type=click.Path(exists=True, file_okay=False, path_type=Path))
def postprocess(config, format, casedir):
    """PostProcess and output CFD results from Urbafoam run"""
    casedir = casedir.expanduser()
    logger.info(f"Post-processing {casedir}")
    cfg, doc = _load(config, casedir)
    if format is not None:
        try:
            cfg.postprocess.outputFormat = format
        except ValidationError as e:
            raise click.BadParameter(str(e), param_hint="'-f'") from e

    pp = cfg.postprocess
    wind_directions = cfg.wind.wind_directions
    Uref = cfg.initial_conditions.Uref
    offset, crs = cfg.models.offset, cfg.models.crs
    file_ext = output_extension(pp.outputFormat)
    (casedir / 'results').mkdir(exist_ok=True)

    for s in pp.sampleHeights:
        sample_name = f'samplePoints_{s}m'
        if cfg.debug.write_postProcess:
            for w in wind_directions:
                write_oriented_data(casedir / case_dir_name(w), sample_name)

        sample_points_with_data = find_sample_points_with_data(casedir, sample_name, pp.sampleSpacing, wind_directions,
                                                               write=cfg.debug.write_postProcess)
        base_points, normalized_data = normalize_oriented_data(sample_points_with_data, casedir, wind_directions, Uref,
                                                               sample_name, speedup=pp.calcSpeedup)

        writeWindPoints(base_points, normalized_data, wind_directions,
                        casedir / 'results' / f'{sample_name}_U_pts.{file_ext}', format=pp.outputFormat,
                        offset=offset, crs=crs)
        for w in wind_directions:
            data = orient_sample_date(casedir / case_dir_name(w), sample_name, field='U', Uref=Uref)
            writeWindVectors(data, casedir / 'results' / f"windVectors_{sample_name}_{case_dir_name(w)}.{file_ext}",
                             scale=pp.scaleVectorsBy, format=pp.outputFormat, offset=offset, crs=crs)
    save_config(cfg, casedir, doc)
