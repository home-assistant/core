"""Control switches."""

from datetime import timedelta
import logging

from ProgettiHWSW.relay import Relay
import async_timeout

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import setup_switch
from .const import DEFAULT_POLLING_INTERVAL_SEC, DOMAIN

_LOGGER = logging.getLogger(DOMAIN)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set the switch platform up (legacy)."""
    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the switches from a config entry."""
    board_api = hass.data[DOMAIN][config_entry.entry_id]
    relay_count = config_entry.data["relay_count"]
    switches = []

    async def async_update_data():
        """Fetch data from API endpoint of board."""
        async with async_timeout.timeout(5):
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
                hass,
                coordinator,
                config_entry,
                f"Relay #{i}",
                setup_switch(board_api, i, config_entry.data[f"relay_{str(i)}"]),
            )
        )

    async_add_entities(switches)


class ProgettihwswSwitch(SwitchEntity):
    """Represent a switch entity."""

    def __init__(self, hass, coordinator, config_entry, name, switch: Relay):
        """Initialize the values."""
        self._switch = switch
        self._name = name
        self._coordinator = coordinator

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._switch.control(True)
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._switch.control(False)
        await self._coordinator.async_request_refresh()

    async def async_toggle(self, **kwargs):
        """Toggle the state of switch."""
        await self._switch.toggle()
        await self._coordinator.async_request_refresh()

    @property
    def name(self):
        """Return the switch name."""
        return self._name

    @property
    def is_on(self):
        """Get switch state."""
        return self._coordinator.data[self._switch.id]

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    async def async_update(self):
        """Update the state of switch."""
        await self._coordinator.async_request_refresh()
