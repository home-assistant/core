"""Services for the Text integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DATA_COMPONENT, DOMAIN, TextService, TextServiceArgument

if TYPE_CHECKING:
    from .entity import TextEntity


async def _async_set_value(entity: TextEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to set a new value."""
    value = service_call.data[TextServiceArgument.VALUE]
    if len(value) < entity.min:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="value_too_short",
            translation_placeholders={
                "value": value,
                "entity_id": entity.entity_id,
                "min": str(entity.min),
            },
        )
    if len(value) > entity.max:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="value_too_long",
            translation_placeholders={
                "value": value,
                "entity_id": entity.entity_id,
                "max": str(entity.max),
            },
        )
    if entity.pattern_cmp and not entity.pattern_cmp.match(value):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="value_pattern_mismatch",
            translation_placeholders={
                "value": value,
                "entity_id": entity.entity_id,
                "pattern": str(entity.pattern),
            },
        )
    await entity.async_set_value(value)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the text services."""
    hass.data[DATA_COMPONENT].async_register_entity_service(
        TextService.SET_VALUE,
        {probatio.Required(TextServiceArgument.VALUE): cv.string},
        _async_set_value,
    )
