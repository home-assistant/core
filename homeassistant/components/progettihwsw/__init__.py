"""Automation manager for boards manufactured by ProgettiHWSW Italy."""

from ProgettiHWSW.input import Input
from ProgettiHWSW.ProgettiHWSWAPI import ProgettiHWSWAPI
from ProgettiHWSW.relay import Relay

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SWITCH]

type ProgettiHWSWConfigEntry = ConfigEntry[ProgettiHWSWAPI]


async def async_setup_entry(
    hass: HomeAssistant, entry: ProgettiHWSWConfigEntry
) -> bool:
    """Set up ProgettiHWSW Automation from a config entry."""
    api = ProgettiHWSWAPI(f"{entry.data['host']}:{entry.data['port']}")

    # Check board validation again to load new values to API.
    await api.check_board()

    entry.runtime_data = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ProgettiHWSWConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def setup_input(api: ProgettiHWSWAPI, input_number: int) -> Input:
    """Initialize the input pin."""
    return api.get_input(input_number)


def setup_switch(api: ProgettiHWSWAPI, switch_number: int, mode: str) -> Relay:
    """Initialize the output pin."""
    return api.get_relay(switch_number, mode)
