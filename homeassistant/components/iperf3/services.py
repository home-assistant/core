"""Services for the Iperf3 integration."""

from enum import StrEnum

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN


class Iperf3Service(StrEnum):
    """Store keys for Iperf3 services."""

    SPEEDTEST = "speedtest"


class Iperf3ServiceArgument(StrEnum):
    """Store keys for Iperf3 service arguments."""

    HOST = "host"


SERVICE_SCHEMA = probatio.Schema(
    {probatio.Optional(Iperf3ServiceArgument.HOST, default=None): cv.string}
)


def _update(call: ServiceCall) -> None:
    """Service call to manually update the data."""
    hass = call.hass
    called_host = call.data[Iperf3ServiceArgument.HOST]
    if called_host in hass.data[DOMAIN]:
        hass.data[DOMAIN][called_host].update()
    else:
        for iperf3_host in hass.data[DOMAIN].values():
            iperf3_host.update()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Iperf3 integration."""

    hass.services.async_register(
        DOMAIN, Iperf3Service.SPEEDTEST, _update, schema=SERVICE_SCHEMA
    )
