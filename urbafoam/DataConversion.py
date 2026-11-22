"""Reading building models and preparing them for snappyHexMesh.

Models are kept as float64 trimesh meshes until they are written into a case, so large map
coordinates do not lose precision (STL stores 32 bit floats).
"""
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import shapely.affinity
import trimesh

MESH_FORMATS = ('.stl', '.obj', '.ply', '.off', '.glb', '.gltf')
FOOTPRINT_FORMATS = ('.json', '.geojson', '.shp', '.gpkg')

# models further than this from the origin are moved next to it by the 'auto' offset
LOCAL_ORIGIN_LIMIT = 10_000.0
# buildings are extended this far below the ground, so they cut through it instead of standing on it
GROUND_DEPTH = 1.0
# parts whose base is less than this above the ground are taken to stand on it
GROUND_TOLERANCE = 0.5


def load_building_model(model_path, height_attr='height', min_feature_size=0.0, keep_area=None):
    """Read a building model in its own coordinates. Returns (trimesh or None, CRS of the source or None).

    Footprints are cleaned up at `min_feature_size` (see `clean_footprints`), and only those
    intersecting `keep_area` (a shapely geometry) are used. None is returned when no footprint is left.
    """
    if not model_path.is_file():
        raise FileNotFoundError(f"Cannot find {model_path}")
    model_ext = model_path.suffix.lower()

    if model_ext == '.stl':
        # process=False: keep the triangles as stored, repair_mesh does the clean-up
        return trimesh.load_mesh(model_path, process=False), None
    if model_ext in MESH_FORMATS:
        return trimesh.load(model_path, force='mesh'), None
    if model_ext in FOOTPRINT_FORMATS:
        footprints, crs = read_footprints(model_path, height_attr)
        if not footprints:
            raise ValueError(f"{model_path} contains no building footprints with a positive '{height_attr}'")
        if keep_area is not None:
            footprints = [(fp, h) for fp, h in footprints if fp.intersects(keep_area)]
        footprints = clean_footprints(footprints, min_feature_size)
        return footprints_to_mesh(footprints), crs
    raise IOError(f"Unknown model file format {model_ext}")


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
        building_footprints.extend((part, float(height)) for part in _polygons(geom))
    crs = gdf.crs.to_string() if gdf.crs is not None else None
    return building_footprints, crs


def _polygons(geom):
    """The polygons of any geometry, skipping lines and points (e.g. from make_valid)."""
    if geom.geom_type == 'Polygon':
        return [geom] if not geom.is_empty else []
    if geom.geom_type in ('MultiPolygon', 'GeometryCollection'):
        return [p for g in geom.geoms for p in _polygons(g)]
    return []


def footprint_to_mesh(filename, height_attr):
    building_footprints, _ = read_footprints(filename, height_attr)
    return footprints_to_mesh(building_footprints)


def clean_footprints(footprints, min_feature_size):
    """Make (Polygon, height) footprints meshable with cells of about `min_feature_size`.

    Invalid polygons are repaired, outlines simplified by a quarter of the size, gaps narrower than
    half of it between neighbouring footprints closed, and courtyards narrower than it and
    footprints with a smaller area than its square removed. A size of 0 only repairs the polygons.
    """
    valid = [(p, h) for fp, h in footprints for p in _polygons(shapely.make_valid(fp))]
    if min_feature_size <= 0 or not valid:
        return valid

    gap = min_feature_size / 2
    polys = [fp.simplify(min_feature_size / 4, preserve_topology=True) for fp, _ in valid]
    # close the gaps: snap each outline to the corners of its neighbours (as they were before
    # snapping, so the result does not depend on the order of the footprints)
    tree = shapely.STRtree(polys)
    snapped = []
    for i, fp in enumerate(polys):
        near = [j for j in tree.query(fp, predicate='dwithin', distance=gap) if j != i]
        if near:
            fp = shapely.snap(fp, shapely.union_all([polys[j] for j in near]), gap)
        snapped.append(fp)

    cleaned, too_small = [], 0
    for fp, (_, height) in zip(snapped, valid):
        for part in _polygons(shapely.make_valid(fp)):
            holes = [h for h in part.interiors if not shapely.Polygon(h).buffer(-gap).is_empty]
            part = shapely.Polygon(part.exterior, holes)
            if part.area >= min_feature_size ** 2:
                cleaned.append((part, height))
            else:
                too_small += 1
    if too_small:
        warnings.warn(f"removed {too_small} footprints smaller than {min_feature_size:g} m x {min_feature_size:g} m")
    return cleaned


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
    merged = _union(parts)
    merged.apply_translation([origin[0], origin[1], 0.0])
    return merged


def _union(meshes):
    return trimesh.boolean.union(meshes, engine='manifold') if len(meshes) > 1 else meshes[0]


def resolve_offset(offset, mesh):
    """The translation to apply to the models: `offset` itself, or for 'auto' one that puts the
    base of `mesh` at z = 0 and moves its centre to the origin if it is more than
    LOCAL_ORIGIN_LIMIT away (rounded to whole metres)."""
    if offset != 'auto':
        return [float(v) for v in offset]
    lo, hi = mesh.bounds
    centre = (lo[:2] + hi[:2]) / 2
    xy = -np.round(centre) if np.abs(centre).max() > LOCAL_ORIGIN_LIMIT else np.zeros(2)
    return [float(xy[0]) + 0.0, float(xy[1]) + 0.0, 0.0 - float(lo[2])]  # + 0.0: no -0.0


def repair_mesh(mesh, name='model'):
    """Turn a mesh model into closed, non-overlapping solids for snappyHexMesh.

    Duplicate vertices are merged, degenerate and duplicate triangles removed, small holes filled
    and the triangles of every part oriented outwards. The closed parts are then joined with a
    boolean union, which removes overlaps and internal walls. Parts that stay open are kept as
    they are, with a warning: snappyHexMesh can leak into them and leave cells inside.
    """
    mesh = mesh.copy()
    mesh.merge_vertices()  # identical vertices only: a coarser tolerance collapses finely tessellated curves
    # only triangles that collapsed to an edge: zero-area triangles with three distinct (collinear)
    # corners close T-junctions, so removing them would open the surface
    faces = np.sort(mesh.faces, axis=1)
    mesh.update_faces((faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]))
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()

    solids, open_parts = [], []
    for part in mesh.split(only_watertight=False):
        if not part.is_watertight:
            part.fill_holes()
        if not part.is_winding_consistent:
            part.fix_normals()  # slow on large parts, so only where needed
        elif part.is_watertight and part.volume < 0:
            part.invert()
        (solids if part.is_volume else open_parts).append(part)
    if open_parts:
        bounds = ', '.join(str(np.round(p.bounds, 1).tolist()) for p in open_parts[:5])
        warnings.warn(f"{name}: {len(open_parts)} of {len(solids) + len(open_parts)} parts are not closed "
                      f"surfaces and could not be repaired (bounds {bounds}{' ...' if len(open_parts) > 5 else ''}). "
                      "The mesh may get cells inside these buildings.")
    if solids:
        try:
            solids = [_union(solids)]
        except Exception as e:  # keep going with the overlapping parts rather than fail
            warnings.warn(f"{name}: could not merge the parts of the model ({e}); overlapping parts are kept")
    return trimesh.util.concatenate(solids + open_parts)


def sink_into_ground(mesh, depth=GROUND_DEPTH, tolerance=GROUND_TOLERANCE):
    """Extend the buildings standing on the ground (z = 0) down to z = -depth.

    A building base in the same plane as the ground of the domain gives snappyHexMesh poor cells
    along the building edges; a building that cuts through the ground does not. The vertices on
    the base of each part whose base is less than `tolerance` above the ground are moved down,
    which stretches the walls. Parts higher up (e.g. bridges) and parts already below are kept.
    """
    parts = mesh.split(only_watertight=False)
    for part in parts:
        base = part.bounds[0][2]
        if -depth < base < tolerance:
            vertices = part.vertices.copy()
            vertices[vertices[:, 2] < base + 0.01, 2] = -depth
            part.vertices = vertices
    return trimesh.util.concatenate(parts) if parts else mesh


def footprint_outline(mesh):
    """2D convex hull of the mesh."""
    return shapely.MultiPoint(mesh.vertices[:, :2]).convex_hull


def crop_surroundings(surrounding, primary, radius):
    """Keep the parts of `surrounding` within `radius` of the primary model (whole buildings: a
    part reaching into the radius is kept) and drop those that overlap the primary model, which is
    often included in the surroundings data too. Returns the cropped mesh, or None if nothing is left."""
    keep_area = footprint_outline(primary).buffer(radius)
    primary_solid = [p for p in primary.split(only_watertight=False) if p.is_volume]
    primary_solid = trimesh.util.concatenate(primary_solid) if primary_solid else None

    kept, outside, overlapping = [], 0, 0
    for part in surrounding.split(only_watertight=False):
        if not footprint_outline(part).intersects(keep_area):
            outside += 1
        elif _overlaps(part, primary_solid):
            overlapping += 1
        else:
            kept.append(part)
    if overlapping:
        warnings.warn(f"left out {overlapping} surrounding buildings that overlap the primary model")
    if not kept:
        warnings.warn(f"no surrounding buildings within {radius:g} m of the primary model")
        return None
    return trimesh.util.concatenate(kept)


def _overlaps(part, solid, fraction=0.01):
    """True if more than `fraction` of the volume of `part` lies inside `solid`."""
    if solid is None or not part.is_volume:
        return False
    (lo, hi), (slo, shi) = part.bounds, solid.bounds
    if np.any(lo >= shi) or np.any(hi <= slo):
        return False
    try:
        inside = trimesh.boolean.intersection([part, solid], engine='manifold')
    except Exception:
        return False
    return inside.volume > fraction * part.volume
