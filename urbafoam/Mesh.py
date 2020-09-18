import os
import copy
import json
from math import radians
from stl import Mesh as stlMesh
from shapely.geometry import MultiPoint, Polygon
from shapely.ops import cascaded_union
from pathlib import Path

from . import MeshTypes


class Mesh:
    def __init__(self, mesh_type=MeshTypes.PRIMARY, offset=[0,0,0]):
        self.file_name = None
        self.name = None
        self.mesh = None
        self.rotated_mesh = None
        self.rotation = 0
        self.bounds = None
        self.centerpoint = [0, 0, 0]
        self.type = mesh_type
        self.offset = offset

    def load_mesh(self, mesh_file):
        if mesh_file.lower().endswith('.stl'):
            self.mesh = _read_stl(mesh_file)
        if self.mesh is not None:
            self.bounds = self.mesh_bounds()
            self.centerpoint = self.mesh_centerpoint()
            self.file_name = os.path.basename(mesh_file)
            self.name = os.path.splitext(self.file_name)[0]

        else:
            raise ValueError("Failed to load %s" % (mesh_file))

    def mesh_bounds(self, mesh=None):
        if mesh is None:
            mesh = self.mesh
        min_bb = (mesh.x.min(), mesh.y.min(), mesh.z.min())
        max_bb = (mesh.x.max(), mesh.y.max(), mesh.z.max())
        return list(zip(min_bb, max_bb))

    def mesh_convex_hull(self, rotated = True):
        if rotated and self.rotated_mesh is not None:
            mesh = self.rotated_mesh
        else:
            mesh = self.mesh
        projected_mesh_points = MultiPoint(list(zip(mesh.x.flatten(), mesh.y.flatten())))
        central_hull = projected_mesh_points.convex_hull
        return central_hull

    def mesh_footprints(self,rotated = True):
        if rotated and self.rotated_mesh is not None:
            mesh = self.rotated_mesh
        else:
            mesh = self.mesh
        footprint_polygons = []
        for t in mesh.vectors:
            tri = Polygon([(t[0][0], t[0][1]), (t[1][0], t[1][1]), (t[2][0], t[2][1])])
            if tri.area > 0:
                footprint_polygons.append(tri)
        cascaded_union(footprint_polygons)

    def mesh_centerpoint(self):
        if self.bounds is None:
            self.mesh_bounds()
        if self.bounds is not None:
            min_x = self.bounds[0][0]
            max_x = self.bounds[0][1]
            min_y = self.bounds[1][0]
            max_y = self.bounds[1][1]
            min_z = self.bounds[2][0]
            max_z = self.bounds[2][1]
            return [min_x + ((max_x - min_x) / 2), min_y + ((max_y - min_y) / 2), min_z]

    def rotate_mesh(self, rotation):
        self.rotation = rotation #270 - wind_direction
        self.rotated_mesh = copy.deepcopy(self.mesh)
        self.rotated_mesh.rotate([0, 0, 1], radians(self.rotation), point=self.centerpoint)

    def rotate_and_save_mesh(self, wind_direction, case_dir):
        self.rotate_mesh(270 - wind_direction)
        out_file = case_dir / "constant" / "triSurface" / self.file_name
        out_file.parent.mkdir(parents=True, exist_ok=True)
        self.rotated_mesh.save(out_file)
        self.rotated_bounds = self.mesh_bounds(self.rotated_mesh)
        rotation_matrix = stlMesh.rotation_matrix([0, 0, 1], radians(270 - wind_direction))
        with open(case_dir / "rotation_matrix.json", 'w') as f:
            json.dump({"rot_matrix": rotation_matrix.tolist(), "centerpoint": list(map(float, self.centerpoint)),
                       'offset': self.offset}, f)
        return rotation_matrix

def _read_stl(stl_file):
    return stlMesh.from_file(stl_file)
