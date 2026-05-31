"""Generate MDI icons file for the pylint plugin."""

from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
import json

from .model import Config, Integration
from .serializer import format_python_namespace

_TARGET = "pylint/plugins/pylint_home_assistant/generated/mdi_icons.py"


def _get_frontend_version() -> str | None:
    """Get the installed home-assistant-frontend version."""
    try:
        return version("home-assistant-frontend")
    except PackageNotFoundError:
        return None


def _load_mdi_icons() -> set[str]:
    """Load the MDI icon names from the frontend package."""
    try:
        mdi_dir = files("hass_frontend") / "static" / "mdi"
        icon_list_path = mdi_dir / "iconList.json"
        data = json.loads(icon_list_path.read_text(encoding="utf-8"))
        return {icon["name"] for icon in data}
    except ImportError, FileNotFoundError, json.JSONDecodeError, KeyError:
        return set()


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate the generated MDI icons file is up to date."""
    frontend_version = _get_frontend_version()
    if frontend_version is None:
        return

    icons = _load_mdi_icons()
    if not icons:
        config.add_error(
            "mdi_icons",
            "Could not load MDI icons from home-assistant-frontend",
        )
        return

    content = format_python_namespace(
        {
            "FRONTEND_VERSION": frontend_version,
            "MDI_ICONS": icons,
        },
        annotations={
            "FRONTEND_VERSION": "Final[str]",
            "MDI_ICONS": "Final[set[str]]",
        },
    )

    config.cache["mdi_icons_content"] = content

    if config.specific_integrations:
        return

    target_path = config.root / _TARGET
    if not target_path.exists() or target_path.read_text() != content:
        config.add_error(
            "mdi_icons",
            f"File {_TARGET} is not up to date. Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate MDI icons file."""
    if "mdi_icons_content" not in config.cache:
        return
    target_path = config.root / _TARGET
    target_path.write_text(config.cache["mdi_icons_content"])
