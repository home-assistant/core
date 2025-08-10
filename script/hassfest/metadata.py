"""Package metadata validation."""

import tomllib

from homeassistant.const import REQUIRED_PYTHON_VER, __version__

from .model import Config, Integration


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate project metadata keys."""
    metadata_path = config.root / "pyproject.toml"
    data = tomllib.loads(metadata_path.read_text())

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
