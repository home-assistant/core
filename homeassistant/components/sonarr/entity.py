"""Base Entity for Sonarr."""
from __future__ import annotations

from sonarr import Sonarr

from homeassistant.const import ATTR_NAME
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import ATTR_IDENTIFIERS, ATTR_MANUFACTURER, ATTR_SOFTWARE_VERSION, DOMAIN


class SonarrEntity(Entity):
    """Defines a base Sonarr entity."""

    def __init__(
        self,
        *,
        sonarr: Sonarr,
        entry_id: str,
        device_id: str,
    ) -> None:
        """Initialize the Sonarr entity."""
        self._entry_id = entry_id
        self._device_id = device_id
        self.sonarr = sonarr

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about the application."""
        if self._device_id is None:
            return None

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._device_id)},
            ATTR_NAME: "Activity Sensor",
            ATTR_MANUFACTURER: "Sonarr",
            ATTR_SOFTWARE_VERSION: self.sonarr.app.info.version,
            "entry_type": "service",
        }
