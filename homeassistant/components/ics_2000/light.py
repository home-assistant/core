"""Platform for ICS-2000 integration."""

from __future__ import annotations

import logging
from typing import Any

from ics_2000.entities import dim_device

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HubConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup the lights."""
    async_add_entities(
        [
            DimmableLight(entity, entry.runtime_data.local_address)
            for entity in entry.runtime_data.devices
            if type(entity) is dim_device.DimDevice
        ]
    )


class DimmableLight(LightEntity):
    """Representation of an dimmable light."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, light: dim_device.DimDevice, local_address: str | None) -> None:
        """Initialize an dimmable light."""
        self._light = light
        self._name = str(light.name)
        self._state = False  # self._light.get_on_status()
        self._brightness = 255  # self._light.get_dim_level()
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._local_address = local_address

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._light.device_data.id)},
            name=self.name,
            model=self._light.device_config.model_name,
            model_id=str(self._light.device_data.device),
            sw_version=str(
                self._light.device_data.data.get("module", {}).get("version", "")
            ),
        )

    @property
    def icon(self) -> str | None:
        """Icon of the entity."""
        return "mdi:lightbulb"

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def color_mode(self) -> ColorMode:
        """Set color mode for this entity."""
        return ColorMode.BRIGHTNESS

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color_modes (in an array format)."""
        return {ColorMode.BRIGHTNESS}

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        return self._brightness

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        await self.hass.async_add_executor_job(
            self._light.dim, kwargs.get(ATTR_BRIGHTNESS, 255), False
        )
        await self.hass.async_add_executor_job(
            self._light.turn_on, self._local_address is not None
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self.hass.async_add_executor_job(
            self._light.turn_off, self._local_address is not None
        )

    async def async_update(self) -> None:
        """Fetch new state data for this light."""
        self._state = await self.hass.async_add_executor_job(self._light.get_on_status)
        self._brightness = await self.hass.async_add_executor_job(
            self._light.get_dim_level
        )
