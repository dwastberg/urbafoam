import json
import math
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import MultiPoint

from .Enums import MeshTypes


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
    def __init__(self, mesh_type=MeshTypes.PRIMARY):
        self.file_name = None
        self.name = None
        self.mesh = None
        self.rotated_mesh = None
        self.rotated_bounds = None
        self.rotation = 0
        self.bounds = None
        self.centerpoint = [0, 0, 0]
        self.type = mesh_type
        self.offset = [0, 0, 0]

    def load_mesh(self, mesh_file, offset=None, center_at_zero=False):
        mesh_file = Path(mesh_file)
        try:
            self.mesh = _read_stl(mesh_file)
        except Exception as e:
            raise IOError(f"failed to load {mesh_file}, make sure it exists and is in stl format") from e

        self.bounds = self.mesh_bounds()
        self.centerpoint = self.mesh_centerpoint()
        self.offset = list(offset) if offset is not None else [0, 0, 0]
        self.file_name = mesh_file.name
        self.name = mesh_file.stem
        if center_at_zero:
            self.offset = [-self.centerpoint[0], -self.centerpoint[1], 0.0]
        if min(self.offset) != 0 or max(self.offset) != 0:
            self.mesh.apply_translation(self.offset)
            self.bounds = self.mesh_bounds()
            self.centerpoint = self.mesh_centerpoint()

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
        if self.bounds is None:
            self.bounds = self.mesh_bounds()
        (min_x, max_x), (min_y, max_y), (min_z, _) = self.bounds
        return [min_x + ((max_x - min_x) / 2), min_y + ((max_y - min_y) / 2), min_z]

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


def _read_stl(stl_file):
    # process=False keeps the triangles exactly as stored (no vertex merging or face removal)
    return trimesh.load_mesh(stl_file, process=False)
