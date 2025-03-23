"""Support for fans through the SmartThings cloud API."""

from __future__ import annotations

import math
from typing import Any

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity

SPEED_RANGE = (1, 3)  # off is not included


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add fans for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsFan(entry_data.client, device)
        for device in entry_data.devices.values()
        if Capability.SWITCH in device.status[MAIN]
        and any(
            capability in device.status[MAIN]
            for capability in (
                Capability.FAN_SPEED,
                Capability.AIR_CONDITIONER_FAN_MODE,
            )
        )
        and Capability.THERMOSTAT_COOLING_SETPOINT not in device.status[MAIN]
    )


class SmartThingsFan(SmartThingsEntity, FanEntity):
    """Define a SmartThings Fan."""

    _attr_name = None
    _attr_speed_count = int_states_in_range(SPEED_RANGE)

    def __init__(self, client: SmartThings, device: FullDevice) -> None:
        """Init the class."""
        super().__init__(
            client,
            device,
            {
                Capability.SWITCH,
                Capability.FAN_SPEED,
                Capability.AIR_CONDITIONER_FAN_MODE,
            },
        )
        self._attr_supported_features = self._determine_features()

    def _determine_features(self):
        flags = FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON

        if self.supports_capability(Capability.FAN_SPEED):
            flags |= FanEntityFeature.SET_SPEED
        if self.supports_capability(Capability.AIR_CONDITIONER_FAN_MODE):
            flags |= FanEntityFeature.PRESET_MODE

        return flags

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.execute_device_command(Capability.SWITCH, Command.OFF)
        else:
            value = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
            await self.execute_device_command(
                Capability.FAN_SPEED,
                Command.SET_FAN_SPEED,
                argument=value,
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset_mode of the fan."""
        await self.execute_device_command(
            Capability.AIR_CONDITIONER_FAN_MODE,
            Command.SET_FAN_MODE,
            argument=preset_mode,
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if (
            FanEntityFeature.SET_SPEED in self._attr_supported_features
            and percentage is not None
        ):
            await self.async_set_percentage(percentage)
        else:
            await self.execute_device_command(Capability.SWITCH, Command.ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.execute_device_command(Capability.SWITCH, Command.OFF)

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return self.get_attribute_value(Capability.SWITCH, Attribute.SWITCH) == "on"

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        return ranged_value_to_percentage(
            SPEED_RANGE,
            self.get_attribute_value(Capability.FAN_SPEED, Attribute.FAN_SPEED),
        )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., auto, smart, interval, favorite.

        Requires FanEntityFeature.PRESET_MODE.
        """
        if not self.supports_capability(Capability.AIR_CONDITIONER_FAN_MODE):
            return None
        return self.get_attribute_value(
            Capability.AIR_CONDITIONER_FAN_MODE, Attribute.FAN_MODE
        )

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires FanEntityFeature.PRESET_MODE.
        """
        if not self.supports_capability(Capability.AIR_CONDITIONER_FAN_MODE):
            return None
        return self.get_attribute_value(
            Capability.AIR_CONDITIONER_FAN_MODE, Attribute.SUPPORTED_AC_FAN_MODES
        )
