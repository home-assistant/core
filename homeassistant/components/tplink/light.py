"""Support for TPLink lights."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from kasa import SmartBulb

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.components.tplink import TPLinkDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired as kelvin_to_mired,
    color_temperature_mired_to_kelvin as mired_to_kelvin,
)

from .common import CoordinatedTPLinkEntity
from .const import CONF_LIGHT, COORDINATORS, DOMAIN as TPLINK_DOMAIN

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=5)
CURRENT_POWER_UPDATE_INTERVAL = timedelta(seconds=60)
HISTORICAL_POWER_UPDATE_INTERVAL = timedelta(minutes=60)

_LOGGER = logging.getLogger(__name__)

ATTR_CURRENT_POWER_W = "current_power_w"
ATTR_DAILY_ENERGY_KWH = "daily_energy_kwh"
ATTR_MONTHLY_ENERGY_KWH = "monthly_energy_kwh"


# TODO: this is c&p from switch.py, refactor
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    entities: list[TPLinkSmartBulb] = []
    coordinators: list[TPLinkDataUpdateCoordinator] = hass.data[TPLINK_DOMAIN][
        COORDINATORS
    ]
    devs: list[SmartBulb] = hass.data[TPLINK_DOMAIN][CONF_LIGHT]
    for dev in devs:
        coordinator = coordinators[dev.device_id]
        entities.append(TPLinkSmartBulb(dev, coordinator))

    async_add_entities(entities)


def brightness_to_percentage(byt):
    """Convert brightness from absolute 0..255 to percentage."""
    return round((byt * 100.0) / 255.0)


def brightness_from_percentage(percent):
    """Convert percentage to absolute value 0..255."""
    return round((percent * 255.0) / 100.0)


class TPLinkSmartBulb(CoordinatedTPLinkEntity, LightEntity):
    """Representation of a TPLink Smart Bulb."""

    def __init__(
        self, smartbulb: SmartBulb, coordinator: DataUpdateCoordinator
    ) -> None:
        """Initialize the bulb."""
        super().__init__(smartbulb, coordinator)
        self.device = smartbulb

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        _LOGGER.debug("Turning on %s", kwargs)

        transition = kwargs.get(ATTR_TRANSITION, None)
        brightness = kwargs.get(ATTR_BRIGHTNESS, None)
        if brightness is not None:
            brightness = int(brightness_to_percentage(brightness))

        # Handle turning to temp mode
        if ATTR_COLOR_TEMP in kwargs:
            color_tmp = mired_to_kelvin(int(kwargs[ATTR_COLOR_TEMP]))
            _LOGGER.info("Changing color temp to %s", color_tmp)
            await self.device.set_color_temp(
                color_tmp, brightness=brightness, transition=transition
            )
            return

        # Handling turning to hs color mode
        if ATTR_HS_COLOR in kwargs:
            # TP-Link requires integers.
            hue_sat = tuple(int(val) for val in kwargs[ATTR_HS_COLOR])
            hue, sat = hue_sat
            await self.device.set_hsv(hue, sat, brightness, transition=transition)
            return

        # Fallback to adjusting brightness or turning the bulb on
        if brightness is not None:
            await self.device.set_brightness(brightness, transition=transition)
        else:
            await self.device.turn_on(transition=transition)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.device.turn_off(transition=kwargs.get(ATTR_TRANSITION))

    @property
    def min_mireds(self) -> int:
        """Return minimum supported color temperature."""
        return kelvin_to_mired(self.device.valid_temperature_range.max)

    @property
    def max_mireds(self) -> int:
        """Return maximum supported color temperature."""
        return kelvin_to_mired(self.device.valid_temperature_range.min)

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature of this light in mireds for HA."""
        return kelvin_to_mired(self.device.color_temp)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return brightness_from_percentage(self.device.brightness)

    @property
    def hs_color(self) -> tuple[int, int] | None:
        """Return the color."""
        h, s, _ = self.device.hsv
        return h, s

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_TRANSITION

    @property
    def supported_color_modes(self) -> set[str] | None:
        """Return list of available color modes."""
        modes = set()
        if self.device.is_variable_color_temp:
            modes.add(COLOR_MODE_COLOR_TEMP)
        if self.device.is_color:
            modes.add(COLOR_MODE_HS)
        if self.device.is_dimmable:
            modes.add(COLOR_MODE_BRIGHTNESS)

        return modes

    @property
    def color_mode(self) -> str | None:
        """Return the active color mode."""
        if self.device.is_color:
            if self.device.color_temp:
                return COLOR_MODE_COLOR_TEMP
            else:
                return COLOR_MODE_HS
        elif self.device.is_variable_color_temp:
            return COLOR_MODE_COLOR_TEMP

        return COLOR_MODE_BRIGHTNESS
