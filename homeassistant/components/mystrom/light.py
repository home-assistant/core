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
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "myStrom bulb"

EFFECT_RAINBOW = "rainbow"
EFFECT_SUNRISE = "sunrise"

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
    device = hass.data[DOMAIN][entry.entry_id].device
    async_add_entities([MyStromLight(device, entry.title, info["mac"])])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the myStrom light integration."""
    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2023.12.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "myStrom",
        },
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


class MyStromLight(LightEntity):
    """Representation of the myStrom WiFi bulb."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_color_mode = ColorMode.HS
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_supported_features = LightEntityFeature.EFFECT | LightEntityFeature.FLASH
    _attr_effect_list = [EFFECT_RAINBOW, EFFECT_SUNRISE]

    def __init__(self, bulb, name, mac):
        """Initialize the light."""
        self._bulb = bulb
        self._attr_available = False
        self._attr_unique_id = mac
        self._attr_hs_color = 0, 0
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=name,
            manufacturer=MANUFACTURER,
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
            if self.hs_color is not None:
                color_h, color_s = self.hs_color
            else:
                color_h, color_s = 0, 0  # Back to white
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
            self._attr_is_on = self._bulb.state

            colors = self._bulb.color
            try:
                color_h, color_s, color_v = colors.split(";")
            except ValueError:
                color_s, color_v = colors.split(";")
                color_h = 0

            self._attr_hs_color = int(color_h), int(color_s)
            self._attr_brightness = int(int(color_v) * 255 / 100)

            self._attr_available = True
        except MyStromConnectionError:
            _LOGGER.warning("No route to myStrom bulb")
            self._attr_available = False
