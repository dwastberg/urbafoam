"""Preparing building models for snappyHexMesh: coordinates, repair, clean-up, ground, surroundings, size."""
import json
import shutil
import warnings

import numpy as np
import pytest
import trimesh
from scipy.spatial import cKDTree
from shapely.geometry import Polygon, box

from tests.regression import CONFIG, TESTDATA, invoke, run_case


def _box(x0, y0, x1, y1, z1, z0=0.0):
    mesh = trimesh.creation.box(bounds=[[x0, y0, z0], [x1, y1, z1]])
    return mesh


# ---------------------------------------------------------------------------- offset / precision

def test_offset_is_subtracted_from_the_results(tmp_path):
    from urbafoam.DataIO import writeWindPoints, writeWindVectors

    offset = [-1000.0, -2000.0, -5.0]  # the model was moved by this
    writeWindPoints([[1.0, 2.0, 2.0]], [np.array([0.5])], [0], tmp_path / "p.csv", offset=offset)
    np.testing.assert_allclose(np.loadtxt(tmp_path / "p.csv", delimiter=",", skiprows=1)[:3], [1001, 2002, 7])
    writeWindVectors([[1.0, 2.0, 2.0, 2.0, 2.0, 2.0, 1.0]], tmp_path / "v.csv", offset=offset)
    np.testing.assert_allclose(np.loadtxt(tmp_path / "v.csv", delimiter=",", skiprows=1)[:6],
                               [1001, 2002, 7, 1002, 2002, 7])


def test_auto_offset():
    from urbafoam.DataConversion import resolve_offset

    far = _box(1_394_600.4, 4_989_700.0, 1_394_700.0, 4_989_800.0, 20, z0=12.5)
    assert resolve_offset('auto', far) == [-1_394_650.0, -4_989_750.0, -12.5]
    near = _box(100, 200, 150, 260, 20)
    assert resolve_offset('auto', near) == [0.0, 0.0, 0.0]
    assert str(resolve_offset('auto', near)) == "[0.0, 0.0, 0.0]"  # no -0.0 in the files
    assert resolve_offset([1, 2, 3], far) == [1.0, 2.0, 3.0]


def test_map_coordinates_are_meshed_near_the_origin_without_losing_precision(tmp_path):
    from urbafoam.Config import load_config
    from urbafoam.DataConversion import clean_footprints, footprints_to_mesh, read_footprints
    from urbafoam.SetupCase import finest_cell_near_buildings

    case = run_case("shp", tmp_path / "case")
    rotation = json.loads((case / "0" / "rotation_matrix.json").read_text())
    offset = np.array(rotation["offset"])
    assert np.abs(offset[:2]).min() > 1e6

    # the STL written into the case is next to the origin and matches the float64 model to < 1 mm
    case_stl = trimesh.load(case / "0" / "constant" / "triSurface" / "buildings.stl")
    assert np.abs(case_stl.bounds).max() < 1000
    footprints, _ = read_footprints(TESTDATA / "buildings.shp", "height")
    min_feature = finest_cell_near_buildings(load_config(case / "urbafoam.toml")[0])
    assert min_feature == 0.625  # quick: 10 m cells, level 4 near the ground
    exact = footprints_to_mesh(clean_footprints(footprints, min_feature))
    # rotated back, the vertices above the ground are those of the model
    R, c = np.array(rotation["rot_matrix"]), np.array(rotation["centerpoint"])
    unrotated = (case_stl.vertices - c).dot(np.linalg.inv(R)) + c
    above_ground = unrotated[unrotated[:, 2] > 0] - offset
    distance, _ = cKDTree(exact.vertices).query(above_ground)
    assert distance.max() < 1e-3

    # results are given in the coordinates of the model again
    pts = np.loadtxt(case / "results" / "samplePoints_2m_U_pts.csv", delimiter=",", skiprows=1)
    (x0, y0, _), (x1, y1, _) = exact.bounds
    assert x0 - 20 < pts[:, 0].mean() < x1 + 20 and y0 - 20 < pts[:, 1].mean() < y1 + 20
    np.testing.assert_allclose(pts[:, 2], 2.0)


def test_sample_points_file_is_in_model_coordinates(tmp_path):
    points = np.array([[1_394_700.0, 4_989_740.0, 0.0], [1_394_710.0, 4_989_750.0, 0.0]])
    np.savetxt(tmp_path / "points.txt", points)
    case = tmp_path / "case"
    invoke("setup", "-q", "quick", "-c", CONFIG, "-w", "0", "-m", TESTDATA / "buildings.shp",
           "-s", tmp_path / "points.txt", case)
    offset = json.loads((case / "0" / "rotation_matrix.json").read_text())["offset"]
    np.testing.assert_allclose(np.loadtxt(case / "sample_points.txt"), points + offset)


def test_models_with_terrain_elevation_are_put_on_the_ground(tmp_path):
    model = _box(0, 0, 20, 20, 52.0, z0=40.0)  # base at 40 m above sea level
    model.export(tmp_path / "elevated.stl")
    case = tmp_path / "case"
    invoke("setup", "-q", "quick", "-c", CONFIG, "-w", "0", "-m", tmp_path / "elevated.stl", case)
    assert json.loads((case / "0" / "rotation_matrix.json").read_text())["offset"] == [0.0, 0.0, -40.0]
    stl = trimesh.load(case / "0" / "constant" / "triSurface" / "elevated.stl")
    assert stl.bounds[1][2] == pytest.approx(12.0)


def test_misplaced_ground_is_reported(tmp_path):
    model = _box(0, 0, 20, 20, 52.0, z0=40.0)
    model.export(tmp_path / "elevated.stl")
    config = tmp_path / "urbafoam.toml"
    config.write_text(CONFIG.read_text() + '\n[models]\noffset = [0, 0, 0]\n')
    with pytest.warns(UserWarning, match="buildings will be cut off or float"):
        invoke("setup", "-q", "quick", "-c", config, "-w", "0", "-m", tmp_path / "elevated.stl", tmp_path / "case")


# ---------------------------------------------------------------------------- model names

def test_primary_and_surrounding_with_the_same_name_are_kept_apart(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    shutil.copy(TESTDATA / "buildings_small.stl", tmp_path / "a" / "buildings.stl")
    _box(200, 120, 215, 135, 20).export(tmp_path / "b" / "buildings.stl")
    case = tmp_path / "case"
    invoke("setup", "-q", "quick", "-c", CONFIG, "-w", "0", "-m", tmp_path / "a" / "buildings.stl",
           "-r", tmp_path / "b" / "buildings.stl", case)

    tri = case / "0" / "constant" / "triSurface"
    primary, surrounding = trimesh.load(tri / "buildings.stl"), trimesh.load(tri / "buildings_surrounding.stl")
    assert primary.volume == pytest.approx(trimesh.load(TESTDATA / "buildings_small.stl").volume, rel=0.05)
    assert surrounding.bounds[0][0] == pytest.approx(200)
    models = (case / "0" / "system" / "buildingModels").read_text()
    assert "buildings_surrounding.stl" in models and '"buildings.stl"' in models


def test_names_starting_with_a_digit_are_valid_openfoam_words():
    from urbafoam.BuildingMesh import foam_name

    assert foam_name("3d model") == "_3d_model"


# ---------------------------------------------------------------------------- mesh repair

def test_repair_closes_orients_and_merges_parts():
    from urbafoam.DataConversion import repair_mesh

    open_box = _box(0, 0, 10, 10, 10)
    open_box.update_faces(np.arange(len(open_box.faces)) != 0)  # a hole in the side
    inverted = _box(20, 0, 30, 10, 10)
    inverted.invert()
    overlapping = [_box(40, 0, 50, 10, 10), _box(45, 5, 55, 15, 20)]  # overlap 5 x 5 x 10
    duplicated = _box(60, 0, 70, 10, 10)
    model = trimesh.util.concatenate([open_box, inverted, *overlapping, duplicated, duplicated.copy()])
    assert not model.is_volume

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # every part can be repaired
        repaired = repair_mesh(model)
    assert repaired.is_volume
    assert len(repaired.split()) == 4
    assert repaired.volume == pytest.approx(1000 + 1000 + (1000 + 2000 - 250) + 1000)


def test_parts_that_cannot_be_closed_are_reported():
    from urbafoam.DataConversion import repair_mesh

    sheet = trimesh.Trimesh(vertices=[[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0], [5, 5, 5]],
                            faces=[[0, 1, 4], [1, 2, 4], [2, 3, 4]])
    model = trimesh.util.concatenate([_box(20, 0, 30, 10, 10), sheet])
    with pytest.warns(UserWarning, match="1 of 2 parts are not closed"):
        repaired = repair_mesh(model)
    assert len(repaired.faces) == 12 + 3


def test_test_models_repair_to_closed_solids():
    from urbafoam.DataConversion import load_building_model, repair_mesh

    for name in ("buildings.stl", "buildings.obj"):
        mesh, _ = load_building_model(TESTDATA / name)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert repair_mesh(mesh, name).is_volume


# ---------------------------------------------------------------------------- footprint clean-up

def test_narrow_gaps_between_footprints_are_closed():
    from urbafoam.DataConversion import clean_footprints, footprints_to_mesh

    footprints = [(box(0, 0, 10, 10), 10.0), (box(10.05, 2, 20, 8), 6.0),  # 5 cm gap
                  (box(25, 0, 30, 10), 10.0)]  # 5 m away: a real street
    assert len(footprints_to_mesh(footprints).split()) == 3
    mesh = footprints_to_mesh(clean_footprints(footprints, 0.6))
    assert len(mesh.split()) == 2
    assert mesh.is_volume


def test_small_courtyards_and_buildings_are_removed():
    from urbafoam.DataConversion import clean_footprints

    with_courtyards = Polygon(box(0, 0, 30, 30).exterior.coords,
                              [box(2, 2, 2.5, 20).exterior.coords,  # 0.5 m wide slot: closed
                               box(10, 10, 20, 20).exterior.coords])  # real courtyard: kept
    footprints = [(with_courtyards, 10.0), (box(40, 0, 40.3, 0.3), 3.0)]  # 0.3 x 0.3 m: removed
    with pytest.warns(UserWarning, match="removed 1 footprints"):
        cleaned = clean_footprints(footprints, 0.6)
    assert len(cleaned) == 1
    assert len(cleaned[0][0].interiors) == 1
    assert cleaned[0][0].area == pytest.approx(900 - 100)


def test_invalid_footprints_are_repaired():
    from urbafoam.DataConversion import clean_footprints, footprints_to_mesh

    bowtie = Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])
    assert not bowtie.is_valid
    cleaned = clean_footprints([(bowtie, 5.0)], 0)
    assert all(fp.is_valid for fp, _ in cleaned)
    assert footprints_to_mesh(cleaned).volume == pytest.approx(5 * 50)


# ---------------------------------------------------------------------------- ground

def test_buildings_on_the_ground_are_extended_below_it():
    from urbafoam.DataConversion import GROUND_DEPTH, sink_into_ground

    on_ground = _box(0, 0, 10, 10, 10)
    slightly_above = _box(20, 0, 30, 10, 10, z0=0.2)
    bridge = _box(40, 0, 50, 10, 10, z0=5)
    sunk = sink_into_ground(trimesh.util.concatenate([on_ground, slightly_above, bridge]))
    parts = sorted(sunk.split(), key=lambda p: p.bounds[0][0])
    assert [p.bounds[0][2] for p in parts] == [-GROUND_DEPTH, -GROUND_DEPTH, 5]
    assert all(p.is_volume for p in parts)
    assert parts[0].bounds[1][2] == 10


def test_case_refines_from_the_ground_not_from_below_it(tmp_path):
    case = tmp_path / "case"
    invoke("setup", "-q", "quick", "-c", CONFIG, "-w", "0", "-m", TESTDATA / "buildings_small.stl", case)
    params = (case / "0" / "system" / "caseParameters").read_text()
    assert "zMin            0.0;" in params or "zMin            0;" in params
    analysis_min = [line for line in params.splitlines() if line.startswith("analysisMin")][0]
    assert analysis_min.rstrip(");").split()[-1] in ("0", "0.0")
    stl = trimesh.load(case / "0" / "constant" / "triSurface" / "buildings_small.stl")
    assert stl.bounds[0][2] < 0  # the buildings cut through the ground


# ---------------------------------------------------------------------------- surroundings

def test_surroundings_are_cropped_and_duplicates_removed():
    from urbafoam.DataConversion import crop_surroundings

    primary = _box(0, 0, 20, 20, 30)
    near, far = _box(30, 0, 40, 10, 10), _box(500, 0, 510, 10, 10)
    touching = _box(20, 0, 25, 10, 10)  # shares a wall with the primary building
    duplicate = _box(0, 0, 20, 20, 30)
    surroundings = trimesh.util.concatenate([near, far, touching, duplicate])
    with pytest.warns(UserWarning, match="left out 1 surrounding buildings that overlap"):
        cropped = crop_surroundings(surroundings, primary, radius=50)
    assert sorted(p.bounds[0][0] for p in cropped.split()) == [20, 30]


def test_surrounding_footprints_beyond_the_radius_are_not_meshed(tmp_path):
    import geopandas as gpd

    gpd.GeoDataFrame({"height": [10.0, 10.0]}, geometry=[box(250, 120, 260, 130), box(2000, 0, 2010, 10)],
                     crs="EPSG:3006").to_file(tmp_path / "around.gpkg")
    case = tmp_path / "case"
    invoke("setup", "-q", "quick", "-c", CONFIG, "-w", "0", "-m", TESTDATA / "buildings_small.stl",
           "-r", tmp_path / "around.gpkg", case)
    stl = trimesh.load(case / "0" / "constant" / "triSurface" / "around.stl")
    assert stl.bounds[1][0] < 300
    params = (case / "0" / "system" / "caseParameters").read_text()
    x_max = float([line for line in params.splitlines() if line.startswith("xMax")][0].split()[1].rstrip(";"))
    assert x_max < 1500  # the domain was not stretched to the far building


# ---------------------------------------------------------------------------- mesh size

def test_mesh_size_estimate_scales_with_the_cell_size(tmp_path):
    from urbafoam.Config import load_config
    from urbafoam.SetupCase import check_mesh_size, prepare_building_models
    from urbafoam.BlockMesh import setup_windtunnel
    from urbafoam.SnappyHexMesh import setup_snappy

    def estimate(cell_size):
        cfg, _ = load_config(CONFIG)
        cfg.models.primary_buildings = str(TESTDATA / "buildings_small.stl")
        cfg.windtunnel.cell_size = cell_size
        primary, _, _ = prepare_building_models(cfg)
        primary.rotate_and_save_mesh(270, tmp_path / str(cell_size))
        wt = setup_windtunnel(cfg.windtunnel, cfg.quality_level, primary.rotated_bounds, primary.rotated_bounds, 0)
        sn = setup_snappy(cfg.snappy, cfg.postprocess.sampleBuffer, wt, [primary, None])
        return check_mesh_size(270, wt, sn, [primary, None], cfg.snappy)

    coarse, fine = estimate(10), estimate(5)
    assert 1e5 < coarse < 1e6  # snappyHexMesh v2606 makes 0.4 million cells
    assert 4 < fine / coarse < 9


def test_too_large_mesh_is_reported(tmp_path):
    config = tmp_path / "urbafoam.toml"
    config.write_text(CONFIG.read_text() + '\n[snappy]\nmaxGlobalCells = 1000\n')
    with pytest.warns(UserWarning, match="more than maxGlobalCells"):
        invoke("setup", "-q", "quick", "-c", config, "-w", "0", "-m", TESTDATA / "buildings_small.stl",
               tmp_path / "case")
    assert "maxGlobalCells             1000;" in (tmp_path / "case" / "0" / "system" / "caseParameters").read_text()


def test_allrun_checks_the_mesh(tmp_path):
    case = tmp_path / "case"
    invoke("setup", "-q", "quick", "-c", CONFIG, "-w", "0", "-m", TESTDATA / "buildings_small.stl", case)
    allrun = (case / "0" / "Allrun").read_text()
    assert "run snappyHexMesh -overwrite\n        check_mesh" in allrun
    assert "checkMesh" in allrun and "cell limit" in allrun
