"""Regression tests for specific bugs fixed after the poetry -> uv migration."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from tests.regression import CONFIG, TESTDATA, invoke, write_fake_results


def _write_rotation(case, angle_deg, centerpoint):
    a = np.radians(angle_deg)
    R = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    case.mkdir(parents=True, exist_ok=True)
    (case / "rotation_matrix.json").write_text(
        json.dumps({"rot_matrix": R.tolist(), "centerpoint": list(centerpoint), "offset": [0, 0, 0]}))
    return R


def test_scalar_and_vector_fields_are_rotated_back_consistently(tmp_path):
    from urbafoam.PostProcess import orient_sample_date

    c = np.array([100.0, 50.0, 0.0])
    R = _write_rotation(tmp_path, 30, c)
    original = np.array([[110.0, 55.0, 2.0], [90.0, 40.0, 2.0], [130.0, 70.0, 2.0]])
    rotated = (original - c).dot(R) + c
    out = tmp_path / "postProcessing" / "sampleDict" / "800"
    out.mkdir(parents=True)
    k, p = np.array([0.1, 0.2, 0.3]), np.array([1.0, 2.0, 3.0])
    U = np.array([[1.0, 0, 0], [2.0, 0, 0], [3.0, 0, 0]])
    # OpenFOAM's raw set writer puts all scalar fields in one file and all vectors in another
    np.savetxt(out / "s_k_p.xy", np.column_stack([rotated, k, p]), delimiter="\t")
    np.savetxt(out / "s_U.xy", np.column_stack([rotated, U]), delimiter="\t")

    p_data = orient_sample_date(tmp_path, "s", "p")
    np.testing.assert_allclose(p_data[:, :3], original, atol=1e-9)
    np.testing.assert_allclose(p_data[:, 3], p)

    k_data = orient_sample_date(tmp_path, "s", "k")
    np.testing.assert_allclose(k_data[:, 3], k)

    u_data = orient_sample_date(tmp_path, "s", "U")
    np.testing.assert_allclose(u_data[:, :3], original, atol=1e-9)
    np.testing.assert_allclose(u_data[:, 6], [1, 2, 3])


def test_combined_set_file_of_openfoam_v2606(tmp_path):
    """v2606 writes all fields of a set into one `<set>_k_p_U.xy`, columns `x y z k p Ux Uy Uz`."""
    from urbafoam.PostProcess import load_sample_points

    pts = np.array([[1.0, 2.0, 2.0], [3.0, 4.0, 2.0]])
    k, p = np.array([0.1, 0.2]), np.array([5.0, 6.0])
    U = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    out = tmp_path / "postProcessing" / "sampleDict" / "800"
    out.mkdir(parents=True)
    np.savetxt(out / "s_k_p_U.xy", np.column_stack([pts, k, p, U]), delimiter="\t")

    for field, expected in [("k", k[:, None]), ("p", p[:, None]), ("U", U)]:
        xyz, values = load_sample_points(tmp_path, "s", field)
        np.testing.assert_allclose(xyz, pts)
        np.testing.assert_allclose(values, expected)


def test_normalize_scalar_field(tmp_path):
    from urbafoam.PostProcess import normalize_oriented_data

    c = np.array([0.0, 0.0, 0.0])
    _write_rotation(tmp_path / "270", 0, c)
    pts = np.array([[0.0, 0, 2], [10, 0, 2], [0, 10, 2], [10, 10, 2]])
    out = tmp_path / "270" / "postProcessing" / "sampleDict" / "800"
    out.mkdir(parents=True)
    np.savetxt(out / "s_k_p.xy", np.column_stack([pts, [0, 0, 0, 0], [1.0, 2, 3, 4]]), delimiter="\t")
    base, data = normalize_oriented_data(pts[:, :2], tmp_path, [270], 10, "s", field="p")
    np.testing.assert_allclose(data[0], [1, 2, 3, 4])


def test_missing_sample_output_gives_clear_error(tmp_path):
    from urbafoam.PostProcess import load_sample_points

    (tmp_path / "postProcessing" / "sampleDict").mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="Has the simulation run"):
        load_sample_points(tmp_path, "s", "U")
    with pytest.raises(FileNotFoundError, match="Has the simulation run"):
        load_sample_points(tmp_path / "nope", "s", "U")


@pytest.mark.parametrize("wind", ["0,90", "0,22.5"])
def test_postprocess_finds_cases_for_float_wind_directions(tmp_path, wind):
    case = tmp_path / "case"
    invoke("setup", "-q", "quick", "-c", CONFIG, "-w", wind, "-m", TESTDATA / "buildings_small.stl", case)
    expected_dirs = {"0", "90"} if wind == "0,90" else {"0", "22.5"}
    assert {p.name for p in case.iterdir() if (p / "rotation_matrix.json").exists()} == expected_dirs
    assert all(f"{d}/Allrun" in (case / "RunAllCases").read_text() for d in expected_dirs)
    write_fake_results(case)
    invoke("postprocess", case)
    assert (case / "results" / "samplePoints_2m_U_pts.csv").exists()


def test_model_type_lookup():
    from urbafoam.Enums import ModelType, modelTypeLookup

    assert modelTypeLookup["dense_urban"] is ModelType.DENSE_URBAN
    assert modelTypeLookup["forest"] is ModelType.FOREST


def test_missing_sample_points_file_is_rejected(tmp_path):
    from click.testing import CliRunner
    from urbafoam import cli

    result = CliRunner().invoke(cli, ["setup", "-q", "quick", "-c", str(CONFIG), "-s", str(tmp_path / "does_not_exist.txt"),
                                      "-m", str(TESTDATA / "buildings_small.stl"), str(tmp_path / "case")])
    assert result.exit_code != 0
    assert "does_not_exist.txt" in result.output and "does not exist" in result.output


def test_missing_sample_points_file_in_config_raises(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "urbafoam.toml").write_text(f'[postprocess]\nsamplePoints = "{tmp_path / "nope.txt"}"\n')
    with pytest.raises(FileNotFoundError, match="nope.txt"):
        invoke("setup", "-q", "quick", "-m", TESTDATA / "buildings_small.stl", case)


def test_integer_roughness_in_config(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "urbafoam.toml").write_text(CONFIG.read_text() + '\n["urbafoam.initalconditions"]\nz0 = 1\n')
    invoke("setup", "-q", "quick", "-m", TESTDATA / "buildings_small.stl", case)
    abl = (case / "0" / "0.orig" / "include" / "ABLConditions").read_text()
    assert "z0                   uniform 1.0;" in abl


def test_footprints_multipolygon_and_missing_height(tmp_path):
    from urbafoam.DataConversion import footprint_to_mesh

    def square(x, y, s=10):
        return [[[x, y], [x + s, y], [x + s, y + s], [x, y + s], [x, y]]]

    features = [
        {"type": "Feature", "properties": {"height": 10},
         "geometry": {"type": "MultiPolygon", "coordinates": [square(0, 0), square(20, 0)]}},
        {"type": "Feature", "properties": {"height": None},
         "geometry": {"type": "Polygon", "coordinates": square(40, 0)}},
        {"type": "Feature", "properties": {"height": 5},
         "geometry": {"type": "Polygon", "coordinates": square(60, 0)}},
    ]
    path = tmp_path / "fp.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    with pytest.warns(UserWarning, match="skipped 1 footprints"):
        mesh = footprint_to_mesh(path, "height")
    assert mesh.volume == pytest.approx(2 * 10 * 100 + 5 * 100)


def test_snappy_with_two_primary_models_does_not_mutate_bounds():
    from urbafoam.Config import QUALITY_DEFAULTS, SnappyConfig
    from urbafoam.Enums import MeshTypes
    from urbafoam.SnappyHexMesh import setup_snappy

    def model(name, bounds):
        return SimpleNamespace(type=MeshTypes.PRIMARY, name=name, file_name=f"{name}.stl",
                               rotated_bounds=list(zip(*bounds)))

    a = model("a", [(0, 0, 0), (10, 10, 20)])
    b = model("b", [(-5, 2, 0), (8, 30, 40)])
    a_before = list(a.rotated_bounds)
    windtunnel = {"background_minx": 0, "background_miny": 0, "background_maxz": 100}
    data = setup_snappy(SnappyConfig(**QUALITY_DEFAULTS["quick"]["snappy"]), 10, windtunnel, [a, b])
    assert a.rotated_bounds == a_before
    assert (data["analysis_minx"], data["analysis_maxy"], data["analysis_maxz"]) == (-5 - 15, 30 + 15, 40)


def test_setup_keeps_user_comments_in_config(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "urbafoam.toml").write_text(
        "# my project notes\n" + CONFIG.read_text().replace("procs = 4", "procs = 4  # cluster node size"))
    invoke("setup", "-q", "quick", "-m", TESTDATA / "buildings_small.stl", case)
    text = (case / "urbafoam.toml").read_text()
    assert "# my project notes" in text
    assert "# cluster node size" in text
    assert "sampleBuffer" in text  # defaults are still written out


def test_adjacent_buildings_are_merged_watertight():
    from shapely.geometry import box
    from urbafoam.DataConversion import footprints_to_mesh

    # two buildings sharing a wall, far from the origin like projected coordinates
    x0, y0 = 1_394_600.0, 4_989_700.0
    mesh = footprints_to_mesh([(box(x0, y0, x0 + 10, y0 + 10), 12.0), (box(x0 + 10, y0, x0 + 25, y0 + 8), 6.0)])
    assert mesh.is_watertight
    assert mesh.volume == pytest.approx(10 * 10 * 12 + 15 * 8 * 6, rel=1e-9)
    assert mesh.bounds[0].tolist() == pytest.approx([x0, y0, 0])


def test_obj_model_is_converted_to_stl(tmp_path):
    import trimesh
    from urbafoam.DataConversion import make_building_mesh

    box = trimesh.creation.box(extents=(10, 20, 30))
    box.apply_translation([105, 210, 15])
    box.export(tmp_path / "model.obj")
    stl_file, crs = make_building_mesh(tmp_path / "model.obj", tmp_path)
    assert stl_file == tmp_path / "model.stl" and crs is None
    np.testing.assert_allclose(trimesh.load(stl_file).bounds, [[100, 200, 0], [110, 220, 30]])
