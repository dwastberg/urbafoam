"""Rough estimate of the number of cells snappyHexMesh will make for a case.

The refinement regions of system/snappyHexMeshDict are integrated over the (z graded) background
mesh, and shells of refined cells are added around the building surfaces and feature edges. The
estimate omits gradual refinement transitions and wall layers. It is meant to catch cases that are
far too big before they are run, so expect it to be within a factor of about 1.5.
"""
import re

import numpy as np
import trimesh

# calibrated against snappyHexMesh v2606 runs of the test models
SURFACE_LAYERS = 1.0  # layers of cells along a surface, in multiples of nCellsBetweenLevels + 1
EDGE_LAYERS = 0.5  # cross section of the refinement along a feature edge, in (nCellsBetweenLevels + 1)^2 cells
N_SAMPLES = 20_000


def parse_levels(level_spec):
    """'(2 4)' -> (2, 4); 3 -> (3, 3)"""
    values = [int(v) for v in re.findall(r'-?\d+', str(level_spec))]
    return values[0], values[-1]


def _cell_heights(z_range, n, grading):
    """Heights of the n background cells of a block with simpleGrading `grading` (last / first)."""
    if n == 1 or grading == 1:
        return np.full(n, z_range / n)
    ratios = grading ** (np.arange(n) / (n - 1))
    return z_range * ratios / ratios.sum()


class _Profile:
    """Refinement level and background cell size as functions of the height above the ground."""

    def __init__(self, windtunnel, snappy, central_ground_bands, n_between):
        self.ground = windtunnel['background_minz']
        heights = _cell_heights(windtunnel['background_maxz'] - self.ground, windtunnel['z_cells'],
                                windtunnel['z_grading'])
        self.tops = np.cumsum(heights)
        self.heights = heights
        self.dx = (windtunnel['background_maxx'] - windtunnel['background_minx']) / windtunnel['x_cells']
        self.dy = (windtunnel['background_maxy'] - windtunnel['background_miny']) / windtunnel['y_cells']
        self.analysis_xy = (snappy['analysis_minx'], snappy['analysis_maxx'],
                            snappy['analysis_miny'], snappy['analysis_maxy'])
        # (level, height up to which it applies) for the whole domain and inside the analysis area;
        # each band reaches nCellsBetweenLevels cells of its level further, as snappy's buffer layers do
        everywhere = [(snappy['verticalRefinementLevel'], snappy['thirdheight'])]
        central = everywhere + [(snappy['insideRefinementLevel'], snappy['analysis_maxz'] - self.ground)]
        central += [(level, distance) for distance, level in central_ground_bands]
        self.bands = {False: self._buffered(everywhere, n_between), True: self._buffered(central, n_between)}

    def _buffered(self, bands, n_between):
        return [(level, top + n_between * self.cell_height(top) / 2 ** level) for level, top in bands]

    def cell_height(self, z):
        return self.heights[np.minimum(np.searchsorted(self.tops, z), len(self.heights) - 1)]

    def in_analysis_area(self, x, y):
        x0, x1, y0, y1 = self.analysis_xy
        return (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)

    def level(self, z, central):
        """Refinement level at height z; `central` (bool or bool array) is True in the analysis area."""
        z = np.asarray(z, dtype=float)
        levels = {}
        for area in (False, True):
            level = np.zeros(z.shape, dtype=int)
            for band_level, top in self.bands[area]:
                level = np.where(z < top, np.maximum(level, band_level), level)
            levels[area] = level
        return np.where(central, levels[True], levels[False])

    def cells_per_volume(self, z, central):
        return 8.0 ** self.level(z, central) / (self.dx * self.dy * self.cell_height(z))


def estimate_cells(windtunnel, snappy, building_models):
    """Estimated number of cells before wall layer addition, from the case data of setup_windtunnel
    and setup_snappy. `building_models` are the BuildingMesh objects (or None) passed to
    setup_snappy, with their rotated mesh set for this wind direction."""
    n_between = snappy['nCellsBetweenLevels']
    # '((3 4) (12 2))': (distance level) pairs
    bands = [(float(d), int(level)) for d, level in re.findall(r'\(\s*([-+.\deE]+)\s+(\d+)\s*\)',
                                                              snappy['verticalCentralRefinement'])]
    profile = _Profile(windtunnel, snappy, bands, n_between)

    # the refinement regions, integrated over the height of the domain
    z_top = windtunnel['background_maxz'] - profile.ground
    z = (np.arange(4000) + 0.5) * z_top / 4000
    x0, x1, y0, y1 = profile.analysis_xy
    domain_area = ((windtunnel['background_maxx'] - windtunnel['background_minx'])
                   * (windtunnel['background_maxy'] - windtunnel['background_miny']))
    central_area = max(x1 - x0, 0) * max(y1 - y0, 0)
    per_height = {c: profile.cells_per_volume(z, c).sum() * z_top / 4000 for c in (False, True)}
    cells = central_area * per_height[True] + (domain_area - central_area) * per_height[False]

    models = [m for m in building_models if m is not None]
    for model, settings in zip(models, snappy['buildingModels']):
        mesh = model.rotated_mesh
        surface_level, max_surface_level = parse_levels(settings['refinementLevel'])
        feature_level = settings['featureLevel']

        # remove the cells inside the buildings
        for part in mesh.split(only_watertight=False):
            if not part.is_volume:
                continue
            (bx0, by0, bz0), (bx1, by1, bz1) = part.bounds
            if bz1 <= 0:
                continue
            centre = profile.in_analysis_area((bx0 + bx1) / 2, (by0 + by1) / 2)
            zs = np.linspace(max(bz0, 0), bz1, 50)
            above_ground = part.volume * (bz1 - max(bz0, 0)) / (bz1 - bz0)
            cells -= above_ground * profile.cells_per_volume(zs, centre).mean()

        # shells of finer cells along the surfaces, above the level of the region they are in
        points, _ = trimesh.sample.sample_surface(mesh, N_SAMPLES, seed=0)
        weight = mesh.area / N_SAMPLES
        points = points[points[:, 2] > 0]
        region = profile.level(points[:, 2], profile.in_analysis_area(points[:, 0], points[:, 1]))
        h0 = (profile.dx * profile.dy * profile.cell_height(points[:, 2])) ** (1 / 3)
        layers = SURFACE_LAYERS * (n_between + 1)
        for level in range(1, surface_level + 1):
            finer = region < level
            cells += np.sum(weight * layers / (h0[finer] / 2 ** level) ** 2)

        # approximate explicit feature and curvature refinement as tubes of finer cells
        mid, length, edge_level = _refinement_edges(
            mesh, settings['includedAngle'], feature_level, snappy['resolveFeatureAngle'], max_surface_level,
        )
        keep = mid[:, 2] > 0
        mid, length, edge_level = mid[keep], length[keep], edge_level[keep]
        region = np.maximum(profile.level(mid[:, 2], profile.in_analysis_area(mid[:, 0], mid[:, 1])), surface_level)
        h0 = (profile.dx * profile.dy * profile.cell_height(mid[:, 2])) ** (1 / 3)
        cross_section = EDGE_LAYERS * (n_between + 1) ** 2
        for level in range(surface_level + 1, edge_level.max(initial=0) + 1):
            finer = (region < level) & (edge_level >= level)
            cells += np.sum(length[finer] * cross_section / (h0[finer] / 2 ** level))
    return max(int(cells), 0)


def _refinement_edges(mesh, included_angle, feature_level, resolve_angle, max_surface_level):
    """Estimate edge refinement using the larger of the explicit feature and curvature levels."""
    angles = mesh.face_adjacency_angles
    explicit = np.where(angles > np.radians(180 - included_angle), feature_level, 0)
    curvature = np.where(angles > np.radians(resolve_angle), max_surface_level, 0)
    levels = np.maximum(explicit, curvature)
    refined = levels > 0
    # open (boundary) edges are explicit features too
    boundary = mesh.edges_sorted[trimesh.grouping.group_rows(mesh.edges_sorted, require_count=1)]
    edges = np.vstack([mesh.face_adjacency_edges[refined], boundary])
    levels = np.concatenate([levels[refined], np.full(len(boundary), feature_level)])
    a, b = mesh.vertices[edges[:, 0]], mesh.vertices[edges[:, 1]]
    return (a + b) / 2, np.linalg.norm(b - a, axis=1), levels
