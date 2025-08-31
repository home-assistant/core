"""The Brother component."""

from __future__ import annotations

from brother import Brother, SnmpError

from homeassistant.components.snmp import async_get_snmp_engine
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_COMMUNITY, DEFAULT_COMMUNITY, DEFAULT_PORT, DOMAIN
from .coordinator import BrotherConfigEntry, BrotherDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: BrotherConfigEntry) -> bool:
    """Set up Brother from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    community = entry.data.get(CONF_COMMUNITY, DEFAULT_COMMUNITY)
    printer_type = entry.data[CONF_TYPE]

    snmp_engine = await async_get_snmp_engine(hass)
    try:
        brother = await Brother.create(
            host, port, community, printer_type=printer_type, snmp_engine=snmp_engine
        )
    except (ConnectionError, SnmpError, TimeoutError) as error:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={
                "device": entry.title,
                "error": repr(error),
            },
        ) from error

    coordinator = BrotherDataUpdateCoordinator(hass, entry, brother)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BrotherConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
