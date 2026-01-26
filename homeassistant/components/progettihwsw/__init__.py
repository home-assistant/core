"""Automation manager for boards manufactured by ProgettiHWSW Italy."""

import types

from lxml import etree
from ProgettiHWSW.input import Input
from ProgettiHWSW.ProgettiHWSWAPI import ProgettiHWSWAPI
from ProgettiHWSW.relay import Relay

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ProgettiHWSW Automation from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = ProgettiHWSWAPI(
        f"{entry.data['host']}:{entry.data['port']}"
    )

    # Monkey patch for get_states_by_tag_prefix bug
    async def get_states_by_tag_prefix_fixed(self, tag: str, is_analog: bool = False):
        request = await self.api.request("status.xml")
        if request is False:
            return False

        root = etree.XML(bytes(request, encoding="utf-8"))  # pylint: disable=c-extension-no-member
        tags = root.xpath(f"//*[starts-with(local-name(), '{tag}')]")

        if len(tags) <= 0:
            return False

        states = {}
        for i in tags:
            # FIX: use int() instead of str() for base 16 conversion
            number = int(i.tag[len(tag) :], 16)
            if is_analog:
                states[number] = i.text
            else:
                # states[number] = True if i.text in ("up", "1", "on") else False
                states[number] = i.text in ("up", "1", "on")
        return states

    # Apply patch
    hass.data[DOMAIN][entry.entry_id].get_states_by_tag_prefix = types.MethodType(
        get_states_by_tag_prefix_fixed, hass.data[DOMAIN][entry.entry_id]
    )

    # Check board validation again to load new values to API.
    await hass.data[DOMAIN][entry.entry_id].check_board()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def setup_input(api: ProgettiHWSWAPI, input_number: int) -> Input:
    """Initialize the input pin."""
    return api.get_input(input_number)


def setup_switch(api: ProgettiHWSWAPI, switch_number: int, mode: str) -> Relay:
    """Initialize the output pin."""
    return api.get_relay(switch_number, mode)
