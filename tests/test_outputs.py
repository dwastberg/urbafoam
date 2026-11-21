"""GIS outputs of `urbafoam postprocess` must carry the same data as the (golden) csv output."""
import geopandas as gpd
import numpy as np
import pytest

from tests.regression import GOLDEN, invoke, run_case

EXT = {"geojson": "json", "shp": "shp", "gpkg": "gpkg"}


@pytest.fixture(scope="module")
def shp_case(tmp_path_factory):
    return run_case("shp", tmp_path_factory.mktemp("outputs") / "case")


@pytest.mark.parametrize("fmt", sorted(EXT))
def test_gis_outputs_match_csv(shp_case, fmt):
    invoke("postprocess", "-f", fmt, shp_case)
    results = shp_case / "results"
    for height in (2, 10):
        golden = np.loadtxt(GOLDEN / "shp" / "results" / f"samplePoints_{height}m_U_pts.csv", delimiter=",", skiprows=1)
        pts = gpd.read_file(results / f"samplePoints_{height}m_U_pts.{EXT[fmt]}")
        xyz = np.array([(g.x, g.y, g.z) for g in pts.geometry])
        np.testing.assert_allclose(xyz, golden[:, :3], rtol=0, atol=1e-6)
        np.testing.assert_allclose(pts[["w_dir0", "w_dir135"]].to_numpy(), golden[:, 3:], rtol=1e-6)

        for w in (0, 135):
            golden_vec = np.loadtxt(GOLDEN / "shp" / "results" / f"windVectors_samplePoints_{height}m_{w}.csv",
                                    delimiter=",", skiprows=1)
            vec = gpd.read_file(results / f"windVectors_samplePoints_{height}m_{w}.{EXT[fmt]}")
            coords = np.array([np.ravel(g.coords) for g in vec.geometry])
            np.testing.assert_allclose(coords, golden_vec[:, :6], rtol=0, atol=1e-6)
            np.testing.assert_allclose(vec["speedup"], golden_vec[:, 6], rtol=1e-6)


@pytest.mark.parametrize("fmt", ["shp", "gpkg"])
def test_gis_outputs_carry_input_crs(shp_case, fmt):
    invoke("postprocess", "-f", fmt, shp_case)
    out = gpd.read_file(shp_case / "results" / f"samplePoints_2m_U_pts.{EXT[fmt]}")
    assert out.crs is not None and out.crs.to_epsg() == 3003
