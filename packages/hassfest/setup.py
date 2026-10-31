"""Capture release metadata in both the sdist and wheel."""

import json
from pathlib import Path
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
else:
    metadata = json.loads((DATA / "build.json").read_text())


def bundle_metadata(destination: Path) -> None:
    """Write release metadata into a build directory."""
    destination.mkdir(parents=True, exist_ok=True)
    # The sdist staging tree may contain hard links to source files.
    (destination / "build.json").unlink(missing_ok=True)
    (destination / "build.json").write_text(json.dumps(metadata))


class BuildPy(build_py):
    """Bundle release metadata in the wheel's build directory."""

    def run(self) -> None:
        """Build package modules and release metadata."""
        super().run()
        bundle_metadata(Path(self.build_lib) / "hassfest/_data")


class Sdist(sdist):
    """Bundle release metadata in the source distribution's staging directory."""

    def make_release_tree(self, base_dir: str, files: list[str]) -> None:
        """Stage the package and its release snapshot."""
        super().make_release_tree(base_dir, files)
        bundle_metadata(Path(base_dir) / "hassfest/_data")


setup(
    cmdclass={"build_py": BuildPy, "sdist": Sdist},
    version=metadata["version"],
    python_requires=metadata["requires-python"],
)
