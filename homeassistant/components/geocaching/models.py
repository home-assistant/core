"""Define DataUpdate Coordinator, Base Entity and Device models for Geocaching API."""
from __future__ import annotations

from typing import TypedDict

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import GeocachingDataUpdateCoordinator


class GeocachingEntity(CoordinatorEntity):
    """Define a base Geocaching entity."""

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        *,
        name: str,
        icon: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize a Geocaching entity."""
        super().__init__(coordinator)
        self._enabled_default = enabled_default
        self._icon = icon
        self._name = name
        self._state = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str | None:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default


class GeocachingSensorSettings(TypedDict):
    """Define Sensor settings class."""

    name: str
    section: str
    state: str
    unit_of_measurement: str | None
    device_class: str | None
    icon: str
    default_enabled: bool
