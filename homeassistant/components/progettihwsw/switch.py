"""Control switches."""
import asyncio
from datetime import timedelta
import logging
from typing import Any

from ProgettiHWSW.relay import Relay

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import setup_switch
from .const import DEFAULT_POLLING_INTERVAL_SEC, DOMAIN

_LOGGER = logging.getLogger(DOMAIN)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switches from a config entry."""
    board_api = hass.data[DOMAIN][config_entry.entry_id]
    relay_count = config_entry.data["relay_count"]
    switches = []

    async def async_update_data():
        """Fetch data from API endpoint of board."""
        async with asyncio.timeout(5):
            return await board_api.get_switches()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="switch",
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_POLLING_INTERVAL_SEC),
    )
    await coordinator.async_refresh()

    for i in range(1, int(relay_count) + 1):
        switches.append(
            ProgettihwswSwitch(
                coordinator,
                f"Relay #{i}",
                setup_switch(board_api, i, config_entry.data[f"relay_{str(i)}"]),
            )
        )

    async_add_entities(switches)


class ProgettihwswSwitch(CoordinatorEntity, SwitchEntity):
    """Represent a switch entity."""

    def __init__(self, coordinator, name, switch: Relay) -> None:
        """Initialize the values."""
        super().__init__(coordinator)
        self._switch = switch
        self._attr_name = name

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._switch.control(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._switch.control(False)
        await self.coordinator.async_request_refresh()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the state of switch."""
        await self._switch.toggle()
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self):
        """Get switch state."""
        return self.coordinator.data[self._switch.id]
