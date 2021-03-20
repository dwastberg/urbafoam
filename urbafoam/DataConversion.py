from shutil import copy

import fiona
import trimesh.creation
import trimesh.exchange
from shapely.geometry import shape


def make_building_mesh(model_path, outdir, height_attr=None):
    if not model_path.is_file():
        raise FileNotFoundError(f"Cannot find {model_path}")
    model_ext = model_path.suffix.lower()

    if model_ext == '.stl':
        building_model = copy(model_path, outdir)
        mesh_file = outdir / model_path.name
    elif model_ext in ('.json', '.geojson', '.shp'):
        building_meshes = footprint_to_mesh(model_path, height_attr)

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
    return mesh_file


def footprint_to_mesh(filename, height_attr):
    building_footprints = []
    with fiona.open(filename, 'r') as src:
        for s in src:
            geom = s['geometry']
            height = s['properties'].get(height_attr, 0)
            if geom['type'] == 'Polygon' and height > 0:
                building_footprints.append((shape(geom), height))
    if len(building_footprints) > 0:
        fp, h = building_footprints.pop()
        building_meshes = trimesh.creation.extrude_polygon(fp, h)
        for fp, h in building_footprints:
            building_meshes = building_meshes + (trimesh.creation.extrude_polygon(fp, h))
    else:
        building_meshes = None
    return building_meshes
