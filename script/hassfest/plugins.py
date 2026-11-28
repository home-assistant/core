"""Select and load hassfest validation and generation plugins."""

from importlib import import_module
from types import ModuleType

from .model import Config

INTEGRATION_PLUGINS = [
    "application_credentials",
    "bluetooth",
    "codeowners",
    "conditions",
    "config_schema",
    "dependencies",
    "dhcp",
    "icons",
    "integration_info",
    "integration_type",
    "json",
    "labs",
    "lorawan",
    "manifest",
    "mqtt",
    "quality_scale",
    "requirements",
    "services",
    "ssdp",
    "translations",
    "triggers",
    "usb",
    "zeroconf",
    "config_flow",  # Must run after translations.
]

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


def load_plugins(config: Config) -> list[ModuleType]:
    """Load selected plugins in validation order for this run."""
    names = INTEGRATION_PLUGINS if config.specific_integrations else ALL_PLUGIN_NAMES
    return [
        import_module(f".{name}", __package__)
        for name in names
        if name in config.plugins
    ]
