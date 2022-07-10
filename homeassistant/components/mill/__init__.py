"""The mill component."""
from __future__ import annotations

from datetime import timedelta
import logging

from mill import Mill
from mill_local import Mill as MillLocal

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CLOUD, CONNECTION_TYPE, DOMAIN, LOCAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]


class MillDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Mill data."""

    def __init__(
        self,
        hass: HomeAssistant,
        update_interval: timedelta | None = None,
        *,
        mill_data_connection: Mill | MillLocal,
    ) -> None:
        """Initialize global Mill data updater."""
        self.mill_data_connection = mill_data_connection

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=mill_data_connection.fetch_heater_and_sensor_data,
            update_interval=update_interval,
        )


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

    if not await mill_data_connection.connect():
        raise ConfigEntryNotReady
    data_coordinator = MillDataUpdateCoordinator(
        hass,
        mill_data_connection=mill_data_connection,
        update_interval=update_interval,
    )

    hass.data[DOMAIN][conn_type][key] = data_coordinator
    await data_coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
