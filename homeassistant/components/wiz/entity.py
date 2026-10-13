"""WiZ integration entities."""

from abc import abstractmethod
from typing import Any, override

from pywizlight import PilotParser, wizlight
from pywizlight.bulblibrary import BulbType

from homeassistant.const import ATTR_HW_VERSION, ATTR_MODEL
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity, ToggleEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import WizCoordinator, WizData


def get_wiz_state(device: wizlight, index: int = 0) -> PilotParser | None:
    """Return the current state for a WiZ device head."""
    state = device.state
    if state is None or len(state) <= index:
        return None
    return state[index]


class WizEntity(CoordinatorEntity[WizCoordinator], Entity):
    """Representation of WiZ entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        wiz_data: WizData,
        name: str,
        state_index: int = 0,
        target_device: int | None = None,
    ) -> None:
        """Initialize a WiZ entity."""
        super().__init__(wiz_data.coordinator)
        self._device = wiz_data.bulb
        self._state_index = state_index
        self._target_device = target_device
        bulb_type: BulbType = self._device.bulbtype
        self._attr_unique_id = (
            self._device.mac
            if state_index == 0
            else f"{self._device.mac}_{state_index}"
        )
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._device.mac)},
            name=name,
            manufacturer="WiZ",
            sw_version=bulb_type.fw_version,
        )
        if bulb_type.name is None:
            return
        hw_data = bulb_type.name.split("_")
        board = hw_data.pop(0)
        model = hw_data.pop(0)
        hw_version = f"{board} {hw_data[0]}" if hw_data else board
        self._attr_device_info[ATTR_HW_VERSION] = hw_version
        self._attr_device_info[ATTR_MODEL] = model

    @property
    def _state(self) -> PilotParser | None:
        """Return the current state for this entity."""
        return get_wiz_state(self._device, self._state_index)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    @abstractmethod
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""


class WizToggleEntity(WizEntity, ToggleEntity):
    """Representation of WiZ toggle entity."""

    @callback
    @override
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_is_on = self._state.get_state() if self._state else None

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the device to turn off."""
        if self._target_device is not None:
            await self._device.turn_off(device=self._target_device)
        else:
            await self._device.turn_off()
        await self.coordinator.async_request_refresh()
