"""Support for ISY994 fans."""
from __future__ import annotations

import math
from typing import Any
from collections import OrderedDict

from pyisy.constants import ISY_VALUE_UNKNOWN, PROTO_INSTEON

from homeassistant.components.fan import (
    DOMAIN as FAN,
    SUPPORT_SET_SPEED,
    SUPPORT_PRESET_MODE,
    SPEED_OFF,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_HIGH,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import _LOGGER, DOMAIN as ISY994_DOMAIN, ISY994_NODES, ISY994_PROGRAMS
from .entity import ISYNodeEntity, ISYProgramEntity
from .helpers import migrate_old_unique_ids

SPEED_RANGE = (1, 255)  # off is not included

FANLINC_FAN_MODES = OrderedDict(
    [(0, SPEED_OFF), (64, SPEED_LOW), (191, SPEED_MEDIUM), (255, SPEED_HIGH)]
)

FANLINC_FAN_MODES_REV = OrderedDict([(v, k) for k, v in FANLINC_FAN_MODES.items()])


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ISY994 fan platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    entities: list[ISYFanEntity | ISYFanProgramEntity] = []

    for node in hass_isy_data[ISY994_NODES][FAN]:
        if hasattr(node, "node_def_id") and node.node_def_id == "FanLincMotor":
            entities.append(ISYFanLincEntity(node))
        else:
            entities.append(ISYFanEntity(node))

    for name, status, actions in hass_isy_data[ISY994_PROGRAMS][FAN]:
        entities.append(ISYFanProgramEntity(name, status, actions))

    await migrate_old_unique_ids(hass, FAN, entities)
    async_add_entities(entities)


class ISYFanLincEntity(ISYNodeEntity, FanEntity):
    """Representation of an ISY994 fan device."""

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        mode = next(
            (v for k, v in FANLINC_FAN_MODES.items() if self._node.status <= k),
            SPEED_OFF,
        )
        return mode

    @property
    def preset_modes(self) -> list[str]:
        """Return a list of available preset modes."""
        return list(FANLINC_FAN_MODES.values())

    @property
    def is_on(self) -> bool | None:
        """Get if the fan is on."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return bool(self._node.status != 0)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target fan mode."""
        isy_speed = FANLINC_FAN_MODES_REV.get(preset_mode, ISY_VALUE_UNKNOWN)
        if isy_speed != ISY_VALUE_UNKNOWN:
            if isy_speed == 0:
                await self._node.turn_off()
                return
            await self._node.turn_on(val=isy_speed)

    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Send the turn on command to the ISY994 fan device."""
        await self.async_set_preset_mode(preset_mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the turn off command to the ISY994 fan device."""
        await self._node.turn_off()

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_PRESET_MODE


class ISYFanEntity(ISYNodeEntity, FanEntity):
    """Representation of an ISY994 fan device."""

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
        """Set node to speed percentage for the ISY994 fan device."""
        if percentage == 0:
            await self._node.turn_off()
            return

        isy_speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))

        await self._node.turn_on(val=isy_speed)

    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Send the turn on command to the ISY994 fan device."""
        await self.async_set_percentage(percentage or 67)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the turn off command to the ISY994 fan device."""
        await self._node.turn_off()

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED


class ISYFanProgramEntity(ISYProgramEntity, FanEntity):
    """Representation of an ISY994 fan program."""

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
        """Send the turn on command to ISY994 fan program."""
        if not await self._actions.run_then():
            _LOGGER.error("Unable to turn off the fan")

    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Send the turn off command to ISY994 fan program."""
        if not await self._actions.run_else():
            _LOGGER.error("Unable to turn on the fan")
