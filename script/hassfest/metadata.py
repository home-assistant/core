"""Package metadata validation."""
import sys

from homeassistant.const import REQUIRED_PYTHON_VER, __version__

from .model import Config, Integration

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate project metadata keys."""
    metadata_path = config.root / "pyproject.toml"
    with open(metadata_path, "rb") as fp:
        data = tomllib.load(fp)

    try:
        if data["project"]["version"] != __version__:
            config.add_error(
                "metadata", f"'project.version' value does not match '{__version__}'"
            )
    except KeyError:
        config.add_error("metadata", "No 'metadata.version' key found!")

    required_py_version = f">={'.'.join(map(str, REQUIRED_PYTHON_VER))}"
    try:
        if data["project"]["requires-python"] != required_py_version:
            config.add_error(
                "metadata",
                f"'project.requires-python' value doesn't match '{required_py_version}'",
            )
    except KeyError:
        config.add_error("metadata", "No 'options.python_requires' key found!")
