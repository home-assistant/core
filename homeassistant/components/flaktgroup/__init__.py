"""Support for Fläktgroup devices."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    CONF_DEVICE_INFO,
    CONF_MODBUS_COORDINATOR,
    CONF_UPDATE_INTERVAL,
    DOMAIN as AGENT_DOMAIN,
)
from .modbus_coordinator import FlaktgroupModbusDataUpdateCoordinator

PLATFORMS = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Fläktgroup component."""
    hass.data.setdefault(AGENT_DOMAIN, {})

    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    name = config_entry.data[CONF_NAME]
    update_interval = config_entry.data[CONF_UPDATE_INTERVAL]

    modbus_coordinator = FlaktgroupModbusDataUpdateCoordinator(
        hass, name, host, port, update_interval
    )
    modbus_connected = await modbus_coordinator.async_connect()
    if not modbus_connected:
        raise ConfigEntryNotReady

    device_id = f"{config_entry.domain}.{config_entry.data[CONF_NAME]}-{config_entry.data[CONF_HOST]}-{config_entry.data[CONF_PORT]}"
    device_identifiers = {(AGENT_DOMAIN, device_id)}
    hass.data[AGENT_DOMAIN][config_entry.entry_id] = {
        CONF_DEVICE_INFO: DeviceInfo(identifiers=device_identifiers, name=name),
        CONF_MODBUS_COORDINATOR: modbus_coordinator,
    }

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers=device_identifiers,
        manufacturer="FläktGroup",
        name=name,
        model="RDKS",
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    await hass.data[AGENT_DOMAIN][config_entry.entry_id][
        CONF_MODBUS_COORDINATOR
    ].async_shutdown()

    if unload_ok:
        hass.data[AGENT_DOMAIN].pop(config_entry.entry_id)

    return unload_ok
