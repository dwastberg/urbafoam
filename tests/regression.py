"""Golden-file regression harness for urbafoam.

`run_case` runs `urbafoam setup`, writes deterministic synthetic OpenFOAM sample output into
every wind-direction case, then runs `urbafoam postprocess`. `snapshot` turns the resulting case
directory into a comparable form, and `compare_snapshot` checks it against tests/golden/.

Regenerate the golden files (only after verifying a change is intended) with:
    uv run python -m tests.make_golden
"""
import json
import shutil
from pathlib import Path

import numpy as np
import trimesh
from click.testing import CliRunner

from urbafoam import cli
from urbafoam.Config import load_config

TESTS_DIR = Path(__file__).parent
TESTDATA = TESTS_DIR / "testdata"
GOLDEN = TESTS_DIR / "golden"
CONFIG = TESTS_DIR / "data" / "regression.toml"

CASES = {
    "stl": "buildings_small.stl",
    "shp": "buildings.shp",
}

NUMERIC_FILES = {"sample_points.txt"}
SAMPLE_TIME = "800"


def invoke(*args):
    result = CliRunner().invoke(cli, [str(a) for a in args], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return result


def case_dirs(case_dir):
    """Wind-direction case directories, i.e. those holding a rotation_matrix.json."""
    return sorted(p.parent for p in case_dir.glob("*/rotation_matrix.json"))


def write_fake_results(case_dir, heights=(2, 10)):
    """Write deterministic OpenFOAM-like sampleDict output for k, p and U.

    Uses the layout of OpenFOAM v2606's raw set writer: one tab separated `<set>_k_p_U.xy`
    file per set with columns `x y z k p Ux Uy Uz`.

    About 15% of the sample points are dropped (as if inside buildings) and the rest are
    jittered slightly, so the post-processing filtering and interpolation are exercised.
    """
    base = np.loadtxt(case_dir / "sample_points.txt")
    idx = np.arange(len(base))
    keep = (idx * 7919) % 100 >= 15
    jitter = 0.05 * np.column_stack([np.sin(idx[keep] * 1.3), np.cos(idx[keep] * 0.7)])
    for wd in case_dirs(case_dir):
        rot = json.loads((wd / "rotation_matrix.json").read_text())
        R, c = np.array(rot["rot_matrix"]), np.array(rot["centerpoint"])
        wind_dir = float(wd.name)
        for h in heights:
            pts = (base[keep] - c).dot(R) + c + np.array([0, 0, h])
            pts[:, :2] += jitter
            u = np.column_stack([
                5 + np.sin(pts[:, 0] / 7.0) + wind_dir / 100,
                np.cos(pts[:, 1] / 5.0),
                0.1 * np.sin(pts[:, 0] * pts[:, 1] / 50.0),
            ])
            out = wd / "postProcessing" / "sampleDict" / SAMPLE_TIME
            out.mkdir(parents=True, exist_ok=True)
            k = 0.5 + 0.1 * np.cos(pts[:, 0] / 3.0)
            p = 0.2 * np.sin(pts[:, 1] / 4.0)
            np.savetxt(out / f"samplePoints_{h}m_k_p_U.xy", np.column_stack([pts, k, p, u]), delimiter="\t",
                       fmt="%.8g")


def run_case(name, out_dir, postprocess_format="csv"):
    model = TESTDATA / CASES[name]
    invoke("setup", "-q", "quick", "-c", CONFIG, "-m", model, out_dir)
    write_fake_results(out_dir)
    invoke("postprocess", "-f", postprocess_format, out_dir)
    return out_dir


def mesh_summary(path):
    m = trimesh.load(path, force="mesh")
    return {
        "bounds": np.round(m.bounds, 3).tolist(),
        "area": round(float(m.area), 2),
        "volume": round(float(m.volume), 2),
    }


def _normalise_text(text, case_dir):
    return text.replace(str(case_dir), "<CASE>").replace(str(TESTDATA), "<TESTDATA>")


def snapshot(case_dir, dest):
    """Copy a finished case into `dest` in golden form (paths normalised, meshes summarised)."""
    case_dir = Path(case_dir)
    if dest.exists():
        shutil.rmtree(dest)
    meshes = {}
    for f in sorted(case_dir.rglob("*")):
        if not f.is_file() or "postProcessing" in f.parts:
            continue
        rel = f.relative_to(case_dir)
        if f.suffix == ".stl":
            meshes[rel.as_posix()] = mesh_summary(f)
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_normalise_text(f.read_text(), case_dir))
    (dest / "meshes.json").write_text(json.dumps(meshes, indent=1, sort_keys=True) + "\n")


def _load_config(path):
    """Config as validated by urbafoam itself, so old-layout golden files compare by meaning."""
    return load_config(path)[0].model_dump()


def compare_snapshot(actual, golden):
    """Return a list of human-readable differences between two snapshot directories."""
    problems = []
    a_files = {p.relative_to(actual) for p in actual.rglob("*") if p.is_file()}
    g_files = {p.relative_to(golden) for p in golden.rglob("*") if p.is_file()}
    for missing in sorted(g_files - a_files):
        problems.append(f"missing file: {missing}")
    for extra in sorted(a_files - g_files):
        problems.append(f"unexpected file: {extra}")

    for rel in sorted(a_files & g_files):
        a, g = actual / rel, golden / rel
        if rel.name == "meshes.json":
            am, gm = json.loads(a.read_text()), json.loads(g.read_text())
            if am.keys() != gm.keys():
                problems.append(f"mesh files differ: {sorted(am)} vs {sorted(gm)}")
            for k in am.keys() & gm.keys():
                for prop in ("bounds", "area", "volume"):
                    if not np.allclose(am[k][prop], gm[k][prop], rtol=1e-4, atol=1e-2):
                        problems.append(f"{k}: {prop} {am[k][prop]} != golden {gm[k][prop]}")
        elif rel.name == "urbafoam.toml":
            if _load_config(a) != _load_config(g):
                problems.append(f"{rel}: config differs\n  actual: {_load_config(a)}\n  golden: {_load_config(g)}")
        elif rel.name in NUMERIC_FILES or rel.suffix == ".csv":
            skip = 1 if rel.suffix == ".csv" else 0
            delim = "," if rel.suffix == ".csv" else None
            av = np.loadtxt(a, delimiter=delim, skiprows=skip, ndmin=2)
            gv = np.loadtxt(g, delimiter=delim, skiprows=skip, ndmin=2)
            if rel.suffix == ".csv" and a.read_text().splitlines()[0] != g.read_text().splitlines()[0]:
                problems.append(f"{rel}: csv header differs")
            if av.shape != gv.shape:
                problems.append(f"{rel}: shape {av.shape} != golden {gv.shape}")
            elif not np.allclose(av, gv, rtol=1e-7, atol=1e-6):
                problems.append(f"{rel}: values differ (max abs diff {np.max(np.abs(av - gv)):.3g})")
        elif a.read_text() != g.read_text():
            problems.append(f"{rel}: text differs")
    return problems
