"""Support for Soma Covers."""
import logging

import logging

from requests import RequestException

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASS_BLIND,
    DEVICE_CLASS_SHADE,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import API, DEVICES, DOMAIN, SomaEntity

from .const import MSG_API_UNREACHABLE, MSG_DEVICE_UNREACHABLE
from .utils import is_api_response_success

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Soma cover platform."""

    devices = hass.data[DOMAIN][DEVICES]
    entities = []

    for device in devices:
        # Assume a shade device if the type is not present in the api response (Connect <2.2.6)
        if "type" in device and device["type"].lower() == "tilt":
            entities.append(SomaTilt(device, hass.data[DOMAIN][API]))
        else:
            entities.append(SomaShade(device, hass.data[DOMAIN][API]))

    async_add_entities(entities, True)


class SomaTilt(SomaEntity, CoverEntity):
    """Representation of a Soma Tilt device."""

    @property
    def device_class(self):
        """Return the class of this device."""
        return DEVICE_CLASS_BLIND

    @property
    def supported_features(self):
        """Flag supported features."""
        return (
            SUPPORT_OPEN_TILT
            | SUPPORT_CLOSE_TILT
            | SUPPORT_STOP_TILT
            | SUPPORT_SET_TILT_POSITION
        )

    @property
    def current_cover_tilt_position(self):
        """Return the current cover tilt position."""
        return self.current_position

    @property
    def is_closed(self):
        """Return if the cover tilt is closed."""
        return self.current_position == 0

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        response = self.api.set_shade_position(self.device["mac"], 100)
        if is_api_response_success(response):
            self.set_position(0)
        else:
            _LOGGER.error(MSG_DEVICE_UNREACHABLE, self.device["name"], response["msg"])

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        response = self.api.set_shade_position(self.device["mac"], -100)
        if is_api_response_success(response):
            self.set_position(100)
        else:
            _LOGGER.error(MSG_DEVICE_UNREACHABLE, self.device["name"], response["msg"])

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover tilt."""
        response = self.api.stop_shade(self.device["mac"])
        if is_api_response_success(response):
            # Set cover position to some value where up/down are both enabled
            self.set_position(50)
        else:
            _LOGGER.error(MSG_DEVICE_UNREACHABLE, self.device["name"], response["msg"])

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        # 0 -> Closed down (api: 100)
        # 50 -> Fully open (api: 0)
        # 100 -> Closed up (api: -100)
        target_api_position = 100 - ((kwargs[ATTR_TILT_POSITION] / 50) * 100)
        response = self.api.set_shade_position(self.device["mac"], target_api_position)
        if is_api_response_success(response):
            self.set_position(kwargs[ATTR_TILT_POSITION])
        else:
            _LOGGER.error(MSG_DEVICE_UNREACHABLE, self.device["name"], response["msg"])

    async def async_update(self):
        """Update the entity with the latest data."""
        try:
            _LOGGER.debug("Soma Tilt Update")
            response = await self.hass.async_add_executor_job(
                self.api.get_shade_state, self.device["mac"]
            )
        except RequestException:
            _LOGGER.error(MSG_API_UNREACHABLE)
            self.is_available = False
            return

        if not is_api_response_success(response):
            _LOGGER.error(MSG_DEVICE_UNREACHABLE, self.device["name"], response["msg"])
            self.is_available = False
            return

        self.is_available = True
        api_position = int(response["position"])

        if "closed_upwards" in response.keys():
            self.current_position = 50 + ((api_position * 50) / 100)
        else:
            self.current_position = 50 - ((api_position * 50) / 100)


class SomaShade(SomaEntity, CoverEntity):
    """Representation of a Soma Shade device."""

    @property
    def device_class(self):
        """Return the class of this device."""
        return DEVICE_CLASS_SHADE

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION

    @property
    def current_cover_position(self):
        """Return the current cover position."""
        return self.current_position

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self.current_position == 0

    def close_cover(self, **kwargs):
        """Close the cover."""
        response = self.api.set_shade_position(self.device["mac"], 100)
        if not is_api_response_success(response):
            _LOGGER.error(MSG_DEVICE_UNREACHABLE, self.device["name"], response["msg"])

    def open_cover(self, **kwargs):
        """Open the cover."""
        response = self.api.set_shade_position(self.device["mac"], 0)
        if not is_api_response_success(response):
            _LOGGER.error(MSG_DEVICE_UNREACHABLE, self.device["name"], response["msg"])

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        response = self.api.stop_shade(self.device["mac"])
        if is_api_response_success(response):
            # Set cover position to some value where up/down are both enabled
            self.set_position(50)
        else:
            _LOGGER.error(MSG_DEVICE_UNREACHABLE, self.device["name"], response["msg"])

    def set_cover_position(self, **kwargs):
        """Move the cover shutter to a specific position."""
        self.current_position = kwargs[ATTR_POSITION]
        response = self.api.set_shade_position(
            self.device["mac"], 100 - kwargs[ATTR_POSITION]
        )
        if not is_api_response_success(response):
            _LOGGER.error(MSG_DEVICE_UNREACHABLE, self.device["name"], response["msg"])

    async def async_update(self):
        """Update the cover with the latest data."""
        try:
            _LOGGER.debug("Soma Shade Update")
            response = await self.hass.async_add_executor_job(
                self.api.get_shade_state, self.device["mac"]
            )
        except RequestException:
            _LOGGER.error(MSG_API_UNREACHABLE)
            self.is_available = False
            return
        if not is_api_response_success(response):
            _LOGGER.error(MSG_DEVICE_UNREACHABLE, self.device["name"], response["msg"])
            self.is_available = False
            return
        self.current_position = 100 - int(response["position"])
        self.is_available = True
