"""Support EZVIZ last motion image."""
from __future__ import annotations

import logging

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import (
    ConfigEntry,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
)
from homeassistant.util import dt as dt_util

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
)
from .coordinator import EzvizDataUpdateCoordinator
from .entity import EzvizEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EZVIZ image entities based on a config entry."""

    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities(
        EzvizLastMotion(hass, coordinator, camera) for camera in coordinator.data
    )


class EzvizLastMotion(EzvizEntity, ImageEntity):
    """Return Last Motion Image from Ezviz Camera."""

    _attr_has_entity_name = True

    def __init__(
        self, hass: HomeAssistant, coordinator: EzvizDataUpdateCoordinator, serial: str
    ) -> None:
        """Initialize a image entity."""
        super().__init__(coordinator, serial)
        ImageEntity.__init__(self, hass)
        self.hass = hass
        self._attr_unique_id = f"{serial}_last_motion_image"
        self._attr_name = "Last motion image"
        self.last_image_url = self.data["last_alarm_pic"]

    @property
    def image_url(self) -> str | None:
        """Return URL of image."""
        return self.last_image_url

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.data.get("last_alarm_pic"):
            return

        if self.last_image_url == self.data["last_alarm_pic"]:
            return

        _LOGGER.debug("Image url changed")
        self.last_image_url = self.data["last_alarm_pic"]
        self._cached_image = None
        self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()
