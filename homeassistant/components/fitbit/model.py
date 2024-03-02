"""Data representation for fitbit API responses."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .const import CONF_CLOCK_FORMAT, CONF_MONITORED_RESOURCES, FitbitScope


@dataclass
class FitbitProfile:
    """User profile from the Fitbit API response."""

    encoded_id: str
    """The ID representing the Fitbit user."""

    display_name: str
    """The name shown when the user's friends look at their Fitbit profile."""

    locale: str | None
    """The locale defined in the user's Fitbit account settings."""


@dataclass
class FitbitDevice:
    """Device from the Fitbit API response."""

    id: str
    """The device ID."""

    device_version: str
    """The product name of the device."""

    battery_level: int
    """The battery level as a percentage."""

    battery: str
    """Returns the battery level of the device."""

    type: str
    """The type of the device such as TRACKER or SCALE."""


@dataclass
class FitbitConfig:
    """Information from the fitbit ConfigEntry data."""

    clock_format: str | None
    monitored_resources: set[str] | None
    scopes: set[FitbitScope]

    def is_explicit_enable(self, key: str) -> bool:
        """Determine if entity is enabled by default."""
        if self.monitored_resources is not None:
            return key in self.monitored_resources
        return False

    def is_allowed_resource(self, scope: FitbitScope | None, key: str) -> bool:
        """Determine if an entity is allowed to be created."""
        if self.is_explicit_enable(key):
            return True
        return scope in self.scopes


def config_from_entry_data(data: Mapping[str, Any]) -> FitbitConfig:
    """Parse the integration config entry into a FitbitConfig."""

    clock_format = data.get(CONF_CLOCK_FORMAT)

    # Originally entities were configured explicitly from yaml config. Newer
    # configurations will infer which entities to enable based on the allowed
    # scopes the user selected during OAuth. When creating entities based on
    # scopes, some entities are disabled by default.
    monitored_resources = data.get(CONF_MONITORED_RESOURCES)
    fitbit_scopes: set[FitbitScope] = set({})
    if scopes := data["token"].get("scope"):
        fitbit_scopes = set({FitbitScope(scope) for scope in scopes.split(" ")})
    return FitbitConfig(clock_format, monitored_resources, fitbit_scopes)
