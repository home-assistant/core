"""Support for Freedompro light."""
import json
import math

from pyfreedompro import put_state

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_HS,
    COLOR_MODE_ONOFF,
    LightEntity,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro light."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(hass, api_key, device, coordinator)
        for device in coordinator.data
        if device["type"] == "lightbulb"
    )


class Device(CoordinatorEntity, LightEntity):
    """Representation of an Freedompro light."""

    def __init__(self, hass, api_key, device, coordinator):
        """Initialize the Freedompro light."""
        super().__init__(coordinator)
        self._hass = hass
        self._session = aiohttp_client.async_get_clientsession(self._hass)
        self._api_key = api_key
        self._attr_name = device["name"]
        self._attr_unique_id = device["uid"]
        self._type = device["type"]
        self._characteristics = device["characteristics"]
        self._attr_is_on = False
        self._attr_brightness = 0
        self._saturation = 0
        self._hue = 0

    @property
    def hs_color(self):
        """Return the status of the light hs_color."""
        return [self._hue, self._saturation]

    @property
    def color_mode(self):
        """Return the color mode of the light."""
        if "hue" in self._characteristics:
            return COLOR_MODE_HS
        if "brightness" in self._characteristics:
            return COLOR_MODE_BRIGHTNESS
        return COLOR_MODE_ONOFF

    @property
    def supported_color_modes(self):
        """Flag supported color modes."""
        return {self.color_mode}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = next(
            (
                device
                for device in self.coordinator.data
                if device["uid"] == self._attr_unique_id
            ),
            None,
        )
        if device is not None and "state" in device:
            state = device["state"]
            if "on" in state:
                self._attr_is_on = state["on"]
            if "brightness" in state:
                self._attr_brightness = math.floor(state["brightness"] / 100 * 255)
            if "hue" in state:
                self._hue = state["hue"]
            if "saturation" in state:
                self._saturation = state["saturation"]
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs):
        """Async function to set on to light."""
        self._attr_is_on = True
        payload = {"on": True}
        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = math.floor(kwargs[ATTR_BRIGHTNESS] / 255 * 100)
            payload["brightness"] = self._attr_brightness
        if ATTR_HS_COLOR in kwargs:
            self._saturation = math.floor(kwargs[ATTR_HS_COLOR][1])
            self._hue = math.floor(kwargs[ATTR_HS_COLOR][0])
            payload["saturation"] = self._saturation
            payload["hue"] = self._hue
        payload = json.dumps(payload)
        await put_state(
            self._session,
            self._api_key,
            self._attr_unique_id,
            payload,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Async function to set off to light."""
        self._attr_is_on = False
        payload = {"on": False}
        payload = json.dumps(payload)
        await put_state(
            self._session,
            self._api_key,
            self._attr_unique_id,
            payload,
        )
        await self.coordinator.async_request_refresh()
