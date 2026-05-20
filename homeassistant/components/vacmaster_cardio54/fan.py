"""Fan platform for the Vacmaster Cardio54."""

import math
from typing import Any

from rf_protocols.commands.ev1527 import EV1527Command

from homeassistant.components.fan import ATTR_PERCENTAGE, FanEntity, FanEntityFeature
from homeassistant.components.radio_frequency import async_send_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import (
    CONF_DEVICE_ID,
    DATA_POWER,
    DATA_SPEEDS,
    FRAME_REPEATS,
    FREQUENCY,
    SPEED_COUNT,
    TIMEBASE_US,
)
from .entity import VacmasterCardio54Entity

PARALLEL_UPDATES = 1

_SPEED_RANGE = (1, SPEED_COUNT)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vacmaster Cardio54 fan platform."""
    async_add_entities([VacmasterCardio54Fan(config_entry)])


class VacmasterCardio54Fan(VacmasterCardio54Entity, FanEntity, RestoreEntity):
    """A Cardio54 fan controlled via one-way 433 MHz RF (assumed state)."""

    _attr_name = None
    _attr_speed_count = SPEED_COUNT
    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.SET_SPEED
    )

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the fan."""
        super().__init__(entry)
        self._device_id: int = entry.data[CONF_DEVICE_ID]
        self._level = 0
        self._attr_unique_id = entry.unique_id

    @property
    def is_on(self) -> bool:
        """Return whether the fan is currently on."""
        return self._level > 0

    @property
    def percentage(self) -> int:
        """Return the current speed as a percentage."""
        if self._level == 0:
            return 0
        return ranged_value_to_percentage(_SPEED_RANGE, self._level)

    async def async_added_to_hass(self) -> None:
        """Restore the last known speed level."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is None or last.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        last_pct = last.attributes.get(ATTR_PERCENTAGE)
        # ``bool`` subclasses ``int``, so guard against a stray boolean
        # attribute (e.g. ``True``) being treated as a percentage of 1.
        if (
            isinstance(last_pct, (int, float))
            and not isinstance(last_pct, bool)
            and last_pct > 0
        ):
            # Clamp the input to 0-100 % and the resulting level to
            # ``SPEED_COUNT`` so a corrupted / legacy attribute can't push
            # ``self._level`` past the last entry of ``DATA_SPEEDS`` on the
            # next ``turn_on`` (would IndexError).
            level = math.ceil(
                percentage_to_ranged_value(_SPEED_RANGE, min(last_pct, 100))
            )
            self._level = min(level, SPEED_COUNT)
        elif last.state == STATE_ON:
            # Older HA versions might restore an "on" state without the
            # percentage attribute; default to the lowest speed so the fan
            # comes back at a sensible level instead of "off".
            self._level = 1
        # The base ``async_added_to_hass`` writes the initial state with
        # ``_level == 0``; if restore set a non-zero level, the UI would
        # otherwise show ``off`` until the next command. Push the restored
        # state once.
        if self._level > 0:
            self.async_write_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on at the requested speed (default = speed 1)."""
        if percentage is None or percentage <= 0:
            level = 1
        else:
            level = math.ceil(percentage_to_ranged_value(_SPEED_RANGE, percentage))
        await self._async_set_level(level)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off.

        The Cardio54 power command is a toggle, so it is only sent when the
        fan is assumed to be running.
        """
        if self._level > 0:
            await self._async_send(DATA_POWER)
        self._level = 0
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed."""
        if percentage <= 0:
            await self.async_turn_off()
            return
        level = math.ceil(percentage_to_ranged_value(_SPEED_RANGE, percentage))
        await self._async_set_level(level)

    async def _async_set_level(self, level: int) -> None:
        """Send the direct speed command for ``level`` and update state."""
        await self._async_send(DATA_SPEEDS[level - 1])
        self._level = level
        self.async_write_ha_state()

    async def _async_send(self, data: int) -> None:
        """Encode and transmit a single EV1527 command via the transmitter."""
        command = EV1527Command(
            device_id=self._device_id,
            data=data,
            frequency=FREQUENCY,
            timebase_us=TIMEBASE_US,
            frame_repeats=FRAME_REPEATS,
        )
        await async_send_command(
            self.hass, self._transmitter, command, context=self._context
        )
