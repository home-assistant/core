"""Support for tracking consumption over given periods of time."""

import logging
import math

import probatio

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback, split_entity_id
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service import async_register_platform_entity_service

from .const import (
    ATTR_VALUE,
    DOMAIN,
    SERVICE_CALIBRATE_METER,
    SERVICE_RESET,
    SIGNAL_RESET_METER,
)

_LOGGER = logging.getLogger(__name__)


def _validate_is_number(value):
    """Validate value is a number."""
    try:
        if math.isfinite(float(value)):
            return value
    except ValueError, TypeError:
        pass
    raise probatio.Invalid("Value is not a number")


async def async_reset_meters(service_call: ServiceCall) -> None:
    """Reset all sensors of a meter."""
    meters = service_call.data["entity_id"]

    for meter in meters:
        _LOGGER.debug("resetting meter %s", meter)
        domain, entity = split_entity_id(meter)
        # backward compatibility up to 2022.07:
        if domain == DOMAIN:
            async_dispatcher_send(
                service_call.hass, SIGNAL_RESET_METER, f"{SELECT_DOMAIN}.{entity}"
            )
        else:
            async_dispatcher_send(service_call.hass, SIGNAL_RESET_METER, meter)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET,
        async_reset_meters,
        probatio.Schema(
            {ATTR_ENTITY_ID: probatio.All(probatio.EnsureList(), [cv.entity_id])}
        ),
    )

    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CALIBRATE_METER,
        entity_domain=Platform.SENSOR,
        func="async_calibrate",
        schema={probatio.Required(ATTR_VALUE): _validate_is_number},
    )
