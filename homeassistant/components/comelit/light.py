"""Support for lights."""

from __future__ import annotations

from typing import Any

from aiocomelit import ComelitSerialBridgeObject
from aiocomelit.const import LIGHT, STATE_OFF, STATE_ON

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ComelitSerialBridge


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comelit lights."""

    coordinator: ComelitSerialBridge = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        ComelitLightEntity(coordinator, device, config_entry.entry_id)
        for device in coordinator.data[LIGHT].values()
    )


class ComelitLightEntity(CoordinatorEntity[ComelitSerialBridge], LightEntity):
    """Light device."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(
        self,
        coordinator: ComelitSerialBridge,
        device: ComelitSerialBridgeObject,
        config_entry_entry_id: str,
    ) -> None:
        """Init light entity."""
        self._api = coordinator.api
        self._device = device
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-{device.index}"
        self._attr_device_info = coordinator.platform_device_info(device, device.type)

    async def _light_set_state(self, state: int) -> None:
        """Set desired light state."""
        await self.coordinator.api.set_device_status(LIGHT, self._device.index, state)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self._light_set_state(STATE_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._light_set_state(STATE_OFF)

    @property
    def is_on(self) -> bool:
        """Return True if light is on."""
        return self.coordinator.data[LIGHT][self._device.index].status == STATE_ON
