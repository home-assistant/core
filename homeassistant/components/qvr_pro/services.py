"""Services for the QVR Pro integration."""

import probatio
from pyqvrpro import Client

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, SERVICE_START_RECORD, SERVICE_STOP_RECORD

SERVICE_CHANNEL_GUID = "guid"

SERVICE_CHANNEL_RECORD_SCHEMA = probatio.Schema(
    {probatio.Required(SERVICE_CHANNEL_GUID): cv.string}
)


def _handle_start_record(call: ServiceCall) -> None:
    """Start recording a channel."""
    qvrpro: Client = call.hass.data[DOMAIN]["client"]
    guid = call.data[SERVICE_CHANNEL_GUID]
    qvrpro.start_recording(guid)


def _handle_stop_record(call: ServiceCall) -> None:
    """Stop recording a channel."""
    qvrpro: Client = call.hass.data[DOMAIN]["client"]
    guid = call.data[SERVICE_CHANNEL_GUID]
    qvrpro.stop_recording(guid)


def setup_services(hass: HomeAssistant) -> None:
    """Register the QVR Pro services."""
    hass.services.register(
        DOMAIN,
        SERVICE_START_RECORD,
        _handle_start_record,
        schema=SERVICE_CHANNEL_RECORD_SCHEMA,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_STOP_RECORD,
        _handle_stop_record,
        schema=SERVICE_CHANNEL_RECORD_SCHEMA,
    )
