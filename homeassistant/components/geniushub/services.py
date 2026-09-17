"""Support for Genius Hub services."""

from datetime import timedelta

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service import verify_domain_control

from .const import (
    ATTR_DURATION,
    ATTR_ZONE_MODE,
    DOMAIN,
    SVC_SET_ZONE_MODE,
    SVC_SET_ZONE_OVERRIDE,
)

SET_ZONE_MODE_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_ENTITY_ID): cv.entity_id,
        probatio.Required(ATTR_ZONE_MODE): probatio.In(["off", "timer", "footprint"]),
    }
)
SET_ZONE_OVERRIDE_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_ENTITY_ID): cv.entity_id,
        probatio.Required(ATTR_TEMPERATURE): probatio.All(
            probatio.Coerce(float), probatio.Range(min=4, max=28)
        ),
        probatio.Optional(ATTR_DURATION): probatio.All(
            cv.time_period,
            probatio.Range(min=timedelta(minutes=5), max=timedelta(days=1)),
        ),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Genius Hub services."""

    @verify_domain_control(DOMAIN)
    async def set_zone_mode(call: ServiceCall) -> None:
        """Set the system mode."""
        entity_id = call.data[ATTR_ENTITY_ID]

        registry = er.async_get(hass)
        registry_entry = registry.async_get(entity_id)

        if registry_entry is None or registry_entry.platform != DOMAIN:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_entity_id",
                translation_placeholders={"entity_id": entity_id},
            )

        if registry_entry.domain != CLIMATE_DOMAIN:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_zone",
                translation_placeholders={"entity_id": entity_id},
            )

        payload = {
            "unique_id": registry_entry.unique_id,
            "service": call.service,
            "data": call.data,
        }

        async_dispatcher_send(hass, DOMAIN, payload)

    hass.services.async_register(
        DOMAIN, SVC_SET_ZONE_MODE, set_zone_mode, schema=SET_ZONE_MODE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SVC_SET_ZONE_OVERRIDE, set_zone_mode, schema=SET_ZONE_OVERRIDE_SCHEMA
    )
