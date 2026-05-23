"""Remote-capable Home Assistant compatibility helpers."""

from .api import HomeAssistantAPI
from .config import RemoteConfig

__all__ = ["HomeAssistantAPI", "RemoteConfig", "RemoteHomeAssistant"]


def __getattr__(name: str):
    """Lazily import runtime objects to avoid importing Home Assistant too early."""
    if name == "RemoteHomeAssistant":
        from .runtime import RemoteHomeAssistant

        return RemoteHomeAssistant
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
