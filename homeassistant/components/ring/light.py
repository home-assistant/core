"""This component provides HA switch support for Ring Door Bell/Chimes."""
from datetime import timedelta
import logging
from typing import Any

import requests

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from . import DOMAIN
from .entity import RingEntityMixin

_LOGGER = logging.getLogger(__name__)


# It takes a few seconds for the API to correctly return an update indicating
# that the changes have been made. Once we request a change (i.e. a light
# being turned on) we simply wait for this time delta before we allow
# updates to take place.

SKIP_UPDATES_DELAY = timedelta(seconds=5)

ON_STATE = "on"
OFF_STATE = "off"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the lights for the Ring devices."""
    devices = hass.data[DOMAIN][config_entry.entry_id]["devices"]

    lights = []

    for device in devices["stickup_cams"]:
        if device.has_capability("light"):
            lights.append(RingLight(config_entry.entry_id, device))

    async_add_entities(lights)


class RingLight(RingEntityMixin, LightEntity):
    """Creates a switch to turn the ring cameras light on and off."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, config_entry_id, device):
        """Initialize the light."""
        super().__init__(config_entry_id, device)
        self._unique_id = device.id
        self._light_on = device.lights == ON_STATE
        self._no_updates_until = dt_util.utcnow()

    @callback
    def _update_callback(self):
        """Call update method."""
        if self._no_updates_until > dt_util.utcnow():
            return

        self._light_on = self._device.lights == ON_STATE
        self.async_write_ha_state()

    @property
    def name(self):
        """Name of the light."""
        return f"{self._device.name} light"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        return self._light_on

    def _set_light(self, new_state):
        """Update light state, and causes Home Assistant to correctly update."""
        try:
            self._device.lights = new_state
        except requests.Timeout:
            _LOGGER.error("Time out setting %s light to %s", self.entity_id, new_state)
            return

        self._light_on = new_state == ON_STATE
        self._no_updates_until = dt_util.utcnow() + SKIP_UPDATES_DELAY
        self.async_write_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on for 30 seconds."""
        self._set_light(ON_STATE)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._set_light(OFF_STATE)
