"""Services for the input_number integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.service import async_register_admin_service

from .const import (
    DATA_INPUT_NUMBER,
    DOMAIN,
    InputNumberService,
    InputNumberServiceArgument,
)

if TYPE_CHECKING:
    from . import InputNumber

RELOAD_SERVICE_SCHEMA = probatio.Schema({})


async def _async_reload_service(service_call: ServiceCall) -> None:
    """Reload yaml entities."""
    hass = service_call.hass
    data = hass.data[DATA_INPUT_NUMBER]
    conf = await data.component.async_prepare_reload(skip_reset=True)
    await data.yaml_collection.async_load(
        [{CONF_ID: id_, **conf} for id_, conf in conf.get(DOMAIN, {}).items()]
    )


async def _async_set_value(entity: InputNumber, service_call: ServiceCall) -> None:
    """Set a new value, given in the unit of the entity state."""
    value = service_call.data[InputNumberServiceArgument.VALUE]
    if value < entity.min_value or value > entity.max_value:
        raise probatio.Invalid(
            f"Invalid value for {entity.entity_id}: {value} (range "
            f"{entity.min_value} - {entity.max_value})"
        )
    native_value = entity.convert_to_native_value(value)
    # Clamp rounding differences of the unit conversion to the native range
    await entity.async_set_native_value(
        min(max(native_value, entity.native_min_value), entity.native_max_value)
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the input_number services."""
    async_register_admin_service(
        hass,
        DOMAIN,
        InputNumberService.RELOAD,
        _async_reload_service,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    component = hass.data[DATA_INPUT_NUMBER].component
    component.async_register_entity_service(
        InputNumberService.SET_VALUE,
        {probatio.Required(InputNumberServiceArgument.VALUE): probatio.Coerce(float)},
        _async_set_value,
    )
    component.async_register_entity_service(
        InputNumberService.INCREMENT, None, "async_increment"
    )
    component.async_register_entity_service(
        InputNumberService.DECREMENT, None, "async_decrement"
    )
