"""Services for the Route53 integration."""

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DATA_ROUTE53, DOMAIN
from .helpers import update_route53


def _update_records(call: ServiceCall) -> None:
    """Update the Route53 records."""
    data = call.hass.data[DATA_ROUTE53]
    update_route53(
        data.aws_access_key_id,
        data.aws_secret_access_key,
        data.zone,
        data.domain,
        data.records,
        data.ttl,
    )


def setup_services(hass: HomeAssistant) -> None:
    """Register the Route53 services."""
    hass.services.register(DOMAIN, "update_records", _update_records)
