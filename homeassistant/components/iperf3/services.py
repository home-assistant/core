"""Services for the Iperf3 integration."""

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import ATTR_HOST, DOMAIN

SERVICE_SCHEMA = probatio.Schema(
    {probatio.Optional(ATTR_HOST, default=None): cv.string}
)


def _update(call: ServiceCall) -> None:
    """Service call to manually update the data."""
    hass = call.hass
    called_host = call.data[ATTR_HOST]
    if called_host in hass.data[DOMAIN]:
        hass.data[DOMAIN][called_host].update()
    else:
        for iperf3_host in hass.data[DOMAIN].values():
            iperf3_host.update()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Iperf3 integration."""

    hass.services.async_register(DOMAIN, "speedtest", _update, schema=SERVICE_SCHEMA)
