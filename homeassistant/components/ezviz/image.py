"""Support EZVIZ last motion image."""
from __future__ import annotations

import logging

import httpx

from homeassistant.components.image import Image, ImageEntity
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
GET_IMAGE_TIMEOUT = 10


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
        self._attr_image_url = self.data["last_alarm_pic"]
        self._attr_image_last_updated = dt_util.parse_datetime(
            str(self.data["last_alarm_time"])
        )

    async def _async_load_image_from_url(self, url: str) -> Image | None:
        """Load an image by url."""
        try:
            response = await self._client.get(
                url, timeout=GET_IMAGE_TIMEOUT, follow_redirects=True
            )
            response.raise_for_status()
            return Image(
                content=response.content,
                content_type="image/jpeg",
            )
        except httpx.TimeoutException:
            _LOGGER.error("%s: Timeout getting image from %s", self.entity_id, url)
            return None
        except (httpx.RequestError, httpx.HTTPStatusError) as err:
            _LOGGER.error(
                "%s: Error getting new image from %s: %s",
                self.entity_id,
                url,
                err,
            )
            return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.data.get("last_alarm_pic"):
            return

        _LOGGER.debug("Image url changed")
        self._attr_image_url = self.data["last_alarm_pic"]
        self._cached_image = None
        self._attr_image_last_updated = dt_util.parse_datetime(
            str(self.data["last_alarm_time"])
        )
        super()._handle_coordinator_update()
