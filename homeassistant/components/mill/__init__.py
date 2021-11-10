"""The mill component."""
from datetime import timedelta
import logging

from mill import Mill
from mill_local import Mill as MillLocal

from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CLOUD, CONNECTION_TYPE, DOMAIN, LOCAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate", "sensor"]


class MillDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Mill data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        mill_data_connection: Mill,
    ) -> None:
        """Initialize global Mill data updater."""
        self.mill_data_connection = mill_data_connection

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=mill_data_connection.fetch_heater_and_sensor_data,
            update_interval=timedelta(seconds=30),
        )


class LocalMillDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Mill data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        mill_data_connection: MillLocal,
    ) -> None:
        """Initialize global Mill data updater."""
        self.mill_data_connection = mill_data_connection

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=mill_data_connection.get_control_status,
            update_interval=timedelta(seconds=15),
        )


async def async_setup_entry(hass, entry):
    """Set up the Mill heater."""
    hass.data.setdefault(DOMAIN, {LOCAL: {}, CLOUD: {}})

    if entry.data[CONNECTION_TYPE] == CLOUD:
        mill_data_connection = Mill(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            websession=async_get_clientsession(hass),
        )
        if not await mill_data_connection.connect():
            raise ConfigEntryNotReady

        data_coordinator = MillDataUpdateCoordinator(
            hass,
            mill_data_connection=mill_data_connection,
        )
        hass.data[DOMAIN][CLOUD] = data_coordinator

    else:
        mill_data_connection = MillLocal(
            entry.data[CONF_IP_ADDRESS],
            websession=async_get_clientsession(hass),
        )

        status = await mill_data_connection.get_status()
        if not status:
            raise ConfigEntryNotReady

        data_coordinator = LocalMillDataUpdateCoordinator(
            hass,
            mill_data_connection=mill_data_connection,
        )
        hass.data[DOMAIN][LOCAL][entry.data[CONF_IP_ADDRESS]] = data_coordinator

    await data_coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
