"""Support for tracking consumption over given periods of time."""

from enum import StrEnum
import logging
import math

import probatio

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback, split_entity_id
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service import async_register_platform_entity_service

from .const import DOMAIN, SIGNAL_RESET_METER

_LOGGER = logging.getLogger(__name__)


class UtilityMeterService(StrEnum):
    """Store keys for utility meter services."""

    CALIBRATE = "calibrate"
    RESET = "reset"


class UtilityMeterServiceArgument(StrEnum):
    """Store keys for utility meter service arguments."""

    VALUE = "value"


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
        UtilityMeterService.RESET,
        async_reset_meters,
        probatio.Schema(
            {ATTR_ENTITY_ID: probatio.All(probatio.EnsureList(), [cv.entity_id])}
        ),
    )

    async_register_platform_entity_service(
        hass,
        DOMAIN,
        UtilityMeterService.CALIBRATE,
        entity_domain=SENSOR_DOMAIN,
        func="async_calibrate",
        schema={
            probatio.Required(UtilityMeterServiceArgument.VALUE): _validate_is_number
        },
    )
