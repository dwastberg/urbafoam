import fiona
import trimesh.creation
import trimesh.exchange
from shapely.geometry import shape


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


if __name__ == '__main__':
    bm = footprint_to_mesh('tests/testdata/buildings.shp', 'height')
    with open('/tmp/buildings.stl', 'wb') as dst:
        dst.write(trimesh.exchange.stl.export_stl(bm))
    pass
