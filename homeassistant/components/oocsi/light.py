"""Platform for sensor integration."""
from __future__ import annotations
from typing import Any
from homeassistant.components import light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW,
    COLOR_MODE_UNKNOWN,
    COLOR_MODE_WHITE,
    FLASH_LONG,
    FLASH_SHORT,
    SUPPORT_EFFECT,
    SUPPORT_FLASH,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.core import callback
from .const import DOMAIN
from . import async_create_new_platform_entity

# Handle platform
async def async_setup_entry(hass, ConfigEntry, async_add_entities):
    """Set up the Oocsi light platform."""
    # Add the corresponding oocsi server
    api = hass.data[DOMAIN][ConfigEntry.entry_id]
    platform = "light"
    # Create entities >  __init__.py
    await async_create_new_platform_entity(
        hass, ConfigEntry, api, BasicLight, async_add_entities, platform
    )


class BasicLight(LightEntity):
    # Import & configure entity
    def __init__(self, hass, entity_name, api, entityProperty):
        # Basic variables
        self._hass = hass
        self._oocsi = api
        self._name = entity_name

        # Set properties
        self._attr_unique_id = entityProperty["channelName"]
        self._oocsichannel = entityProperty["channelName"]
        self._channelState = entityProperty["state"]
        self._brightness = entityProperty["brightness"]
        self._supportedFeature = entityProperty["type"]
        self._rgb_color = None
        self._attr_supported_color_modes = set()
        if entityProperty["color_mode"] == "rgb_color":
            self._attr_supported_color_modes.add(COLOR_MODE_RGB)

    async def async_added_to_hass(self) -> None:
        @callback
        def channelUpdateEvent(sender, recipient, event):
            self._channelState = event["state"]
            self.brightness = event["brightness"]
            self.async_write_ha_state()

        self._oocsi.subscribe(self._oocsichannel, channelUpdateEvent)

    @property
    def color_mode(self):
        return COLOR_MODE_RGB

    # @property
    # def supported_features(self):
    #     """Flag supported features."""
    #     return self._supportedFeature

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def device_info(self):
        return {"name": self._name}

    @property
    def icon(self) -> str:
        """Return the icon."""
        # return self._static_info.icon
        return "mdi:toggle-switch"

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._channelState

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""

        self._rgb_color = kwargs.get(ATTR_RGB_COLOR, self._rgb_color)
        self._oocsi.send(self._oocsichannel, {"colour": self._rgb_color})
        self._brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
        self._oocsi.send(self._oocsichannel, {"brightness": self._brightness})
        self._channelState = True
        self._oocsi.send(self._oocsichannel, {"state": True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._oocsi.send(self._oocsichannel, {"state": False})
        self._channelState = False
