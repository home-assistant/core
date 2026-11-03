"""Set a package's version to the Home Assistant release being published."""

import argparse
from pathlib import Path
import tomllib


def main() -> None:
    """Set the package version and pin homeassistant if the package uses it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="Path to the package directory")
    path = parser.parse_args().package / "pyproject.toml"

    version = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
    content = path.read_text()
    if content.count('version = "0.0.0"') != 1:
        raise SystemExit(f'Expected exactly one version = "0.0.0" in {path}')
    content = content.replace('version = "0.0.0"', f'version = "{version}"')
    # Fixtures reach into Core internals, so only the matching release works.
    content = content.replace('"homeassistant",', f'"homeassistant=={version}",')
    path.write_text(content)


if __name__ == "__main__":
    main()
