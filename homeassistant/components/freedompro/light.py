"""Support for Freedompro light."""
import json

from pyfreedompro import put_state

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
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
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._api_key = api_key
        self._attr_name = device["name"]
        self._attr_unique_id = device["uid"]
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, self.unique_id),
            },
            manufacturer="Freedompro",
            model=device["type"],
            name=self.name,
        )
        self._attr_is_on = False
        self._attr_brightness = 0
        color_mode = ColorMode.ONOFF
        if "hue" in device["characteristics"]:
            color_mode = ColorMode.HS
        elif "brightness" in device["characteristics"]:
            color_mode = ColorMode.BRIGHTNESS
        self._attr_color_mode = color_mode
        self._attr_supported_color_modes = {color_mode}

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
                self._attr_brightness = round(state["brightness"] / 100 * 255)
            if "hue" in state and "saturation" in state:
                self._attr_hs_color = (state["hue"], state["saturation"])
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_turn_on(self, **kwargs):
        """Async function to set on to light."""
        payload = {"on": True}
        if ATTR_BRIGHTNESS in kwargs:
            payload["brightness"] = round(kwargs[ATTR_BRIGHTNESS] / 255 * 100)
        if ATTR_HS_COLOR in kwargs:
            payload["saturation"] = round(kwargs[ATTR_HS_COLOR][1])
            payload["hue"] = round(kwargs[ATTR_HS_COLOR][0])
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
        payload = {"on": False}
        payload = json.dumps(payload)
        await put_state(
            self._session,
            self._api_key,
            self._attr_unique_id,
            payload,
        )
        await self.coordinator.async_request_refresh()
