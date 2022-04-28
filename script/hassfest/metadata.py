"""Package metadata validation."""
import configparser

from homeassistant.const import REQUIRED_PYTHON_VER, __version__

from .model import Config, Integration


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate project metadata keys."""
    metadata_path = config.root / "setup.cfg"
    parser = configparser.ConfigParser()
    parser.read(metadata_path)

    try:
        if parser["metadata"]["version"] != __version__:
            config.add_error(
                "metadata", f"'metadata.version' value does not match '{__version__}'"
            )
    except KeyError:
        config.add_error("metadata", "No 'metadata.version' key found!")

    required_py_version = f">={'.'.join(map(str, REQUIRED_PYTHON_VER))}"
    try:
        if parser["options"]["python_requires"] != required_py_version:
            config.add_error(
                "metadata",
                f"'options.python_requires' value doesn't match '{required_py_version}",
            )
    except KeyError:
        config.add_error("metadata", "No 'options.python_requires' key found!")
