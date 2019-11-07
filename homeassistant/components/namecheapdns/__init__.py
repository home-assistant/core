"""Support for namecheap DNS services."""
from datetime import timedelta
import logging

import defusedxml.ElementTree as ET
import voluptuous as vol

from homeassistant.const import (
    CONF_DOMAIN,
    CONF_DOMAINS,
    CONF_HOSTS,
    CONF_PASSWORD,
    ATTR_DOMAIN,
    CONF_SCAN_INTERVAL,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

DOMAIN = "namecheapdns"

ATTR_HOST = "host"
ATTR_PASSWORD = "password"

UPDATE_URL = "https://dynamicdns.park-your-domain.com/update"

DEFAULT_HOST = "@"
DEFAULT_INTERVAL = 5

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_DOMAINS): vol.All(
                    cv.ensure_list,
                    [
                        vol.Schema(
                            {
                                vol.Required(CONF_DOMAIN): cv.string,
                                vol.Optional(CONF_HOSTS): vol.All(
                                    cv.ensure_list, [cv.string]
                                ),
                                vol.Required(CONF_PASSWORD): cv.string,
                            }
                        )
                    ],
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL
                ): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Initialize the namecheap DNS component."""
    interval = timedelta(minutes=config[DOMAIN][CONF_SCAN_INTERVAL])
    if CONF_DOMAINS in config[DOMAIN]:
        domains = config[DOMAIN][CONF_DOMAINS]
    else:
        domains = None

    session = async_get_clientsession(hass)

    result = await _update_all_namecheapdns(session, domains)

    if not result:
        return False

    async def update_domain_interval(now):
        """Update the namecheap DNS entry."""
        await _update_all_namecheapdns(session, domains)

    async def handle_update(call):
        """Handle service call to update the namecheap DNS entry."""
        host = call.data.get(ATTR_HOST, DEFAULT_HOST)
        domain = call.data.get(ATTR_DOMAIN)
        password = call.data.get(ATTR_PASSWORD)
        await _update_namecheapdns(session, host, domain, password)

    async def handle_update_all(call):
        """Handle service call to update all configured domains."""
        await _update_all_namecheapdns(session, domains)

    hass.services.async_register(DOMAIN, "update", handle_update)
    hass.services.async_register(DOMAIN, "update_all", handle_update_all)

    if CONF_DOMAINS in config[DOMAIN]:
        async_track_time_interval(hass, update_domain_interval, interval)

    return result


async def _update_all_namecheapdns(session, domains):
    """Update all configured domains."""
    if domains is not None:
        _LOGGER.debug("Updating all configured domains")
        for domain_dict in domains:
            domain = domain_dict[CONF_DOMAIN]
            password = domain_dict[CONF_PASSWORD]
            if CONF_HOSTS in domain_dict:
                for host in domain_dict[CONF_HOSTS]:
                    resp = await _update_namecheapdns(session, host, domain, password)
                    if not resp:
                        return resp
            else:
                _LOGGER.debug("No hosts configured, updating default")
                return await _update_namecheapdns(
                    session, DEFAULT_HOST, domain, password
                )
    else:
        _LOGGER.debug("No domains to update")
    return True


async def _update_namecheapdns(session, host, domain, password):
    """Update namecheap DNS entry."""
    params = {"host": host, "domain": domain, "password": password}
    resp = await session.get(UPDATE_URL, params=params)
    xml_string = await resp.text()
    root = ET.fromstring(xml_string)
    err_count = root.find("ErrCount").text

    if int(err_count) != 0:
        _LOGGER.warning("Updating namecheap domain failed: %s", domain)
        for error in root.find("errors"):
            _LOGGER.warning(error.text)
        return False

    _LOGGER.debug("Updated %s.%s", host, domain)

    return True
