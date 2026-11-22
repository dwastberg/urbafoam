import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from urbafoam.preview.case import MeshExport, PreviewError, mesh_run, setup_scene


def test_setup_uses_rotated_case_models_and_domain(tmp_path):
    system = tmp_path / "system"
    system.mkdir()
    system.joinpath("caseParameters").write_text(
        "xMin -1e1;\nxMax 4;\nyMin -7;\nyMax 9;\nzMin 0;\nzMax 6;\n"
        "analysisMin (-1 -2 0);\nanalysisMax (3 4 5);\n")
    system.joinpath("buildingModels").write_text('file "primary.stl";\nfile "around.stl";\nfile "primary.eMesh";')
    surface = tmp_path / "constant/triSurface"
    surface.mkdir(parents=True)
    for name in ("around", "primary", "obsolete"):
        (surface / f"{name}.stl").touch()
    scene, paths = setup_scene(tmp_path)
    assert paths == [surface / "primary.stl", surface / "around.stl"]
    assert scene["domain"] == [-10, 4, -7, 9, 0, 6]
    assert scene["refinement"] == [-1, 3, -2, 4, 0, 5]


def test_mesh_status_during_run_and_after_restart(tmp_path):
    log = tmp_path / "log.snappyHexMesh"
    block = tmp_path / "log.blockMesh"
    block.touch()
    with pytest.raises(PreviewError, match="Waiting"):
        mesh_run(tmp_path)
    log.write_text("nProcs : 1\nSnapping...\n")
    with pytest.raises(PreviewError, match="interrupted"):
        mesh_run(tmp_path)
    log.write_text("FOAM FATAL ERROR")
    with pytest.raises(PreviewError, match="Meshing failed"):
        mesh_run(tmp_path)
    log.write_text("nProcs : 1\nFinished meshing in = 1 s.\nEnd\n")
    os.utime(log, (1, 1))
    with pytest.raises(PreviewError, match="newer mesh run"):
        mesh_run(tmp_path)


@pytest.mark.parametrize("ranks", [1, 2])
def test_export_uses_completed_run_and_reuses_patches(tmp_path, monkeypatch, ranks):
    case = tmp_path / "case"
    case.mkdir()
    (case / "log.snappyHexMesh").write_text(f"nProcs : {ranks}\nFinished meshing\nEnd\n")
    (case / "constant/polyMesh").mkdir(parents=True)
    (case / "constant/polyMesh/boundary").touch()
    if ranks > 1:
        with pytest.raises(PreviewError, match="Missing snapped mesh"):
            mesh_run(case)
        for i in range(ranks):
            mesh = case / f"processor{i}/constant/polyMesh"
            mesh.mkdir(parents=True)
            (mesh / "boundary").touch()

    def convert(command, **kwargs):
        parallel = ranks > 1
        assert ("-parallel" in command) == parallel
        if parallel:
            assert command[:3] == ["mpirun", "-np", str(ranks)]
        assert "-no-fields" in command and "-no-internal" in command
        directory = Path(command[command.index("-name") + 1]) / "case_0/boundary"
        directory.mkdir(parents=True)
        (directory / "building.vtp").touch()
        return Mock(returncode=0)

    runner = Mock(side_effect=convert)
    monkeypatch.setattr("urbafoam.preview.case.shutil.which", lambda exe: exe)
    monkeypatch.setattr("urbafoam.preview.case.subprocess.run", runner)
    export = MeshExport(case, tmp_path)
    layers = export.layers_for_run()
    assert [layer["name"] for layer in layers] == ["building"]
    assert export.files[layers[0]["url"]].is_file()
    assert export.layers_for_run() == layers
    assert runner.call_count == 1
