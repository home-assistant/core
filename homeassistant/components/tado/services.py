"""Services for the Tado integration."""

from enum import StrEnum
import logging

import probatio

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, selector, service
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.helpers.typing import VolDictType

from .const import (
    ATTR_MESSAGE,
    CONST_EXCLUSIVE_OVERLAY_GROUP,
    CONST_OVERLAY_TADO_OPTIONS,
    DOMAIN,
)
from .coordinator import TadoConfigEntry

_LOGGER = logging.getLogger(__name__)


class TadoService(StrEnum):
    """Store keys for Tado services."""

    ADD_METER_READING = "add_meter_reading"
    SET_CLIMATE_TEMPERATURE_OFFSET = "set_climate_temperature_offset"
    SET_CLIMATE_TIMER = "set_climate_timer"
    SET_WATER_HEATER_TIMER = "set_water_heater_timer"


class TadoServiceArgument(StrEnum):
    """Store keys for Tado service arguments."""

    CONFIG_ENTRY = "config_entry"
    OFFSET = "offset"
    READING = "reading"
    REQUESTED_OVERLAY = "requested_overlay"
    TEMPERATURE = "temperature"
    TIME_PERIOD = "time_period"


SCHEMA_ADD_METER_READING = probatio.Schema(
    {
        probatio.Required(
            TadoServiceArgument.CONFIG_ENTRY
        ): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
        probatio.Required(TadoServiceArgument.READING): probatio.Coerce(int),
    }
)


CLIMATE_TIMER_SCHEMA: VolDictType = {
    probatio.Required(TadoServiceArgument.TEMPERATURE): probatio.Coerce(float),
    probatio.Exclusive(
        TadoServiceArgument.TIME_PERIOD, CONST_EXCLUSIVE_OVERLAY_GROUP
    ): probatio.All(
        cv.time_period, cv.positive_timedelta, lambda td: td.total_seconds()
    ),
    probatio.Exclusive(
        TadoServiceArgument.REQUESTED_OVERLAY, CONST_EXCLUSIVE_OVERLAY_GROUP
    ): probatio.In(CONST_OVERLAY_TADO_OPTIONS),
}

CLIMATE_TEMP_OFFSET_SCHEMA: VolDictType = {
    probatio.Required(TadoServiceArgument.OFFSET, default=0): probatio.Coerce(float),
}

WATER_HEATER_TIMER_SCHEMA: VolDictType = {
    probatio.Required(
        TadoServiceArgument.TIME_PERIOD, default="01:00:00"
    ): probatio.All(
        cv.time_period, cv.positive_timedelta, lambda td: td.total_seconds()
    ),
    probatio.Optional(TadoServiceArgument.TEMPERATURE): probatio.Coerce(float),
}


async def _add_meter_reading(call: ServiceCall) -> None:
    """Send meter reading to Tado."""
    reading: int = call.data[TadoServiceArgument.READING]
    _LOGGER.debug("Add meter reading %s", reading)

    entry: TadoConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[TadoServiceArgument.CONFIG_ENTRY]
    )

    coordinator = entry.runtime_data
    response: dict = await coordinator.set_meter_reading(
        call.data[TadoServiceArgument.READING]
    )

    if ATTR_MESSAGE in response:
        raise HomeAssistantError(response[ATTR_MESSAGE])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Tado integration."""

    hass.services.async_register(
        DOMAIN,
        TadoService.ADD_METER_READING,
        _add_meter_reading,
        SCHEMA_ADD_METER_READING,
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        TadoService.SET_CLIMATE_TIMER,
        entity_domain=Platform.CLIMATE,
        func="set_timer",
        schema=CLIMATE_TIMER_SCHEMA,
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        TadoService.SET_CLIMATE_TEMPERATURE_OFFSET,
        entity_domain=Platform.CLIMATE,
        func="set_temp_offset",
        schema=CLIMATE_TEMP_OFFSET_SCHEMA,
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        TadoService.SET_WATER_HEATER_TIMER,
        entity_domain=Platform.WATER_HEATER,
        func="set_timer",
        schema=WATER_HEATER_TIMER_SCHEMA,
    )
