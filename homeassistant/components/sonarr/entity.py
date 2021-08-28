"""Base Entity for Sonarr."""
from __future__ import annotations

from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_NAME,
    ATTR_SW_VERSION,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SonarrDataUpdateCoordinator


class SonarrEntity(CoordinatorEntity):
    """Defines a base Sonarr entity."""

    def __init__(
        self,
        *,
        coordinator: SonarrDataUpdateCoordinator,
        entry_id: str,
        device_id: str,
    ) -> None:
        """Initialize the Sonarr entity."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._device_id = device_id

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about the application."""
        if self._device_id is None:
            return None

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._device_id)},
            ATTR_NAME: "Activity Sensor",
            ATTR_MANUFACTURER: "Sonarr",
            ATTR_SW_VERSION: self.coordinator.sonarr.app.info.version,
            "entry_type": "service",
        }
