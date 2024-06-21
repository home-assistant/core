"""The Brother component."""

from __future__ import annotations

from brother import Brother, SnmpError

from homeassistant.components.snmp import async_get_snmp_engine
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import BrotherDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]

type BrotherConfigEntry = ConfigEntry[BrotherDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BrotherConfigEntry) -> bool:
    """Set up Brother from a config entry."""
    host = entry.data[CONF_HOST]
    printer_type = entry.data[CONF_TYPE]

    snmp_engine = await async_get_snmp_engine(hass)
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
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
