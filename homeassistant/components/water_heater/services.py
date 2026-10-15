"""Services for the water_heater integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.const import ATTR_TEMPERATURE, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import VolDictType
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    ATTR_AWAY_MODE,
    ATTR_OPERATION_MODE,
    DATA_COMPONENT,
    SERVICE_SET_AWAY_MODE,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    WaterHeaterEntityFeature,
)

if TYPE_CHECKING:
    from . import WaterHeaterEntity

CONVERTIBLE_ATTRIBUTE = [ATTR_TEMPERATURE]


SET_AWAY_MODE_SCHEMA: VolDictType = {
    probatio.Required(ATTR_AWAY_MODE): cv.boolean,
}


SET_TEMPERATURE_SCHEMA: VolDictType = {
    probatio.Required(ATTR_TEMPERATURE, "temperature"): probatio.Coerce(float),
    probatio.Optional(ATTR_OPERATION_MODE): cv.string,
}


SET_OPERATION_MODE_SCHEMA: VolDictType = {
    probatio.Required(ATTR_OPERATION_MODE): cv.string,
}


async def _async_service_away_mode(
    entity: WaterHeaterEntity, service: ServiceCall
) -> None:
    """Handle away mode service."""
    if service.data[ATTR_AWAY_MODE]:
        await entity.async_turn_away_mode_on()
    else:
        await entity.async_turn_away_mode_off()


async def _async_service_temperature_set(
    entity: WaterHeaterEntity, service: ServiceCall
) -> None:
    """Handle set temperature service."""
    hass = entity.hass
    kwargs = {}

    for value, temp in service.data.items():
        if value in CONVERTIBLE_ATTRIBUTE:
            kwargs[value] = TemperatureConverter.convert(
                temp,
                hass.config.units.temperature_unit,
                entity.native_temperature_unit,
            )
        else:
            kwargs[value] = temp

    await entity.async_set_temperature(**kwargs)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the water_heater services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SERVICE_TURN_ON, None, "async_turn_on", [WaterHeaterEntityFeature.ON_OFF]
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, None, "async_turn_off", [WaterHeaterEntityFeature.ON_OFF]
    )
    component.async_register_entity_service(
        SERVICE_SET_AWAY_MODE,
        SET_AWAY_MODE_SCHEMA,
        _async_service_away_mode,
        [WaterHeaterEntityFeature.AWAY_MODE],
    )
    component.async_register_entity_service(
        SERVICE_SET_TEMPERATURE,
        SET_TEMPERATURE_SCHEMA,
        _async_service_temperature_set,
        [WaterHeaterEntityFeature.TARGET_TEMPERATURE],
    )
    component.async_register_entity_service(
        SERVICE_SET_OPERATION_MODE,
        SET_OPERATION_MODE_SCHEMA,
        "async_handle_set_operation_mode",
        [WaterHeaterEntityFeature.OPERATION_MODE],
    )
