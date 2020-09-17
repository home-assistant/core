"""Automation manager for boards manufactured by ProgettiHWSW Italy."""
import asyncio

from ProgettiHWSW.ProgettiHWSWAPI import ProgettiHWSWAPI
from ProgettiHWSW.input import Input
from ProgettiHWSW.relay import Relay

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = ["switch", "binary_sensor"]


async def async_setup(hass, config):
    """Set up the ProgettiHWSW Automation component."""
    hass.data[DOMAIN] = {}

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up ProgettiHWSW Automation from a config entry."""

    hass.data[DOMAIN][entry.entry_id] = ProgettiHWSWAPI(
        f'{entry.data["host"]}:{entry.data["port"]}'
    )

    # Check board validation again to load new values to API.
    await hass.data[DOMAIN][entry.entry_id].check_board()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def setup_input(api: ProgettiHWSWAPI, input_number: int) -> Input:
    """Initialize the input pin."""
    return api.get_input(input_number)


def setup_switch(api: ProgettiHWSWAPI, switch_number: int, mode: str) -> Relay:
    """Initialize the output pin."""
    return api.get_relay(switch_number, mode)
