"""Services for the Number integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError

from .const import ATTR_VALUE, DATA_COMPONENT, DOMAIN, SERVICE_SET_VALUE

if TYPE_CHECKING:
    from . import NumberEntity


async def _async_set_value(entity: NumberEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to set a new value."""
    value = service_call.data["value"]
    if value < entity.min_value or value > entity.max_value:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="out_of_range",
            translation_placeholders={
                "value": value,
                "entity_id": entity.entity_id,
                "min_value": str(entity.min_value),
                "max_value": str(entity.max_value),
            },
        )

    try:
        native_value = entity.convert_to_native_value(value)
        # Clamp to the native range
        native_value = min(
            max(native_value, entity.native_min_value), entity.native_max_value
        )
        await entity.async_set_native_value(native_value)
    except NotImplementedError:
        await entity.async_set_value(value)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the number services."""
    hass.data[DATA_COMPONENT].async_register_entity_service(
        SERVICE_SET_VALUE,
        {probatio.Required(ATTR_VALUE): probatio.Coerce(float)},
        _async_set_value,
    )
