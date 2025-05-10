"""The mill component."""

from __future__ import annotations

from datetime import timedelta

from mill import Mill
from mill_local import Mill as MillLocal

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLOUD, CONNECTION_TYPE, DOMAIN, LOCAL
from .coordinator import MillDataUpdateCoordinator, MillHistoricDataUpdateCoordinator

PLATFORMS = [Platform.CLIMATE, Platform.NUMBER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Mill heater."""
    hass.data.setdefault(DOMAIN, {LOCAL: {}, CLOUD: {}})

    if entry.data.get(CONNECTION_TYPE) == LOCAL:
        mill_data_connection = MillLocal(
            entry.data[CONF_IP_ADDRESS],
            websession=async_get_clientsession(hass),
        )
        update_interval = timedelta(seconds=15)
        key = entry.data[CONF_IP_ADDRESS]
        conn_type = LOCAL
    else:
        mill_data_connection = Mill(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            websession=async_get_clientsession(hass),
        )
        update_interval = timedelta(seconds=30)
        key = entry.data[CONF_USERNAME]
        conn_type = CLOUD

        historic_data_coordinator = MillHistoricDataUpdateCoordinator(
            hass,
            mill_data_connection=mill_data_connection,
        )
        historic_data_coordinator.async_add_listener(lambda: None)
        await historic_data_coordinator.async_config_entry_first_refresh()
    try:
        if not await mill_data_connection.connect():
            raise ConfigEntryNotReady
    except TimeoutError as error:
        raise ConfigEntryNotReady from error
    data_coordinator = MillDataUpdateCoordinator(
        hass, entry, mill_data_connection, update_interval
    )

    await data_coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][conn_type][key] = data_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
