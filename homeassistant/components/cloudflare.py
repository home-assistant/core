"""
Update the IP adderesses of your Cloudflare DNS records.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/cloudflare/
"""
import logging
from datetime import timedelta
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_time_interval
from homeassistant.const import (CONF_API_KEY, CONF_EMAIL, CONF_ZONE)

REQUIREMENTS = ['pycfdns==0.0.1']

DOMAIN = 'cloudflare'
CONF_RECORDS = 'records'

INTERVAL = timedelta(minutes=60)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_ZONE): cv.string,
        vol.Optional(CONF_RECORDS, default='None'):
            vol.All(cv.ensure_list, [cv.string]),
    })
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Set up the component."""
    from pycfdns import CloudflareUpdater
    cfupdate = CloudflareUpdater()
    email = config[DOMAIN][CONF_EMAIL]
    key = config[DOMAIN][CONF_API_KEY]
    zone = config[DOMAIN][CONF_ZONE]
    records = config[DOMAIN][CONF_RECORDS]

    def update_records_interval(now):
        """Set up recuring update."""
        _update_cloudflare(cfupdate, email, key, zone, records)

    def update_records_service(now):
        """Set up service for manual trigger."""
        _update_cloudflare(cfupdate, email, key, zone, records)

    track_time_interval(hass, update_records_interval, INTERVAL)
    hass.services.register(
        DOMAIN, 'update_records', update_records_service)
    return True


def _update_cloudflare(cfupdate, email, key, zone, records):
    """Update DNS records for a given zone."""
    _LOGGER.debug('Starting update for zone %s.', zone)

    headers = cfupdate.set_header(email, key)
    _LOGGER.debug('Header data defined as: %s.', headers)

    zoneid = cfupdate.get_zoneID(headers, zone)
    _LOGGER.debug('Zone ID is set to: %s.', zoneid)

    update_records = cfupdate.get_recordInfo(headers, zoneid, zone, records)
    _LOGGER.debug('Records: %s.', update_records)

    result = cfupdate.update_records(headers, zoneid, update_records)
    _LOGGER.debug('Update for zone %s is complete.', zone)

    if result is not True:
        _LOGGER.warning(result)
    return True
