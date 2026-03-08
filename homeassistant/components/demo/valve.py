"""Demo valve platform that implements valves."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from homeassistant.components.valve import ValveEntity, ValveEntityFeature, ValveState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_utc_time_change

OPEN_CLOSE_DELAY = 2  # Used to give a realistic open/close experience in frontend


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    async_add_entities(
        [
            DemoValve("Front Garden", ValveState.OPEN),
            DemoValve("Orchard", ValveState.CLOSED),
            DemoValve("Back Garden", ValveState.CLOSED, position=70),
            DemoValve("Trees", ValveState.CLOSED, position=30),
        ]
    )


class DemoValve(ValveEntity):
    """Representation of a Demo valve."""

    _attr_should_poll = False

    def __init__(
        self,
        name: str,
        state: str,
        moveable: bool = True,
        position: int | None = None,
    ) -> None:
        """Initialize the valve."""
        self._attr_name = name
        if moveable:
            self._attr_supported_features = (
                ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
            )
        self._state = state
        self._moveable = moveable
        self._attr_reports_position = False
        self._unsub_listener_valve: CALLBACK_TYPE | None = None
        self._set_position: int = 0
        self._position: int = 0
        if position is None:
            return

        self._position = self._set_position = position
        self._attr_reports_position = True
        self._attr_supported_features |= (
            ValveEntityFeature.SET_POSITION | ValveEntityFeature.STOP
        )

    @property
    def current_valve_position(self) -> int:
        """Return current position of valve."""
        return self._position

    @property
    def is_opening(self) -> bool:
        """Return true if valve is opening."""
        return self._state == ValveState.OPENING

    @property
    def is_closing(self) -> bool:
        """Return true if valve is closing."""
        return self._state == ValveState.CLOSING

    @property
    def is_closed(self) -> bool:
        """Return true if valve is closed."""
        return self._state == ValveState.CLOSED

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open the valve."""
        self._state = ValveState.OPENING
        self.async_write_ha_state()
        await asyncio.sleep(OPEN_CLOSE_DELAY)
        self._state = ValveState.OPEN
        self.async_write_ha_state()

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close the valve."""
        self._state = ValveState.CLOSING
        self.async_write_ha_state()
        await asyncio.sleep(OPEN_CLOSE_DELAY)
        self._state = ValveState.CLOSED
        self.async_write_ha_state()

    async def async_stop_valve(self) -> None:
        """Stop the valve."""
        self._state = ValveState.OPEN if self._position > 0 else ValveState.CLOSED
        if self._unsub_listener_valve is not None:
            self._unsub_listener_valve()
            self._unsub_listener_valve = None
        self.async_write_ha_state()

    async def async_set_valve_position(self, position: int) -> None:
        """Move the valve to a specific position."""
        if position == self._position:
            return
        if position > self._position:
            self._state = ValveState.OPENING
        else:
            self._state = ValveState.CLOSING

        self._set_position = round(position, -1)
        self._listen_valve()
        self.async_write_ha_state()

    @callback
    def _listen_valve(self) -> None:
        """Listen for changes in valve."""
        if self._unsub_listener_valve is None:
            self._unsub_listener_valve = async_track_utc_time_change(
                self.hass, self._time_changed_valve
            )

    async def _time_changed_valve(self, now: datetime) -> None:
        """Track time changes."""
        if self._state == ValveState.OPENING:
            self._position += 10
        elif self._state == ValveState.CLOSING:
            self._position -= 10

        if self._position in (100, 0, self._set_position):
            await self.async_stop_valve()
            return

        self.async_write_ha_state()
