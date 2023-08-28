"""Support for ISY fans."""
from __future__ import annotations

import math
from typing import Any

from pyisy.constants import ISY_VALUE_UNKNOWN, PROTO_INSTEON

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import _LOGGER, DOMAIN
from .entity import ISYNodeEntity, ISYProgramEntity
from .models import IsyData

SPEED_RANGE = (1, 255)  # off is not included


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ISY fan platform."""
    isy_data: IsyData = hass.data[DOMAIN][entry.entry_id]
    devices: dict[str, DeviceInfo] = isy_data.devices
    entities: list[ISYFanEntity | ISYFanProgramEntity] = []

    for node in isy_data.nodes[Platform.FAN]:
        entities.append(ISYFanEntity(node, devices.get(node.primary_node)))

    for name, status, actions in isy_data.programs[Platform.FAN]:
        entities.append(ISYFanProgramEntity(name, status, actions))

    async_add_entities(entities)


class ISYFanEntity(ISYNodeEntity, FanEntity):
    """Representation of an ISY fan device."""

    _attr_supported_features = FanEntityFeature.SET_SPEED

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return ranged_value_to_percentage(SPEED_RANGE, self._node.status)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        if self._node.protocol == PROTO_INSTEON:
            return 3
        return int_states_in_range(SPEED_RANGE)

    @property
    def is_on(self) -> bool | None:
        """Get if the fan is on."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return bool(self._node.status != 0)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set node to speed percentage for the ISY fan device."""
        if percentage == 0:
            await self._node.turn_off()
            return

        isy_speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))

        await self._node.turn_on(val=isy_speed)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Send the turn on command to the ISY fan device."""
        await self.async_set_percentage(percentage or 67)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the turn off command to the ISY fan device."""
        await self._node.turn_off()


class ISYFanProgramEntity(ISYProgramEntity, FanEntity):
    """Representation of an ISY fan program."""

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return ranged_value_to_percentage(SPEED_RANGE, self._node.status)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    @property
    def is_on(self) -> bool:
        """Get if the fan is on."""
        return bool(self._node.status != 0)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the turn on command to ISY fan program."""
        if not await self._actions.run_then():
            _LOGGER.error("Unable to turn off the fan")

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Send the turn off command to ISY fan program."""
        if not await self._actions.run_else():
            _LOGGER.error("Unable to turn on the fan")
