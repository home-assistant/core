"""Built-in validators for integrations."""

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


def load_plugins(config: Config) -> list[ModuleType]:
    """Load selected validators in their required execution order."""
    return [
        import_module(f".{name}", __package__)
        for name in INTEGRATION_PLUGINS
        if name in config.plugins
    ]
