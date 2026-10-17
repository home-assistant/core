"""Capture release metadata and requirements in both the sdist and wheel."""

import json
from pathlib import Path
import shutil
import tomllib

from setuptools import setup

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
    DATA.mkdir(exist_ok=True)
    for filename in ("requirements.txt", "requirements_all.txt"):
        shutil.copyfile(CORE / filename, DATA / filename)
    (DATA / "build.json").write_text(
        json.dumps(
            {
                "version": project["version"],
                "requires-python": project["requires-python"],
            }
        )
    )

metadata = json.loads((DATA / "build.json").read_text())
setup(
    version=metadata["version"],
    python_requires=metadata["requires-python"],
    install_requires=[
        f"homeassistant=={metadata['version']}",
        "awesomeversion",
        "orjson",
        "packaging",
        "pipdeptree",
        "probatio",
        "ruff",
        "tqdm",
        "uv",
    ],
)
