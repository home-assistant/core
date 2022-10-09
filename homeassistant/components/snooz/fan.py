"""Fan representation of a Snooz device."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pysnooz.api import UnknownSnoozState
from pysnooz.commands import (
    SnoozCommandData,
    SnoozCommandResultStatus,
    set_volume,
    turn_off,
    turn_on,
)

from homeassistant.components.fan import ATTR_PERCENTAGE, FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .models import SnoozConfigurationData


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Snooz device from a config entry."""

    data: SnoozConfigurationData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([SnoozFan(data)])


class SnoozFan(FanEntity, RestoreEntity):
    """Fan representation of a Snooz device."""

    def __init__(self, data: SnoozConfigurationData) -> None:
        """Initialize a Snooz fan entity."""
        self._device = data.device
        self._attr_name = data.title
        self._attr_unique_id = data.device.address
        self._attr_supported_features = FanEntityFeature.SET_SPEED
        self._attr_should_poll = False
        self._is_on: bool | None = None
        self._percentage: int | None = None

    @callback
    def _async_write_state_changed(self) -> None:
        # cache state for restore entity
        if not self.assumed_state:
            self._is_on = self._device.state.on
            self._percentage = self._device.state.volume

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to device events."""
        await super().async_added_to_hass()

        if last_state := await self.async_get_last_state():
            if last_state.state in (STATE_ON, STATE_OFF):
                self._is_on = last_state.state == STATE_ON
            else:
                self._is_on = None
            self._percentage = last_state.attributes.get(ATTR_PERCENTAGE)

        self.async_on_remove(self._async_subscribe_to_device_change())

    @callback
    def _async_subscribe_to_device_change(self) -> Callable[[], None]:
        return self._device.subscribe_to_state_change(self._async_write_state_changed)

    @property
    def percentage(self) -> int | None:
        """Volume level of the device."""
        return self._percentage if self.assumed_state else self._device.state.volume

    @property
    def is_on(self) -> bool | None:
        """Power state of the device."""
        return self._is_on if self.assumed_state else self._device.state.on

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return not self._device.is_connected or self._device.state is UnknownSnoozState

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the device."""
        await self._async_execute_command(turn_on(percentage))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        await self._async_execute_command(turn_off())

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the volume of the device. A value of 0 will turn off the device."""
        await self._async_execute_command(
            set_volume(percentage) if percentage > 0 else turn_off()
        )

    async def _async_execute_command(self, command: SnoozCommandData) -> None:
        result = await self._device.async_execute_command(command)

        if result.status == SnoozCommandResultStatus.SUCCESSFUL:
            self._async_write_state_changed()
        elif result.status != SnoozCommandResultStatus.CANCELLED:
            raise HomeAssistantError(
                f"Command {command} failed with status {result.status.name} after {result.duration}"
            )
