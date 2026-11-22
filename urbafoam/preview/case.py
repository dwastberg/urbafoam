"""Read Urbafoam's generated case inputs and export the snapped boundary on demand."""

import re
import shutil
import subprocess
from pathlib import Path
from tempfile import mkdtemp
from threading import Lock


class PreviewError(ValueError):
    pass


def setup_scene(case):
    """Read the literal entries written by Urbafoam's case templates."""
    try:
        params = (case / "system/caseParameters").read_text()
        entries = dict(re.findall(r"^\s*(\w+)\s+([-+.\deE ()]+);", params, re.MULTILINE))
        domain = [float(entries[axis + end]) for axis in "xyz" for end in ("Min", "Max")]
        low, high = (entries[key].strip("()").split() for key in ("analysisMin", "analysisMax"))
        if len(low) != 3 or len(high) != 3:
            raise ValueError("expected three coordinates for the analysis box")
        refinement = [float(value) for pair in zip(low, high) for value in pair]
        geometry = (case / "system/buildingModels").read_text()
        names = re.findall(r'^\s*file\s+"([^"/]+\.stl)"\s*;', geometry, re.MULTILINE)
        models = [case / "constant/triSurface" / name for name in names]
        if not models or not all(path.is_file() for path in models):
            raise ValueError("missing building STL in constant/triSurface")
    except (OSError, KeyError, ValueError) as exc:
        raise PreviewError(f"Cannot read generated case {case}: {exc}") from exc
    return {"name": case.name, "domain": domain, "refinement": refinement,
            "models": [{"name": p.stem, "url": f"/models/{i}"} for i, p in enumerate(models)]}, models


def log_ending(path):
    with path.open("rb") as stream:
        size = stream.seek(0, 2)
        stream.seek(max(0, size - 8192))
        return stream.read()


def mesh_run(case):
    log = case / "log.snappyHexMesh"
    stamp = log.stat().st_mtime_ns if log.exists() else 0
    for stage in ("surfaceFeatureExtract", "blockMesh", "decomposePar"):
        other = case / f"log.{stage}"
        if other.exists() and other.stat().st_mtime_ns > stamp:
            if b"FOAM FATAL" in log_ending(other):
                raise PreviewError(f"{stage} failed. See {other.name}.")
            if stamp:
                raise PreviewError("A newer mesh run has started. Check the case logs and retry when it finishes.")
    if not stamp:
        raise PreviewError("Waiting for a snapped mesh. Run ./Allrun mesh in this case.")
    with log.open("rb") as stream:
        header = stream.read(8192)
    ending = log_ending(log)
    if b"FOAM FATAL" in ending:
        raise PreviewError("Meshing failed. See log.snappyHexMesh.")
    if not re.search(rb"^End\s*$", ending, re.MULTILINE) or b"Finished meshing" not in ending:
        raise PreviewError("Meshing is running or was interrupted. Check log.snappyHexMesh and retry.")
    ranks = re.search(rb"^nProcs\s*:\s*(\d+)", header, re.MULTILINE)
    if not ranks:
        raise PreviewError("Cannot determine the run's processor count from log.snappyHexMesh.")
    count = int(ranks[1])
    roots = [case / f"processor{i}" for i in range(count)] if count > 1 else [case]
    for root in roots:
        if not (root / "constant/polyMesh/boundary").is_file():
            raise PreviewError(f"Missing snapped mesh in {root.name}/constant/polyMesh.")
    return count, stamp


class MeshExport:
    def __init__(self, case, temp):
        self.case = case
        self.temp = temp
        self.lock = Lock()
        self.run = None
        self.layers = []
        self.files = {}

    def layers_for_run(self):
        with self.lock:
            run = mesh_run(self.case)
            if self.run == run:
                return self.layers
            count, _ = run
            if not shutil.which("foamToVTK") or (count > 1 and not shutil.which("mpirun")):
                raise PreviewError("Start urbafoam preview from an OpenFOAM environment to export this mesh.")
            directory = Path(mkdtemp(dir=self.temp))
            command = ["foamToVTK", "-case", str(self.case), "-name", str(directory),
                       "-time", "0", "-no-internal", "-no-fields", "-no-lagrangian",
                       "-no-finite-area", "-noFunctionObjects"]
            if count > 1:
                command = ["mpirun", "-np", str(count), *command, "-parallel"]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, errors="replace")
            if result.returncode:
                raise PreviewError(f"Boundary export failed (exit {result.returncode}).\n{result.stdout[-2000:]}")
            patches = sorted(directory.glob("*/boundary/*.vtp"))
            if not patches:
                raise PreviewError("foamToVTK produced no boundary patches at time 0.")
            if mesh_run(self.case) != run:
                raise PreviewError("The case was remeshed during export. Retry to load the new mesh.")
            layers = []
            for patch in patches:
                url = f"/patches/{directory.name}/{len(layers)}"
                self.files[url] = patch
                layers.append({"name": patch.stem, "url": url})
            self.layers, self.run = layers, run
            return layers
