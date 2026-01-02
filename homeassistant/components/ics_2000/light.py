"""Platform for ICS-2000 integration."""

from __future__ import annotations

import logging
from typing import Any

from ics_2000.entities import dim_device

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HubConfigEntry
from .const import DOMAIN
from .coordinator import ICS200Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup the lights."""
    async_add_entities(
        [
            DimmableLight(
                entry.runtime_data, entity, entry.runtime_data.hub.local_address
            )
            for entity in entry.runtime_data.hub.devices
            if type(entity) is dim_device.DimDevice
        ]
    )


class DimmableLight(CoordinatorEntity[ICS200Coordinator], LightEntity):
    """Representation of an dimmable light."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: ICS200Coordinator,
        light: dim_device.DimDevice,
        local_address: str | None,
    ) -> None:
        """Initialize an dimmable light."""
        super().__init__(coordinator, context=str(light.entity_id))
        self._light = light
        self._state = False
        self._brightness = None
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._local_address = local_address
        self._attr_unique_id = str(light.entity_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, light.device_data.id)},
            name=str(light.name),
            model=light.device_config.model_name,
            model_id=str(light.device_data.device),
            sw_version=str(light.device_data.data.get("module", {}).get("version", "")),
        )

    @property
    def icon(self) -> str | None:
        """Icon of the entity."""
        return "mdi:lightbulb"

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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        status = self.coordinator.hub.device_statuses.get(self._light.entity_id, [])
        if self._light.device_config.on_off_function is not None:
            self._state = status[self._light.device_config.on_off_function] == 1
        if self._light.device_config.dim_function is not None:
            self._brightness = status[self._light.device_config.dim_function]
        self.async_write_ha_state()
