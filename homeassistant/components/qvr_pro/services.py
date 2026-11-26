"""Services for the QVR Pro integration."""

from enum import StrEnum

import probatio
from pyqvrpro import Client

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN


class QVRProService(StrEnum):
    """Store keys for QVR Pro services."""

    START_RECORD = "start_record"
    STOP_RECORD = "stop_record"


class QVRProServiceArgument(StrEnum):
    """Store keys for QVR Pro service arguments."""

    GUID = "guid"


SERVICE_CHANNEL_RECORD_SCHEMA = probatio.Schema(
    {probatio.Required(QVRProServiceArgument.GUID): cv.string}
)


def _handle_start_record(call: ServiceCall) -> None:
    """Start recording a channel."""
    qvrpro: Client = call.hass.data[DOMAIN]["client"]
    guid = call.data[QVRProServiceArgument.GUID]
    qvrpro.start_recording(guid)


def _handle_stop_record(call: ServiceCall) -> None:
    """Stop recording a channel."""
    qvrpro: Client = call.hass.data[DOMAIN]["client"]
    guid = call.data[QVRProServiceArgument.GUID]
    qvrpro.stop_recording(guid)


def setup_services(hass: HomeAssistant) -> None:
    """Register the QVR Pro services."""
    hass.services.register(
        DOMAIN,
        QVRProService.START_RECORD,
        _handle_start_record,
        schema=SERVICE_CHANNEL_RECORD_SCHEMA,
    )
    hass.services.register(
        DOMAIN,
        QVRProService.STOP_RECORD,
        _handle_stop_record,
        schema=SERVICE_CHANNEL_RECORD_SCHEMA,
    )
