"""Platform for light integration."""

from __future__ import annotations

import logging
from typing import Any

from zcc import ControlPoint
from zcc.device import ControlPointDevice

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

# Import the device class from the component that you want to support
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zimi Light platform."""

    api: ControlPoint = config_entry.runtime_data

    entities = [ZimiLight(device, api) for device in api.lights]

    async_add_entities(entities)


class ZimiLight(LightEntity):
    """Representation of a Zimi Light."""

    def __init__(self, light: ControlPointDevice, api: ControlPoint) -> None:
        """Initialize an ZimiLight."""

        self._attr_unique_id = light.identifier
        self._attr_name = light.name.strip()
        self._attr_should_poll = False
        self._light = light
        self._light.subscribe(self)
        if self._light.type == "dimmer":
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, light.identifier)},
            name=self._attr_name,
            suggested_area=self._light.room,
            via_device=(DOMAIN, api.mac),
        )
        self.update()
        _LOGGER.debug("Initialising %s in %s", self.name, self._light.room)

    @property
    def available(self) -> bool:
        """Return True if Home Assistant is able to read the state and control the underlying device."""
        return self._light.is_connected

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""

        if self._light.type == "dimmer":
            return self._light.brightness * 255 / 100

        return None

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._light.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on (with optional brightness)."""

        _LOGGER.debug(
            "Sending turn_on(brightness=%d) for %s",
            kwargs.get(ATTR_BRIGHTNESS, 255) * 100 / 255,
            self.name,
        )

        if self._light.type == "dimmer":
            await self._light.set_brightness(
                kwargs.get(ATTR_BRIGHTNESS, 255) * 100 / 255
            )
        else:
            await self._light.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""

        _LOGGER.debug("Sending turn_off() for %s", self.name)

        await self._light.turn_off()

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup ZimiLight with removal of notification prior to removal."""
        await super().async_will_remove_from_hass()
        self._light.unsubscribe(self)

    def notify(self, _observable):
        """Receive notification from light device that state has changed."""

        _LOGGER.debug("Received notification() for %s", self.name)
        self._attr_name = self._light.name.strip()
        self.schedule_update_ha_state(force_refresh=True)

    def update(self) -> None:
        """Fetch new state data for this light."""
