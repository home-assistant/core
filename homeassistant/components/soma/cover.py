"""Support for Soma Covers."""

import logging

from requests import RequestException

from homeassistant.components.cover import ATTR_POSITION, CoverEntity
from homeassistant.components.soma import API, DEVICES, DOMAIN, SomaEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Soma cover platform."""

    devices = hass.data[DOMAIN][DEVICES]

    async_add_entities(
        [SomaCover(cover, hass.data[DOMAIN][API]) for cover in devices], True
    )


class SomaCover(SomaEntity, CoverEntity):
    """Representation of a Soma cover device."""

    def close_cover(self, **kwargs):
        """Close the cover."""
        response = self.api.set_shade_position(self.device["mac"], 100)
        if response["result"] != "success":
            _LOGGER.error(
                "Unable to reach device %s (%s)", self.device["name"], response["msg"]
            )

    def open_cover(self, **kwargs):
        """Open the cover."""
        response = self.api.set_shade_position(self.device["mac"], 0)
        if response["result"] != "success":
            _LOGGER.error(
                "Unable to reach device %s (%s)", self.device["name"], response["msg"]
            )

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        # Set cover position to some value where up/down are both enabled
        self.current_position = 50
        response = self.api.stop_shade(self.device["mac"])
        if response["result"] != "success":
            _LOGGER.error(
                "Unable to reach device %s (%s)", self.device["name"], response["msg"]
            )

    def set_cover_position(self, **kwargs):
        """Move the cover shutter to a specific position."""
        self.current_position = kwargs[ATTR_POSITION]
        response = self.api.set_shade_position(
            self.device["mac"], 100 - kwargs[ATTR_POSITION]
        )
        if response["result"] != "success":
            _LOGGER.error(
                "Unable to reach device %s (%s)", self.device["name"], response["msg"]
            )

    @property
    def current_cover_position(self):
        """Return the current position of cover shutter."""
        return self.current_position

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self.current_position == 0

    async def async_update(self):
        """Update the cover with the latest data."""
        try:
            _LOGGER.debug("Soma Cover Update")
            response = await self.hass.async_add_executor_job(
                self.api.get_shade_state, self.device["mac"]
            )
        except RequestException:
            _LOGGER.error("Connection to SOMA Connect failed")
            self.is_available = False
            return
        if response["result"] != "success":
            _LOGGER.error(
                "Unable to reach device %s (%s)", self.device["name"], response["msg"]
            )
            self.is_available = False
            return
        self.current_position = 100 - int(response["position"])
        self.is_available = True
