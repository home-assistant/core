"""Support for myStrom Wifi bulbs."""
from __future__ import annotations

import logging
from typing import Any

from pymystrom.exceptions import MyStromConnectionError
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_MANUFACTURER, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "myStrom bulb"

EFFECT_RAINBOW = "rainbow"
EFFECT_SUNRISE = "sunrise"

MYSTROM_EFFECT_LIST = [EFFECT_RAINBOW, EFFECT_SUNRISE]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the myStrom entities."""
    info = hass.data[DOMAIN][entry.entry_id].info
    device_type = info["type"]

    if device_type == 102:
        device = hass.data[DOMAIN][entry.entry_id].device
        async_add_entities([MyStromLight(device, info["mac"])])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the myStrom light integration."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2023.12.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


class MyStromLight(LightEntity):
    """Representation of the myStrom WiFi bulb."""

    _attr_color_mode = ColorMode.HS
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_supported_features = LightEntityFeature.EFFECT | LightEntityFeature.FLASH

    def __init__(self, bulb, mac):
        """Initialize the light."""
        self._bulb = bulb
        self._state = None
        self._available = False
        self._brightness = 0
        self._color_h = 0
        self._color_s = 0
        self._mac = mac

    @property
    def name(self):
        """Return the display name of this light."""
        return self._mac

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._mac

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the color of the light."""
        return self._color_h, self._color_s

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return MYSTROM_EFFECT_LIST

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info for the light entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=self.name,
            manufacturer=ATTR_MANUFACTURER,
            sw_version=self._bulb.firmware,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        effect = kwargs.get(ATTR_EFFECT)

        if ATTR_HS_COLOR in kwargs:
            color_h, color_s = kwargs[ATTR_HS_COLOR]
        elif ATTR_BRIGHTNESS in kwargs:
            # Brightness update, keep color
            color_h, color_s = self._color_h, self._color_s
        else:
            color_h, color_s = 0, 0  # Back to white

        try:
            if not self.is_on:
                await self._bulb.set_on()
            if brightness is not None:
                await self._bulb.set_color_hsv(
                    int(color_h), int(color_s), round(brightness * 100 / 255)
                )
            if effect == EFFECT_SUNRISE:
                await self._bulb.set_sunrise(30)
            if effect == EFFECT_RAINBOW:
                await self._bulb.set_rainbow(30)
        except MyStromConnectionError:
            _LOGGER.warning("No route to myStrom bulb")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the bulb."""
        try:
            await self._bulb.set_off()
        except MyStromConnectionError:
            _LOGGER.warning("The myStrom bulb not online")

    async def async_update(self) -> None:
        """Fetch new state data for this light."""
        try:
            await self._bulb.get_state()
            self._state = self._bulb.state

            colors = self._bulb.color
            try:
                color_h, color_s, color_v = colors.split(";")
            except ValueError:
                color_s, color_v = colors.split(";")
                color_h = 0

            self._color_h = int(color_h)
            self._color_s = int(color_s)
            self._brightness = int(color_v) * 255 / 100

            self._available = True
        except MyStromConnectionError:
            _LOGGER.warning("No route to myStrom bulb")
            self._available = False
