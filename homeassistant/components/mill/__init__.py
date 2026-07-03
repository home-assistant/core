"""The mill component."""

from datetime import timedelta

from mill import Mill
from mill_local import Mill as MillLocal

from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .climate import SET_ROOM_TEMP_SCHEMA
from .const import (
    ATTR_AWAY_TEMP,
    ATTR_COMFORT_TEMP,
    ATTR_ROOM_NAME,
    ATTR_SLEEP_TEMP,
    CLOUD,
    CONNECTION_TYPE,
    DOMAIN,
    LOCAL,
    SERVICE_SET_ROOM_TEMP,
)
from .coordinator import (
    MillConfigEntry,
    MillDataUpdateCoordinator,
    MillHistoricDataUpdateCoordinator,
)

PLATFORMS = [Platform.CLIMATE, Platform.NUMBER, Platform.SENSOR]

__all__ = ["CLOUD", "CONNECTION_TYPE", "DOMAIN", "LOCAL"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Mill integration."""
    async_register_services(hass)

    return True


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register Mill services."""

    async def set_room_temp(service: ServiceCall) -> None:
        """Set room temp."""
        room_name = service.data[ATTR_ROOM_NAME]
        sleep_temp = service.data.get(ATTR_SLEEP_TEMP)
        comfort_temp = service.data.get(ATTR_COMFORT_TEMP)
        away_temp = service.data.get(ATTR_AWAY_TEMP)

        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coordinator = entry.runtime_data
            await coordinator.mill_data_connection.set_room_temperatures_by_name(
                room_name, sleep_temp, comfort_temp, away_temp
            )

    hass.services.async_register(
        DOMAIN, SERVICE_SET_ROOM_TEMP, set_room_temp, schema=SET_ROOM_TEMP_SCHEMA
    )


async def async_setup_entry(hass: HomeAssistant, entry: MillConfigEntry) -> bool:
    """Set up the Mill heater."""
    if entry.data.get(CONNECTION_TYPE) == LOCAL:
        mill_data_connection = MillLocal(
            entry.data[CONF_IP_ADDRESS],
            websession=async_get_clientsession(hass),
        )
        update_interval = timedelta(seconds=15)
    else:
        mill_data_connection = Mill(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            websession=async_get_clientsession(hass),
        )
        update_interval = timedelta(seconds=30)

        historic_data_coordinator = MillHistoricDataUpdateCoordinator(
            hass,
            entry,
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
    entry.runtime_data = data_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MillConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
