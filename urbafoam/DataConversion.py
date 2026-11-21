import warnings
from shutil import copy

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import shapely.affinity
import trimesh

# 3D model formats converted to STL with trimesh (STL itself is copied as is)
MESH_FORMATS = ('.obj', '.ply', '.off', '.glb', '.gltf')


def make_building_mesh(model_path, outdir, height_attr=None):
    """Write the model as an STL in `outdir`. Returns (stl path, CRS of the source data or None)."""
    crs = None
    if not model_path.is_file():
        raise FileNotFoundError(f"Cannot find {model_path}")
    model_ext = model_path.suffix.lower()

    if model_ext == '.stl':
        copy(model_path, outdir)
        mesh_file = outdir / model_path.name
    elif model_ext in MESH_FORMATS:
        mesh_file = outdir / (model_path.stem + ".stl")
        trimesh.load(model_path, force='mesh').export(mesh_file)
    elif model_ext in ('.json', '.geojson', '.shp', '.gpkg'):
        footprints, crs = read_footprints(model_path, height_attr)
        building_meshes = footprints_to_mesh(footprints)
        if building_meshes is None:
            raise ValueError(f"{model_path} contains no building footprints with a positive '{height_attr}'")

        mesh_file = outdir / (model_path.stem + ".stl")
        with open(mesh_file, 'wb') as dst:
            dst.write(trimesh.exchange.stl.export_stl(building_meshes))
    else:
        raise IOError(f"Unknown model file format {model_ext}")
    #mesh name cannot start with a number (openFOAM 'limitation')
    if mesh_file.name[0].isdigit():
        new_name = outdir / ('_'+ str(mesh_file.name))
        mesh_file.rename(new_name)
        mesh_file = new_name
    return mesh_file, crs


def read_footprints(filename, height_attr):
    """Read building footprints as a list of (Polygon, height) and the source CRS (or None)."""
    gdf = gpd.read_file(filename, engine='pyogrio')
    if height_attr not in gdf.columns:
        raise ValueError(f"{filename} has no height attribute '{height_attr}'. "
                         f"Available attributes: {[c for c in gdf.columns if c != 'geometry']}")
    heights = pd.to_numeric(gdf[height_attr], errors='coerce')
    skipped = int(heights.isna().sum())
    if skipped:
        warnings.warn(f"{filename}: skipped {skipped} footprints without a numeric '{height_attr}' value")
    building_footprints = []
    for geom, height in zip(gdf.geometry, heights):
        if geom is None or not height > 0:
            continue
        if geom.geom_type == 'Polygon':
            building_footprints.append((geom, float(height)))
        elif geom.geom_type == 'MultiPolygon':
            building_footprints.extend((part, float(height)) for part in geom.geoms)
    crs = gdf.crs.to_string() if gdf.crs is not None else None
    return building_footprints, crs


def footprint_to_mesh(filename, height_attr):
    building_footprints, _ = read_footprints(filename, height_attr)
    return footprints_to_mesh(building_footprints)


def footprints_to_mesh(building_footprints):
    """Extrude (Polygon, height) footprints and merge them into one watertight mesh.

    Adjacent buildings share walls; a boolean union removes those internal faces, which
    snappyHexMesh cannot handle well. The work is done near the origin because projected
    coordinates (often ~1e6 m) cost the triangulation and boolean operations precision.
    """
    building_footprints = list(building_footprints)
    if not building_footprints:
        return None
    origin = np.min([fp.bounds[:2] for fp, _ in building_footprints], axis=0)
    parts = [
        trimesh.creation.extrude_polygon(shapely.affinity.translate(fp, -origin[0], -origin[1]), h,
                                         engine='manifold')
        for fp, h in building_footprints
    ]
    merged = trimesh.boolean.union(parts, engine='manifold') if len(parts) > 1 else parts[0]
    merged.apply_translation([origin[0], origin[1], 0.0])
    return merged
