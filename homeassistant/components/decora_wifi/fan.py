"""Support for Decora Wifi Fan controls."""

import logging

from homeassistant.components.fan import ATTR_PERCENTAGE, SUPPORT_SET_SPEED, FanEntity

from .common import (
    DecoraWifiCommFailed,
    DecoraWifiEntity,
    DecoraWifiPlatform,
    DecoraWifiSessionNotFound,
)
from .const import CONF_FAN, DOMAIN, SPEEDS_FAN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Decora fans based on a config entry."""

    email = hass.data[DOMAIN][entry.entry_id]

    try:
        devices = await DecoraWifiPlatform.async_getdevices(hass, email)
    except DecoraWifiCommFailed:
        _LOGGER.error("Communication with Decora Wifi platform failed.")
    except DecoraWifiSessionNotFound:
        _LOGGER.error("DecoraWifi Session Not Found.")
    finally:
        fans = devices[CONF_FAN]
        entities = []
        if fans:
            for f in fans:
                entities.append(DecoraWifiDeviceFan(f))
        _LOGGER.debug(f"Decora Wifi: Setting up {len(entities)} Fans.")
        async_add_entities(entities, True)


class DecoraWifiDeviceFan(DecoraWifiEntity, FanEntity):
    """Representation of a Decora WiFi fan control."""

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_SET_SPEED

    @property
    def name(self):
        """Return the display name of this fan switch."""
        return self._switch.name

    @property
    def percentage(self):
        """Return the speed of the fan in percent."""
        maxlevel = self._switch.data.get("maxLevel", 100)
        return int(self._switch.brightness / maxlevel * 100)

    @property
    def speed_count(self):
        """Return the number of speeds supported by the fan."""
        return SPEEDS_FAN.get(self._switch.model, 100)

    @property
    def is_on(self):
        """Return true if fan switch is on."""
        return self._switch.power == "ON"

    async def async_turn_on(self, **kwargs):
        """Instruct the switch to turn on & adjust fan speed."""
        swdata = dict(self._switch.data)
        maxlevel = swdata.get("maxLevel", 100)
        minlevel = swdata.get("minLevel", 0)
        attribs = {"power": "ON"}

        pct = kwargs.get(ATTR_PERCENTAGE)
        if pct is not None:
            percentage = int(maxlevel * (pct / 100))
            percentage = max(percentage, minlevel)
            attribs["brightness"] = percentage

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
            await self.hass.async_add_executor_job(tryupdate)
        except ValueError:
            _LOGGER.error("Failed to turn off myLeviton switch")

    async def async_set_percentage(self, percentage: int):
        """Instruct the switch to turn on & adjust fan speed."""
        maxlevel = self._switch.data.get("maxLevel", 100)
        minlevel = self._switch.data.get("minLevel", 0)

        percentage = int(maxlevel * (percentage / 100))
        percentage = max(percentage, minlevel)
        attribs = {"brightness": percentage}

        def tryupdate():
            self._switch.update_attributes(attribs)

        try:
            await self.hass.async_add_executor_job(tryupdate)
        except ValueError:
            _LOGGER.error("Failed to turn on myLeviton switch")

    async def async_update(self):
        """Fetch new state data for this switch."""
        try:
            await self.hass.async_add_executor_job(self._switch.refresh)
        except ValueError:
            _LOGGER.error("Failed to update myLeviton switch data")
