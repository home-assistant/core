"""Services for the Mill integration."""

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ATTR_AWAY_TEMP,
    ATTR_COMFORT_TEMP,
    ATTR_ROOM_NAME,
    ATTR_SLEEP_TEMP,
    DOMAIN,
    SERVICE_SET_ROOM_TEMP,
)

if TYPE_CHECKING:
    from .coordinator import MillConfigEntry

SET_ROOM_TEMP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ROOM_NAME): cv.string,
        vol.Optional(ATTR_AWAY_TEMP): cv.positive_int,
        vol.Optional(ATTR_COMFORT_TEMP): cv.positive_int,
        vol.Optional(ATTR_SLEEP_TEMP): cv.positive_int,
    }
)


async def _set_room_temp(call: ServiceCall) -> None:
    """Set room temp."""
    room_name = call.data[ATTR_ROOM_NAME]
    sleep_temp = call.data.get(ATTR_SLEEP_TEMP)
    comfort_temp = call.data.get(ATTR_COMFORT_TEMP)
    away_temp = call.data.get(ATTR_AWAY_TEMP)

    entry: MillConfigEntry = service.async_get_config_entry(call.hass, DOMAIN, None)
    await entry.runtime_data.mill_data_connection.set_room_temperatures_by_name(
        room_name, sleep_temp, comfort_temp, away_temp
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Mill services."""

    hass.services.async_register(
        DOMAIN, SERVICE_SET_ROOM_TEMP, _set_room_temp, schema=SET_ROOM_TEMP_SCHEMA
    )
