"""Support EZVIZ last motion image."""

from __future__ import annotations

import logging

from propcache.api import cached_property
from pyezviz.exceptions import PyEzvizError
from pyezviz.utils import decrypt_image

from homeassistant.components.image import Image, ImageEntity, ImageEntityDescription
from homeassistant.config_entries import SOURCE_IGNORE
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EzvizConfigEntry, EzvizDataUpdateCoordinator
from .entity import EzvizEntity

_LOGGER = logging.getLogger(__name__)

IMAGE_TYPE = ImageEntityDescription(
    key="last_motion_image",
    translation_key="last_motion_image",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzvizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EZVIZ image entities based on a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        EzvizLastMotion(hass, coordinator, camera) for camera in coordinator.data
    )


class EzvizLastMotion(EzvizEntity, ImageEntity):
    """Return Last Motion Image from Ezviz Camera."""

    def __init__(
        self, hass: HomeAssistant, coordinator: EzvizDataUpdateCoordinator, serial: str
    ) -> None:
        """Initialize a image entity."""
        EzvizEntity.__init__(self, coordinator, serial)
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = f"{serial}_{IMAGE_TYPE.key}"
        self.entity_description = IMAGE_TYPE
        self._attr_image_url = self.data["last_alarm_pic"]
        self._attr_image_last_updated = dt_util.parse_datetime(
            str(self.data["last_alarm_time"])
        )
        camera = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, serial)
        self.alarm_image_password = (
            camera.data[CONF_PASSWORD]
            if camera and camera.source != SOURCE_IGNORE
            else None
        )

    @cached_property
    def available(self) -> bool:
        """Entity gets data from ezviz API so always available."""
        return True

    async def _async_load_image_from_url(self, url: str) -> Image | None:
        """Load an image by url."""
        if response := await self._fetch_url(url):
            image_data = response.content
            if self.data["encrypted"] and self.alarm_image_password is not None:
                try:
                    image_data = decrypt_image(
                        response.content, self.alarm_image_password
                    )
                except PyEzvizError:
                    _LOGGER.warning(
                        "%s: Can't decrypt last alarm picture, looks like it was encrypted with other password",
                        self.entity_id,
                    )
                    image_data = response.content
            return Image(
                content=image_data,
                content_type="image/jpeg",  # Actually returns binary/octet-stream
            )
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            self.data["last_alarm_pic"]
            and self.data["last_alarm_pic"] != self._attr_image_url
        ):
            _LOGGER.debug("Image url changed to %s", self.data["last_alarm_pic"])

            self._attr_image_url = self.data["last_alarm_pic"]
            self._cached_image = None
            self._attr_image_last_updated = dt_util.parse_datetime(
                str(self.data["last_alarm_time"])
            )

        super()._handle_coordinator_update()
