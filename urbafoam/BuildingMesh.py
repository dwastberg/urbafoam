import json
import math
import re
from pathlib import Path

import numpy as np
from shapely.geometry import MultiPoint

from .Enums import MeshTypes


def foam_name(name):
    """`name` as a safe OpenFOAM word: used for the mesh file and patch names in the case."""
    name = re.sub(r'[^A-Za-z0-9_.-]', '_', name)
    return '_' + name if name[:1].isdigit() else name  # a word cannot start with a digit


def rotation_matrix_z(theta):
    """Rotation matrix about the z axis for row vectors (`points.dot(R)`), built with the
    Euler-Rodrigues formula exactly as earlier versions (via numpy-stl) did, so stored
    rotation_matrix.json files stay bit-identical."""
    axis = np.array([0.0, 0.0, 1.0])
    a = math.cos(0.5 * theta)
    b, c, d = -axis * math.sin(0.5 * theta)
    aa, bb, cc, dd = a * a, b * b, c * c, d * d
    ab, ac, ad, bc, bd, cd = a * b, a * c, a * d, b * c, b * d, c * d
    return np.array([
        [aa + bb - cc - dd, 2 * (bc + ad), 2 * (bd - ac)],
        [2 * (bc - ad), aa + cc - bb - dd, 2 * (cd + ab)],
        [2 * (bd + ac), 2 * (cd - ab), aa + dd - bb - cc],
    ])


class BuildingMesh:
    """A building model prepared for the case: `mesh` is in case coordinates, i.e. the model
    coordinates moved by `offset`, with the ground at z = 0."""

    def __init__(self, mesh, name, mesh_type=MeshTypes.PRIMARY, offset=(0.0, 0.0, 0.0)):
        self.mesh = mesh
        self.name = foam_name(name)
        self.file_name = self.name + '.stl'
        self.type = mesh_type
        self.offset = [float(v) for v in offset]
        self.rotated_mesh = None
        self.rotated_bounds = None
        self.rotation = 0
        self.bounds = self.mesh_bounds()
        self.centerpoint = self.mesh_centerpoint()

    def save(self, directory):
        out_file = Path(directory) / self.file_name
        self.mesh.export(out_file)
        return out_file

    def mesh_bounds(self, mesh=None):
        """Bounds as [(min_x, max_x), (min_y, max_y), (min_z, max_z)] in Python floats."""
        if mesh is None:
            mesh = self.mesh
        return [(float(lo), float(hi)) for lo, hi in mesh.bounds.T]

    def mesh_convex_hull(self, rotated=True):
        if rotated and self.rotated_mesh is not None:
            mesh = self.rotated_mesh
        else:
            mesh = self.mesh
        return MultiPoint(mesh.vertices[:, :2]).convex_hull

    def mesh_centerpoint(self):
        """Centre of the bounding box on the ground; the models are rotated about it."""
        (min_x, max_x), (min_y, max_y), _ = self.bounds
        return [min_x + ((max_x - min_x) / 2), min_y + ((max_y - min_y) / 2), 0.0]

    def _rotate_mesh(self, rotation):
        self.rotation = rotation  # 270 - wind_direction
        rotation_matrix = rotation_matrix_z(math.radians(self.rotation))
        center = np.asarray(self.centerpoint, dtype=float)
        self.rotated_mesh = self.mesh.copy()
        if self.rotation:  # skip the identity so coordinates are not perturbed by (v - c) + c
            self.rotated_mesh.vertices = (self.mesh.vertices - center).dot(rotation_matrix) + center
        return rotation_matrix

    def rotate_and_save_mesh(self, wind_direction, case_dir):
        rotation_matrix = self._rotate_mesh(270 - wind_direction)
        out_file = case_dir / "constant" / "triSurface" / self.file_name
        out_file.parent.mkdir(parents=True, exist_ok=True)
        self.rotated_mesh.export(out_file)
        self.rotated_bounds = self.mesh_bounds(self.rotated_mesh)
        with open(case_dir / "rotation_matrix.json", 'w') as f:
            json.dump({"rot_matrix": rotation_matrix.tolist(), "centerpoint": list(map(float, self.centerpoint)),
                       'offset': self.offset}, f)
        return rotation_matrix
