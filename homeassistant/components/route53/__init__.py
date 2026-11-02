"""Update the IP addresses of your Route53 DNS records."""

from datetime import timedelta

import probatio

from homeassistant.const import CONF_DOMAIN, CONF_TTL, CONF_ZONE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .helpers import _update_route53

CONF_ACCESS_KEY_ID = "aws_access_key_id"
CONF_SECRET_ACCESS_KEY = "aws_secret_access_key"
CONF_RECORDS = "records"

INTERVAL = timedelta(minutes=60)
DEFAULT_TTL = 300

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Required(CONF_ACCESS_KEY_ID): cv.string,
                probatio.Required(CONF_DOMAIN): cv.string,
                probatio.Required(CONF_RECORDS): probatio.All(
                    probatio.EnsureList(), [cv.string]
                ),
                probatio.Required(probatio.Secret(CONF_SECRET_ACCESS_KEY)): cv.string,
                probatio.Required(CONF_ZONE): cv.string,
                probatio.Optional(CONF_TTL, default=DEFAULT_TTL): cv.positive_int,
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Route53 component."""
    domain = config[DOMAIN][CONF_DOMAIN]
    records = config[DOMAIN][CONF_RECORDS]
    zone = config[DOMAIN][CONF_ZONE]
    aws_access_key_id = config[DOMAIN][CONF_ACCESS_KEY_ID]
    aws_secret_access_key = config[DOMAIN][CONF_SECRET_ACCESS_KEY]
    ttl = config[DOMAIN][CONF_TTL]

    def update_records_interval(now):
        """Set up recurring update."""
        _update_route53(
            aws_access_key_id, aws_secret_access_key, zone, domain, records, ttl
        )

    def update_records_service(call: ServiceCall) -> None:
        """Set up service for manual trigger."""
        _update_route53(
            aws_access_key_id, aws_secret_access_key, zone, domain, records, ttl
        )

    track_time_interval(hass, update_records_interval, INTERVAL)

    # Should be adjusted to register actions in setup_services in services.py
    # pylint: disable-next=home-assistant-action-registered-outside-services-module
    hass.services.register(DOMAIN, "update_records", update_records_service)
    return True
