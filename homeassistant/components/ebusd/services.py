"""Services for the Ebusd integration."""

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, EBUSD_DATA

SERVICE_EBUSD_WRITE = "ebusd_write"


def _ebusd_write(call: ServiceCall) -> None:
    """Call write method on ebusd."""
    call.hass.data[EBUSD_DATA].write(call)


def setup_services(hass: HomeAssistant) -> None:
    """Register the Ebusd services."""
    hass.services.register(DOMAIN, SERVICE_EBUSD_WRITE, _ebusd_write)
