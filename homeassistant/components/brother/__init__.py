"""The Brother component."""

from __future__ import annotations

from brother import Brother, SnmpError
from pysnmp.hlapi.asyncio.cmdgen import lcd

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, SNMP_ENGINE
from .coordinator import BrotherDataUpdateCoordinator
from .utils import get_snmp_engine

PLATFORMS = [Platform.SENSOR]

type BrotherConfigEntry = ConfigEntry[BrotherDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BrotherConfigEntry) -> bool:
    """Set up Brother from a config entry."""
    host = entry.data[CONF_HOST]
    printer_type = entry.data[CONF_TYPE]

    snmp_engine = get_snmp_engine(hass)
    try:
        brother = await Brother.create(
            host, printer_type=printer_type, snmp_engine=snmp_engine
        )
    except (ConnectionError, SnmpError, TimeoutError) as error:
        raise ConfigEntryNotReady from error

    coordinator = BrotherDataUpdateCoordinator(hass, brother)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BrotherConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    # We only want to remove the SNMP engine when unloading the last config entry
    if unload_ok and len(loaded_entries) == 1:
        lcd.unconfigure(hass.data[SNMP_ENGINE], None)
        hass.data.pop(SNMP_ENGINE)

    return unload_ok
