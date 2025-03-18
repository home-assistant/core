"""The TISControl integration."""

from __future__ import annotations

import logging

from attr import dataclass
from TISControlProtocol.api import TISApi
from TISControlProtocol.Protocols.udp.ProtocolHandler import TISProtocolHandler

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DEVICES_DICT, DOMAIN

PLATFORMS: list[Platform] = [Platform.SWITCH]
type TISConfigEntry = ConfigEntry[TISData]
protocol_handler = TISProtocolHandler()


@dataclass
class TISData:
    """TISControl data stored in the ConfigEntry."""

    api: TISApi


async def async_setup_entry(hass: HomeAssistant, entry: TISConfigEntry) -> bool:
    """Set up TISControl from a config entry."""
    tis_api = TISApi(
        port=int(entry.data["port"]),
        hass=hass,
        domain=DOMAIN,
        devices_dict=DEVICES_DICT,
    )
    entry.runtime_data = TISData(api=tis_api)

    try:
        await tis_api.connect()
    except ConnectionError as e:
        raise ConfigEntryNotReady from e
    # add the tis api to the hass data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TISConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return unload_ok

    return False
