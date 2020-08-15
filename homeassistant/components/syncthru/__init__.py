"""The syncthru component."""

from typing import Set, Tuple

from pysyncthru import SyncThru

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import DEFAULT_MODEL, DEFAULT_NAME_TEMPLATE, DOMAIN
from .exceptions import SyncThruNotSupported


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up config entry."""

    session = aiohttp_client.async_get_clientsession(hass)
    printer = hass.data[DOMAIN][entry.entry_id] = SyncThru(
        entry.data[CONF_URL], session
    )

    try:
        await printer.update()
    except ValueError as ex:
        raise SyncThruNotSupported from ex
    else:
        if printer.is_unknown_state():
            raise ConfigEntryNotReady

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=device_connections(printer),
        identifiers={(DOMAIN, printer.serial_number())},
        model=printer.model(),
        name=DEFAULT_NAME_TEMPLATE.format(printer.model() or DEFAULT_MODEL),
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, SENSOR_DOMAIN)
    )
    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, SENSOR_DOMAIN)
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


def device_connections(printer: SyncThru) -> Set[Tuple[str, str]]:
    """Get device connections for device registry."""
    connections = set()
    try:
        mac = printer.raw()["identity"]["mac_addr"]
        if mac:
            connections.add((dr.CONNECTION_NETWORK_MAC, mac))
    except AttributeError:
        pass
    return connections
