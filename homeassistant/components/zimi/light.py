"""Platform for light integration."""

from __future__ import annotations

import logging
from typing import Any

from zcc import ControlPoint
from zcc.device import ControlPointDevice

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

# Import the device class from the component that you want to support
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZimiConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ZimiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zimi Light platform."""

    api: ControlPoint = config_entry.runtime_data

    async_add_entities(
        ZimiLight(device, api)
        for device in filter(lambda light: light.type != "dimmer", api.lights)
    )
    async_add_entities(
        ZimiDimmer(device, api)
        for device in filter(lambda light: light.type == "dimmer", api.lights)
    )


class ZimiLight(LightEntity):
    """Representation of a Zimi Light."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, light: ControlPointDevice, api: ControlPoint) -> None:
        """Initialize a ZimiLight."""

        self._attr_unique_id = light.identifier
        self._light = light
        self._light.subscribe(self)
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, light.identifier)},
            name=self._light.name.strip(),
            manufacturer=api.brand,
            model=self._light.type,
            suggested_area=self._light.room,
            via_device=(DOMAIN, api.mac),
        )
        _LOGGER.debug("Initialising %s in %s", self._light.name, self._light.room)

    @property
    def available(self) -> bool:
        """Return True if Home Assistant is able to read the state and control the underlying device."""
        return self._light.is_connected

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._light.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on (with optional brightness)."""

        _LOGGER.debug(
            "Sending turn_on() for %s in %s", self._light.name, self._light.room
        )

        await self._light.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""

        _LOGGER.debug(
            "Sending turn_off() for %s in %s", self._light.name, self._light.room
        )

        await self._light.turn_off()

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup ZimiLight with removal of notification prior to removal."""
        await super().async_will_remove_from_hass()
        self._light.unsubscribe(self)

    def notify(self, _observable):
        """Receive notification from light device that state has changed."""

        _LOGGER.debug(
            "Received notification() for %s in %s", self._light.name, self._light.room
        )
        self.schedule_update_ha_state(force_refresh=True)

    def update(self) -> None:
        """Fetch new state data for this light."""


class ZimiDimmer(ZimiLight):
    """Zimi Light supporting dimming."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, light: ControlPointDevice, api: ControlPoint) -> None:
        """Initialize a ZimiDimmer."""
        super().__init__(light, api)
        if self._light.type != "dimmer":
            raise ValueError("ZimiDimmer needs a dimmable light")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on (with optional brightness)."""

        _LOGGER.debug(
            "Sending turn_on(brightness=%d) for %s in %s",
            kwargs.get(ATTR_BRIGHTNESS, 255) * 100 / 255,
            self._light.name,
            self._light.room,
        )

        await self._light.set_brightness(kwargs.get(ATTR_BRIGHTNESS, 255) * 100 / 255)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        return self._light.brightness * 255 / 100
