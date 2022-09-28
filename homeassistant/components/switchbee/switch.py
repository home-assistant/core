"""Support for SwitchBee switch."""

from __future__ import annotations

from typing import Any, TypeVar, Union, cast

from switchbee.api import SwitchBeeDeviceOfflineError, SwitchBeeError
from switchbee.device import (
    ApiStateCommand,
    SwitchBeeGroupSwitch,
    SwitchBeeSwitch,
    SwitchBeeTimedSwitch,
    SwitchBeeTimerSwitch,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SwitchBeeCoordinator
from .entity import SwitchBeeDeviceEntity

_DeviceTypeT = TypeVar(
    "_DeviceTypeT",
    bound=Union[
        SwitchBeeTimedSwitch,
        SwitchBeeGroupSwitch,
        SwitchBeeSwitch,
        SwitchBeeTimerSwitch,
    ],
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Switchbee switch."""
    coordinator: SwitchBeeCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SwitchBeeSwitchEntity(device, coordinator)
        for device in coordinator.data.values()
        if isinstance(
            device,
            (
                SwitchBeeTimedSwitch,
                SwitchBeeGroupSwitch,
                SwitchBeeSwitch,
                SwitchBeeTimerSwitch,
            ),
        )
    )


class SwitchBeeSwitchEntity(SwitchBeeDeviceEntity[_DeviceTypeT], SwitchEntity):
    """Representation of a Switchbee switch."""

    def __init__(
        self,
        device: _DeviceTypeT,
        coordinator: SwitchBeeCoordinator,
    ) -> None:
        """Initialize the Switchbee switch."""
        super().__init__(device, coordinator)
        self._attr_is_on = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_coordinator()
        super()._handle_coordinator_update()

    def _update_from_coordinator(self) -> None:
        """Update the entity attributes from the coordinator data."""

        coordinator_device = cast(_DeviceTypeT, self.coordinator.data[self._device.id])

        if coordinator_device.state == -1:

            self._check_if_became_offline()
            return

        self._check_if_became_online()

        # timed power switch state is an integer representing the number of minutes left until it goes off
        # regulare switches state is ON/OFF (1/0 respectively)
        self._attr_is_on = coordinator_device.state != ApiStateCommand.OFF

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Async function to set on to switch."""
        return await self._async_set_state(ApiStateCommand.ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Async function to set off to switch."""
        return await self._async_set_state(ApiStateCommand.OFF)

    async def _async_set_state(self, state: str) -> None:
        try:
            await self.coordinator.api.set_state(self._device.id, state)
        except (SwitchBeeError, SwitchBeeDeviceOfflineError) as exp:
            await self.coordinator.async_refresh()
            raise HomeAssistantError(
                f"Failed to set {self._attr_name} state {state}, {str(exp)}"
            ) from exp

        await self.coordinator.async_refresh()
