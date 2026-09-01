"""Support for RFXtrx services."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import ATTR_EVENT, DATA_RFXOBJECT, DOMAIN, SERVICE_SEND


def _bytearray_string(data: Any) -> bytearray:
    val = cv.string(data)
    try:
        return bytearray.fromhex(val)
    except ValueError as err:
        raise vol.Invalid(
            "Data must be a hex string with multiple of two characters"
        ) from err


SERVICE_SEND_SCHEMA = vol.Schema({ATTR_EVENT: _bytearray_string})


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the RFXtrx services."""

    def send(call: ServiceCall) -> None:
        rfx_object = hass.data.get(DOMAIN, {}).get(DATA_RFXOBJECT)
        if rfx_object is None:
            raise HomeAssistantError("RFXtrx is not connected, cannot send event")
        rfx_object.transport.send(call.data[ATTR_EVENT])

    hass.services.async_register(DOMAIN, SERVICE_SEND, send, schema=SERVICE_SEND_SCHEMA)
