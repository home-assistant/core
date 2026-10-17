"""Capture release metadata and requirements in both the sdist and wheel."""

import json
from pathlib import Path
import shutil
import tomllib

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

PACKAGE = Path(__file__).resolve().parent
CORE = PACKAGE.parent.parent
DATA = PACKAGE / "hassfest/_data"

# A source checkout supplies fresh data. An extracted sdist supplies the snapshot
# captured when that sdist was built and does not need its original checkout.
if (
    PACKAGE == CORE / "packages/hassfest"
    and (CORE / "homeassistant/const.py").is_file()
):
    project = tomllib.loads((CORE / "pyproject.toml").read_text())["project"]
    metadata = {
        "version": project["version"],
        "requires-python": project["requires-python"],
    }
    requirements_source = CORE
else:
    metadata = json.loads((DATA / "build.json").read_text())
    requirements_source = DATA


def bundle_data(destination: Path) -> None:
    """Write the release snapshot into a build directory."""
    destination.mkdir(parents=True, exist_ok=True)
    # The sdist staging tree may contain hard links to source files.
    for filename in ("requirements.txt", "requirements_all.txt", "build.json"):
        (destination / filename).unlink(missing_ok=True)
    for filename in ("requirements.txt", "requirements_all.txt"):
        shutil.copyfile(requirements_source / filename, destination / filename)
    (destination / "build.json").write_text(json.dumps(metadata))


class BuildPy(build_py):
    """Bundle reference data in the wheel's build directory."""

    def run(self) -> None:
        """Build package modules and reference data."""
        super().run()
        bundle_data(Path(self.build_lib) / "hassfest/_data")


class Sdist(sdist):
    """Bundle reference data in the source distribution's staging directory."""

    def make_release_tree(self, base_dir: str, files: list[str]) -> None:
        """Stage the package and its release snapshot."""
        super().make_release_tree(base_dir, files)
        bundle_data(Path(base_dir) / "hassfest/_data")


setup(
    cmdclass={"build_py": BuildPy, "sdist": Sdist},
    version=metadata["version"],
    python_requires=metadata["requires-python"],
    install_requires=[
        f"homeassistant=={metadata['version']}",
        "ruff",
    ],
)
