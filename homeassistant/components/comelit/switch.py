"""Support for switches."""
from __future__ import annotations

from typing import Any

from aiocomelit import ComelitSerialBridgeObject
from aiocomelit.const import IRRIGATION, OTHER, STATE_OFF, STATE_ON

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
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
    """Set up Comelit switches."""

    coordinator: ComelitSerialBridge = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[ComelitSwitchEntity] = []
    entities.extend(
        ComelitSwitchEntity(coordinator, device, config_entry.entry_id)
        for device in coordinator.data[IRRIGATION].values()
    )
    entities.extend(
        ComelitSwitchEntity(coordinator, device, config_entry.entry_id)
        for device in coordinator.data[OTHER].values()
    )
    async_add_entities(entities)


class ComelitSwitchEntity(CoordinatorEntity[ComelitSerialBridge], SwitchEntity):
    """Switch device."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: ComelitSerialBridge,
        device: ComelitSerialBridgeObject,
        config_entry_entry_id: str,
    ) -> None:
        """Init switch entity."""
        self._api = coordinator.api
        self._device = device
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-{device.type}-{device.index}"
        self._attr_device_info = coordinator.platform_device_info(device, device.type)
        if device.type == OTHER:
            self._attr_device_class = SwitchDeviceClass.OUTLET

    async def _switch_set_state(self, state: int) -> None:
        """Set desired switch state."""
        await self.coordinator.api.set_device_status(
            self._device.type, self._device.index, state
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._switch_set_state(STATE_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._switch_set_state(STATE_OFF)

    @property
    def is_on(self) -> bool:
        """Return True if switch is on."""
        return (
            self.coordinator.data[self._device.type][self._device.index].status
            == STATE_ON
        )
