"""Services for the AI Task integration."""

from typing import Any

import probatio

from homeassistant.const import ATTR_ENTITY_ID, CONF_DESCRIPTION, CONF_SELECTOR
from homeassistant.core import (
    HassJobType,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    ATTR_ATTACHMENTS,
    ATTR_INSTRUCTIONS,
    ATTR_REQUIRED,
    ATTR_STRUCTURE,
    ATTR_TASK_NAME,
    DOMAIN,
    SERVICE_GENERATE_DATA,
    SERVICE_GENERATE_IMAGE,
)
from .task import async_generate_data, async_generate_image

STRUCTURE_FIELD_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_DESCRIPTION): str,
        probatio.Optional(ATTR_REQUIRED): bool,
        probatio.Required(CONF_SELECTOR): selector.validate_selector,
    }
)


def _validate_structure_fields(value: dict[str, Any]) -> probatio.Schema:
    """Validate the structure fields as a probatio Schema."""
    if not isinstance(value, dict):
        raise probatio.Invalid("Structure must be a dictionary")
    fields = {}
    for k, v in value.items():
        field_class = (
            probatio.Required if v.get(ATTR_REQUIRED, False) else probatio.Optional
        )
        fields[field_class(k, description=v.get(CONF_DESCRIPTION))] = selector.selector(
            v[CONF_SELECTOR]
        )
    return probatio.Schema(fields, extra=probatio.PREVENT_EXTRA)


async def async_service_generate_data(call: ServiceCall) -> ServiceResponse:
    """Run the data task service."""
    result = await async_generate_data(
        hass=call.hass, context=call.context, **call.data
    )
    return result.as_dict()


async def async_service_generate_image(call: ServiceCall) -> ServiceResponse:
    """Run the image task service."""
    return await async_generate_image(hass=call.hass, context=call.context, **call.data)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the AI Task services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_DATA,
        async_service_generate_data,
        schema=probatio.Schema(
            {
                probatio.Required(ATTR_TASK_NAME): cv.string,
                probatio.Optional(ATTR_ENTITY_ID): cv.entity_id,
                probatio.Required(ATTR_INSTRUCTIONS): cv.string,
                probatio.Optional(ATTR_STRUCTURE): probatio.All(
                    probatio.Schema({str: STRUCTURE_FIELD_SCHEMA}),
                    _validate_structure_fields,
                ),
                probatio.Optional(ATTR_ATTACHMENTS): selector.MediaSelector(
                    {"accept": ["*/*"], "multiple": True}
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
        job_type=HassJobType.Coroutinefunction,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_IMAGE,
        async_service_generate_image,
        schema=probatio.Schema(
            {
                probatio.Required(ATTR_TASK_NAME): cv.string,
                probatio.Optional(ATTR_ENTITY_ID): cv.entity_id,
                probatio.Required(ATTR_INSTRUCTIONS): cv.string,
                probatio.Optional(ATTR_ATTACHMENTS): selector.MediaSelector(
                    {"accept": ["*/*"], "multiple": True}
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
        job_type=HassJobType.Coroutinefunction,
    )
