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
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired as kelvin_to_mired,
    color_temperature_mired_to_kelvin as mired_to_kelvin,
)

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


class TPLinkSmartBulb(CoordinatorEntity, LightEntity):
    """Representation of a TPLink Smart Bulb."""

    def __init__(
        self, smartbulb: SmartBulb, coordinator: DataUpdateCoordinator
    ) -> None:
        """Initialize the bulb."""
        super().__init__(coordinator)
        self.smartbulb = smartbulb

    @property
    def data(self) -> dict[str, Any]:
        """Return data from DataUpdateCoordinator."""
        return self.coordinator.data

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self.smartbulb.device_id

    @property
    def name(self) -> str | None:
        """Return the name of the Smart Bulb."""
        return self.smartbulb.alias

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return {
            "name": self.smartbulb.alias,
            "model": self.smartbulb.model,
            "manufacturer": "TP-Link",
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.smartbulb.device_id)},
            "sw_version": self.smartbulb.hw_info["sw_ver"],
        }

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
            await self.smartbulb.set_color_temp(
                color_tmp, brightness=brightness, transition=transition
            )
            return

        # Handling turning to hs color mode
        if ATTR_HS_COLOR in kwargs:
            # TP-Link requires integers.
            hue_sat = tuple(int(val) for val in kwargs[ATTR_HS_COLOR])
            hue, sat = hue_sat
            await self.smartbulb.set_hsv(hue, sat, brightness, transition=transition)
            return

        # Fallback to adjusting brightness or turning the bulb on
        if brightness is not None:
            await self.smartbulb.set_brightness(brightness, transition=transition)
        else:
            await self.smartbulb.turn_on(transition=transition)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.smartbulb.turn_off(transition=kwargs.get(ATTR_TRANSITION))

    @property
    def min_mireds(self) -> int:
        """Return minimum supported color temperature."""
        return kelvin_to_mired(self.smartbulb.valid_temperature_range.max)

    @property
    def max_mireds(self) -> int:
        """Return maximum supported color temperature."""
        return kelvin_to_mired(self.smartbulb.valid_temperature_range.min)

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature of this light in mireds for HA."""
        return kelvin_to_mired(self.smartbulb.color_temp)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return brightness_from_percentage(self.smartbulb.brightness)

    @property
    def hs_color(self) -> tuple[int, int] | None:
        """Return the color."""
        h, s, _ = self.smartbulb.hsv
        return h, s

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.smartbulb.is_on

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_TRANSITION

    @property
    def supported_color_modes(self) -> set[str] | None:
        """Return list of available color modes."""
        modes = set()
        if self.smartbulb.is_variable_color_temp:
            modes.add(COLOR_MODE_COLOR_TEMP)
        if self.smartbulb.is_color:
            modes.add(COLOR_MODE_HS)
        if self.smartbulb.is_dimmable:
            modes.add(COLOR_MODE_BRIGHTNESS)

        return modes

    @property
    def color_mode(self) -> str | None:
        """Return the active color mode."""
        if self.smartbulb.is_color:
            if self.smartbulb.color_temp:
                return COLOR_MODE_COLOR_TEMP
            else:
                return COLOR_MODE_HS
        elif self.smartbulb.is_variable_color_temp:
            return COLOR_MODE_COLOR_TEMP

        return COLOR_MODE_BRIGHTNESS
