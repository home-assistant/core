"""Support for Mythic Beasts Dynamic DNS service."""

from datetime import timedelta

import mbddns
import probatio

from homeassistant.const import (
    CONF_DOMAIN,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

DOMAIN = "mythicbeastsdns"

DEFAULT_INTERVAL = timedelta(minutes=10)

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Required(CONF_DOMAIN): cv.string,
                probatio.Required(CONF_HOST): cv.string,
                probatio.Required(CONF_PASSWORD): cv.string,
                probatio.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL
                ): probatio.All(cv.time_period, cv.positive_timedelta),
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the Mythic Beasts component."""
    domain = config[DOMAIN][CONF_DOMAIN]
    password = config[DOMAIN][CONF_PASSWORD]
    host = config[DOMAIN][CONF_HOST]
    update_interval = config[DOMAIN][CONF_SCAN_INTERVAL]

    session = async_get_clientsession(hass)

    result = await mbddns.update(domain, password, host, session=session)

    if not result:
        return False

    async def update_domain_interval(now):
        """Update the DNS entry."""
        await mbddns.update(domain, password, host, session=session)

    async_track_time_interval(hass, update_domain_interval, update_interval)

    return True
