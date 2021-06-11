"""Base Entity for Sonarr."""
from __future__ import annotations

from sonarr import Sonarr

from homeassistant.const import ATTR_NAME
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_SOFTWARE_VERSION,
    DOMAIN,
)


class SonarrEntity(Entity):
    """Defines a base Sonarr entity."""

    def __init__(
        self,
        *,
        sonarr: Sonarr,
        entry_id: str,
        device_id: str,
        name: str,
        icon: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the Sonarr entity."""
        self._entry_id = entry_id
        self._device_id = device_id
        self._enabled_default = enabled_default
        self._icon = icon
        self._name = name
        self.sonarr = sonarr

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

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
