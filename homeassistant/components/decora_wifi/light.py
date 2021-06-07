"""Interfaces with the myLeviton API for Decora Smart WiFi products."""

import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.const import CONF_USERNAME

from .common import (
    DecoraWifiCommFailed,
    DecoraWifiEntity,
    DecoraWifiPlatform,
    DecoraWifiSessionNotFound,
)
from .const import LIGHT_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Decora Wifi lights based on a config entry."""

    email = entry.data[CONF_USERNAME]

    try:
        devices = await DecoraWifiPlatform.async_getdevices(hass, email)
    except DecoraWifiCommFailed:
        _LOGGER.error("Communication with Decora Wifi platform failed.")
    except DecoraWifiSessionNotFound:
        _LOGGER.error("DecoraWifi Session not found.")

    lights = devices[LIGHT_DOMAIN]
    entities = []
    if lights:
        for light in lights:
            entities.append(DecoraWifiLight(light))
    async_add_entities(entities, True)


class DecoraWifiLight(DecoraWifiEntity, LightEntity):
    """Representation of a Decora WiFi switch."""

    @property
    def unique_id(self):
        """Return the unique id of the switch."""
        return self._unique_id

    @property
    def supported_features(self):
        """Return supported features."""
        if self._switch.canSetLevel:
            return SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION
        return 0

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._switch.name

    @property
    def brightness(self):
        """Return the brightness of the dimmer switch."""
        return int(self._switch.brightness * 255 / 100)

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._switch.power == "ON"

    async def async_turn_on(self, **kwargs):
        """Instruct the switch to turn on & adjust brightness."""
        attribs = {"power": "ON"}

        if ATTR_BRIGHTNESS in kwargs:
            maxlevel = self._switch.data.get("maxLevel", 100)
            minlevel = self._switch.data.get("minLevel", 100)
            brightness = int(kwargs[ATTR_BRIGHTNESS] * maxlevel / 255)
            brightness = max(brightness, minlevel)
            attribs["brightness"] = brightness

        if ATTR_TRANSITION in kwargs:
            transition = int(kwargs[ATTR_TRANSITION])
            attribs["fadeOnTime"] = attribs["fadeOffTime"] = transition

        def tryupdate():
            self._switch.update_attributes(attribs)

        try:
            await self.hass.async_add_executor_job(tryupdate)
        except ValueError:
            _LOGGER.error("Failed to turn on myLeviton switch")

    async def async_turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        attribs = {"power": "OFF"}

        def tryupdate():
            self._switch.update_attributes(attribs)

        try:
            self._switch.update_attributes(tryupdate)
        except ValueError:
            _LOGGER.error("Failed to turn off myLeviton switch")

    async def async_update(self):
        """Fetch new state data for this switch."""
        try:
            await self.hass.async_add_executor_job(self._switch.refresh)
        except ValueError:
            _LOGGER.error("Failed to update myLeviton switch data")
