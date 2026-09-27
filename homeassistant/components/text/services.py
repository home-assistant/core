"""Services for the Text integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import ATTR_VALUE, DATA_COMPONENT, SERVICE_SET_VALUE

if TYPE_CHECKING:
    from . import TextEntity


async def _async_set_value(entity: TextEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to set a new value."""
    value = service_call.data[ATTR_VALUE]
    if len(value) < entity.min:
        raise ValueError(
            f"Value {value} for {entity.entity_id} is too short (minimum length"
            f" {entity.min})"
        )
    if len(value) > entity.max:
        raise ValueError(
            f"Value {value} for {entity.entity_id}"
            f" is too long (maximum length {entity.max})"
        )
    if entity.pattern_cmp and not entity.pattern_cmp.match(value):
        raise ValueError(
            f"Value {value} for {entity.entity_id}"
            f" doesn't match pattern {entity.pattern}"
        )
    await entity.async_set_value(value)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the text services."""
    hass.data[DATA_COMPONENT].async_register_entity_service(
        SERVICE_SET_VALUE,
        {probatio.Required(ATTR_VALUE): cv.string},
        _async_set_value,
    )
