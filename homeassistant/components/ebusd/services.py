"""Services for the Ebusd integration."""

import probatio

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, EBUSD_DATA

SERVICE_EBUSD_WRITE = "ebusd_write"

SERVICE_EBUSD_WRITE_SCHEMA = probatio.Schema(
    {
        probatio.Required("name"): cv.string,
        probatio.Required("value"): cv.string,
    }
)


def _ebusd_write(call: ServiceCall) -> None:
    """Call write method on ebusd."""
    call.hass.data[EBUSD_DATA].write(call)


def setup_services(hass: HomeAssistant) -> None:
    """Register the Ebusd services."""
    hass.services.register(
        DOMAIN, SERVICE_EBUSD_WRITE, _ebusd_write, schema=SERVICE_EBUSD_WRITE_SCHEMA
    )
