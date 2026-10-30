"""Built-in validators for integrations."""

from importlib import import_module
from types import ModuleType

from .model import Config

INTEGRATION_PLUGINS = ["codeowners", "json"]


def load_plugins(config: Config) -> list[ModuleType]:
    """Load selected validators in their required execution order."""
    return [
        import_module(f".{name}", __package__)
        for name in INTEGRATION_PLUGINS
        if name in config.plugins
    ]
