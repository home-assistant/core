"""Services for the Mill integration."""

from enum import StrEnum

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN
from .coordinator import MillConfigEntry


class MillService(StrEnum):
    """Store keys for Mill services."""

    SET_ROOM_TEMPERATURE = "set_room_temperature"


class MillServiceArgument(StrEnum):
    """Store keys for Mill service arguments."""

    ROOM_NAME = "room_name"
    AWAY_TEMP = "away_temp"
    COMFORT_TEMP = "comfort_temp"
    SLEEP_TEMP = "sleep_temp"


SET_ROOM_TEMP_SCHEMA = probatio.Schema(
    {
        probatio.Required(MillServiceArgument.ROOM_NAME): cv.string,
        probatio.Optional(MillServiceArgument.AWAY_TEMP): cv.positive_int,
        probatio.Optional(MillServiceArgument.COMFORT_TEMP): cv.positive_int,
        probatio.Optional(MillServiceArgument.SLEEP_TEMP): cv.positive_int,
    }
)


async def _set_room_temp(call: ServiceCall) -> None:
    """Set room temp."""
    entry: MillConfigEntry = service.async_get_config_entry(call.hass, DOMAIN, None)
    await entry.runtime_data.mill_data_connection.set_room_temperatures_by_name(
        call.data[MillServiceArgument.ROOM_NAME],
        call.data.get(MillServiceArgument.SLEEP_TEMP),
        call.data.get(MillServiceArgument.COMFORT_TEMP),
        call.data.get(MillServiceArgument.AWAY_TEMP),
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Mill services."""

    hass.services.async_register(
        DOMAIN,
        MillService.SET_ROOM_TEMPERATURE,
        _set_room_temp,
        schema=SET_ROOM_TEMP_SCHEMA,
    )
