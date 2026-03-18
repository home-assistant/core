"""Runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os


def _env_flag(name: str, default: bool) -> bool:
    """Parse a boolean environment flag."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class RemoteConfig:
    """Configuration for remote Home Assistant sync."""

    websocket_url: str | None = None
    token: str | None = None
    ssl: bool = True
    sync_states: bool = True
    sync_entity_registry: bool = True
    sync_remote_services: bool = True

    @property
    def enabled(self) -> bool:
        """Return if remote sync is configured."""
        return bool(self.websocket_url)

    @classmethod
    def from_env(cls) -> RemoteConfig:
        """Load configuration from the environment."""
        return cls(
            websocket_url=os.environ.get("HASS_CLIENT_WS_URL"),
            token=os.environ.get("HASS_CLIENT_TOKEN"),
            ssl=_env_flag("HASS_CLIENT_SSL", True),
            sync_states=_env_flag("HASS_CLIENT_SYNC_STATES", True),
            sync_entity_registry=_env_flag("HASS_CLIENT_SYNC_ENTITY_REGISTRY", True),
            sync_remote_services=_env_flag("HASS_CLIENT_SYNC_REMOTE_SERVICES", True),
        )
