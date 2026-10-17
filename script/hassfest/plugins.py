"""Select and load hassfest validation and generation plugins."""

from importlib import import_module
from types import ModuleType

from hassfest.model import Config
from hassfest.plugins import INTEGRATION_PLUGINS as PACKAGE_PLUGINS

INTEGRATION_PLUGINS = list(PACKAGE_PLUGINS)
INTEGRATION_PLUGINS.insert(
    INTEGRATION_PLUGINS.index("integration_type"), "integration_info"
)

CORE_PLUGINS = [
    "core_files",
    "device_classes",
    "docker",
    "integration_categories",
    "mdi_icons",
    "mypy_config",
    "metadata",
    "sensor",
]

ALL_PLUGIN_NAMES = [*INTEGRATION_PLUGINS, *CORE_PLUGINS]
LOCAL_PLUGINS = {
    name: f"{__package__}.{name}"
    for name in (*CORE_PLUGINS, "codeowners", "integration_info")
}


def load_plugins(config: Config) -> list[ModuleType]:
    """Load selected plugins in validation order for this run."""
    names = INTEGRATION_PLUGINS if config.specific_integrations else ALL_PLUGIN_NAMES
    return [
        import_module(LOCAL_PLUGINS.get(name, f"hassfest.{name}"))
        for name in names
        if name in config.plugins
    ]
