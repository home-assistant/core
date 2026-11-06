"""Services for the Route53 integration."""

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DATA_ROUTE53, DOMAIN
from .helpers import update_route53


def _update_records(call: ServiceCall) -> None:
    """Update the Route53 records."""
    update_route53(call.hass.data[DATA_ROUTE53])


def setup_services(hass: HomeAssistant) -> None:
    """Register the Route53 services."""
    hass.services.register(DOMAIN, "update_records", _update_records)
