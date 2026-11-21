"""Update the IP addresses of your Route53 DNS records."""

from datetime import timedelta

import probatio

from homeassistant.const import CONF_DOMAIN, CONF_TTL, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DATA_ROUTE53, DOMAIN
from .helpers import Route53Data, update_route53
from .services import setup_services

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
    domain_config = config[DOMAIN]
    data = hass.data[DATA_ROUTE53] = Route53Data(
        aws_access_key_id=domain_config[CONF_ACCESS_KEY_ID],
        aws_secret_access_key=domain_config[CONF_SECRET_ACCESS_KEY],
        zone=domain_config[CONF_ZONE],
        domain=domain_config[CONF_DOMAIN],
        records=domain_config[CONF_RECORDS],
        ttl=domain_config[CONF_TTL],
    )

    def update_records_interval(now):
        """Set up recurring update."""
        update_route53(data)

    track_time_interval(hass, update_records_interval, INTERVAL)

    setup_services(hass)
    return True
