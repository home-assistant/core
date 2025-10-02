"""Support for lights."""

from __future__ import annotations

from typing import Any, cast

from aiocomelit.const import LIGHT, STATE_OFF, STATE_ON

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ComelitConfigEntry, ComelitSerialBridge
from .entity import ComelitBridgeBaseEntity
from .utils import bridge_api_call

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ComelitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Comelit lights."""

    coordinator = cast(ComelitSerialBridge, config_entry.runtime_data)

    known_devices: set[int] = set()

    def _check_device() -> None:
        current_devices = set(coordinator.data[LIGHT])
        new_devices = current_devices - known_devices
        if new_devices:
            known_devices.update(new_devices)
            async_add_entities(
                ComelitLightEntity(coordinator, device, config_entry.entry_id)
                for device in coordinator.data[LIGHT].values()
                if device.index in new_devices
            )

    _check_device()
    config_entry.async_on_unload(coordinator.async_add_listener(_check_device))


class ComelitLightEntity(ComelitBridgeBaseEntity, LightEntity):
    """Light device."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.ONOFF}

    @bridge_api_call
    async def _light_set_state(self, state: int) -> None:
        """Set desired light state."""
        await self.coordinator.api.set_device_status(LIGHT, self._device.index, state)
        self.coordinator.data[LIGHT][self._device.index].status = state
        self.async_write_ha_state()

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
