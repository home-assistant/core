"""Support EZVIZ last motion image."""
from __future__ import annotations

import logging

import httpx

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import (
    ConfigEntry,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import (
    config_validation as cv,
    template as template_helper,
)
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
)
from homeassistant.helpers.httpx_client import get_async_client

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
    """Set up EZVIZ cameras based on a config entry."""

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
        ImageEntity.__init__(self)
        self.hass = hass
        self._attr_unique_id = f"{serial}_last_motion_image"
        self._attr_name = "Last motion image"

        self._last_url = None
        self._last_image: bytes | None = None

    async def async_image(self) -> bytes | None:
        """Return last still image response from EZVIZ api."""
        try:
            url = self._still_image_url.async_render(parse_result=False)
        except TemplateError as err:
            _LOGGER.error("Error parsing template %s: %s", self._still_image_url, err)
            return self._last_image

        if url == self._last_url:
            return self._last_image

        try:
            async_client = get_async_client(self.hass, verify_ssl=True)
            response = await async_client.get(
                url, timeout=GET_IMAGE_TIMEOUT, follow_redirects=True
            )
            response.raise_for_status()
            self._last_image = response.content
        except httpx.TimeoutException:
            _LOGGER.error("Timeout getting camera image from %s", self.name)
            return self._last_image
        except (httpx.RequestError, httpx.HTTPStatusError) as err:
            _LOGGER.error("Error getting new camera image from %s: %s", self.name, err)
            return self._last_image

        self._last_url = url
        return self._last_image

    @property
    def _still_image_url(self) -> template_helper.Template:
        """Return the template for the image."""
        _api_image_url = cv.template(self.data["last_alarm_pic"])
        _api_image_url.hass = self.hass

        return _api_image_url
