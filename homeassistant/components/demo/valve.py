"""Demo valve platform that implements valves."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.valve import ValveEntity, ValveEntityFeature, ValveState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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
    ) -> None:
        """Initialize the valve."""
        self._attr_name = name
        if moveable:
            self._attr_supported_features = (
                ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
            )
        self._state = state
        self._moveable = moveable

    @property
    def is_open(self) -> bool:
        """Return true if valve is open."""
        return self._state == ValveState.OPEN

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

    @property
    def reports_position(self) -> bool:
        """Return True if entity reports position, False otherwise."""
        return False

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
