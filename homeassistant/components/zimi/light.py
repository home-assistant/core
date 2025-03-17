"""Platform for light integration."""

from __future__ import annotations

import logging
from typing import Any

from zcc import ControlPoint
from zcc.device import ControlPointDevice

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant

# Import the device class from the component that you want to support
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ZimiConfigEntry
from .entity import ZimiEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ZimiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zimi Light platform."""

    api = config_entry.runtime_data

    lights: list[ZimiLight | ZimiDimmer] = [
        ZimiLight(device, api)
        for device in filter(lambda light: light.type != "dimmer", api.lights)
    ]

    lights.extend(
        [
            ZimiDimmer(device, api)
            for device in filter(lambda light: light.type == "dimmer", api.lights)
        ]
    )

    async_add_entities(lights)


class ZimiLight(ZimiEntity, LightEntity):
    """Representation of a Zimi Light."""

    def __init__(self, device: ControlPointDevice, api: ControlPoint) -> None:
        """Initialize a ZimiLight."""

        super().__init__(device, api)

        self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {ColorMode.ONOFF}

        _LOGGER.debug(
            "Initialising ZimiLight %s in %s", self._device.name, self._device.room
        )

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._device.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on (with optional brightness)."""

        _LOGGER.debug(
            "Sending turn_on() for %s in %s", self._device.name, self._device.room
        )

        await self._device.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""

        _LOGGER.debug(
            "Sending turn_off() for %s in %s", self._device.name, self._device.room
        )

        await self._device.turn_off()


class ZimiDimmer(ZimiLight):
    """Zimi Light supporting dimming."""

    def __init__(self, device: ControlPointDevice, api: ControlPoint) -> None:
        """Initialize a ZimiDimmer."""
        super().__init__(device, api)
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        if self._device.type != "dimmer":
            raise ValueError("ZimiDimmer needs a dimmable light")

        _LOGGER.debug(
            "Initialising ZimiDimmer %s in %s", self._device.name, self._device.room
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on (with optional brightness)."""

        _LOGGER.debug(
            "Sending turn_on(brightness=%d) for %s in %s",
            kwargs.get(ATTR_BRIGHTNESS, 255) * 100 / 255,
            self._device.name,
            self._device.room,
        )

        await self._device.set_brightness(kwargs.get(ATTR_BRIGHTNESS, 255) * 100 / 255)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        return self._device.brightness * 255 / 100
