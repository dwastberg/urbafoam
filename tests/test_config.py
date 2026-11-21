"""Typed configuration: legacy migration, validation, quality switching and CLI precedence."""
import shutil

import pytest
import tomlkit
from click.testing import CliRunner

from tests.regression import CONFIG, TESTDATA, invoke
from urbafoam import cli
from urbafoam.Config import load_config

MODEL = TESTDATA / "buildings_small.stl"


def _setup_fails(*args):
    result = CliRunner().invoke(cli, ["setup", *map(str, args)])
    assert result.exit_code != 0
    return result.output


def test_legacy_config_is_migrated_and_comments_kept(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "urbafoam.toml").write_text(
        '# project notes\n'
        'out_dir = "/somewhere/else"\n'
        '[urbafoam.windtunnel]  # unquoted legacy section name\n'
        'downwind_buffer = 7  # upstream length\n'
        '["urbafoam.initalConditions"]\n'
        'Uref = 12\n'
        '["urbafoam.wind"]\n'
        'wind_directions = [0, 135]\n')
    cfg, _ = load_config(case_dir=case)
    assert cfg.windtunnel.inlet_buffer == 7
    assert cfg.windtunnel.outlet_buffer == 8  # quick default
    assert cfg.initial_conditions.Uref == 12

    invoke("setup", "-c", case / "urbafoam.toml", "-m", MODEL, case)
    text = (case / "urbafoam.toml").read_text()
    doc = tomlkit.parse(text)
    assert not [k for k in doc if k.startswith("urbafoam")]
    assert "out_dir" not in doc
    assert doc["windtunnel"]["inlet_buffer"] == 7
    assert "# project notes" in text and "# upstream length" in text


def test_unknown_key_is_reported(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "urbafoam.toml").write_text("[postprocess]\nsampleSpacng = 2.0\n")
    assert "sampleSpacng" in _setup_fails("-m", MODEL, case)


@pytest.mark.parametrize("section, line, message", [
    ("initial_conditions", 'turbulenceModel = "LES"', "LES"),
    ("initial_conditions", 'z0 = "desert"', "desert"),
    ("postprocess", 'outputFormat = "xls"', "xls"),
    ("parallel", "procs = 0", "procs"),
])
def test_invalid_values_are_reported(tmp_path, section, line, message):
    case = tmp_path / "case"
    case.mkdir()
    (case / "urbafoam.toml").write_text(f"[{section}]\n{line}\n")
    assert message in _setup_fails("-m", MODEL, case)


def test_changing_quality_updates_defaults_but_keeps_edits(tmp_path):
    case = tmp_path / "case"
    invoke("setup", "-q", "quick", "-c", CONFIG, "-m", MODEL, case)
    doc = tomlkit.parse((case / "urbafoam.toml").read_text())
    doc["snappy"]["SurfaceLayers"] = 5  # user edit (quick default is 2, normal default 3)
    (case / "urbafoam.toml").write_text(tomlkit.dumps(doc))

    invoke("setup", "-q", "normal", case)
    cfg, _ = load_config(case_dir=case)
    assert cfg.quality == "normal"
    assert cfg.snappy.CentralRefinement == 3
    assert cfg.controls.endTime == 1200
    assert cfg.initial_conditions.turbulenceModel == "KOmegaSST"
    assert cfg.snappy.SurfaceLayers == 5


def test_copied_case_is_regenerated_in_place(tmp_path):
    original, copy = tmp_path / "original", tmp_path / "copy"
    invoke("setup", "-q", "quick", "-c", CONFIG, "-m", MODEL, original)
    shutil.copytree(original, copy)
    shutil.rmtree(original / "0")
    invoke("setup", copy)
    assert not (original / "0").exists()
    assert (copy / "0" / "system" / "controlDict").exists()


def test_model_path_is_stored_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(TESTDATA)
    invoke("setup", "-q", "quick", "-c", CONFIG, "-m", "buildings_small.stl", tmp_path / "case")
    cfg, _ = load_config(case_dir=tmp_path / "case")
    assert cfg.models.primary_buildings == str(MODEL)


def test_missing_model_is_reported(tmp_path):
    assert "no building model given" in _setup_fails("-c", CONFIG, tmp_path / "case")
