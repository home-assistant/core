"""
This component provides support for Netgear Arlo IP cameras.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/arlo/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol
from requests.exceptions import HTTPError, ConnectTimeout

from homeassistant.helpers import config_validation as cv
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL)
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, dispatcher_send)

REQUIREMENTS = ['pyarlo==0.1.2']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by arlo.netgear.com"

DATA_ARLO = 'data_arlo'
DEFAULT_BRAND = 'Netgear Arlo'
DOMAIN = 'arlo'

NOTIFICATION_ID = 'arlo_notification'
NOTIFICATION_TITLE = 'Arlo Component Setup'

#SCAN_INTERVAL = timedelta(minutes=5)
SCAN_INTERVAL = timedelta(seconds=60)

SIGNAL_UPDATE_ARLO = "arlo_update"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            cv.time_period,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up an Arlo component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

    try:
        from pyarlo import PyArlo

        arlo = PyArlo(username, password, preload=False)
        if not arlo.is_connected:
            return False
        hass.data[DATA_ARLO] = ArloHub(arlo)
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Netgear Arlo: %s", str(ex))
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    def hub_refresh(event_time):
        """Call ArloHub to refresh information."""
        _LOGGER.debug("Updating Arlo Hub component")
        hass.data[DATA_ARLO].hub.update()
        dispatcher_send(hass, SIGNAL_UPDATE_ARLO)

    track_time_interval(hass, hub_refresh, scan_interval)
    return True


class ArloHub(object):
    """Representation of the base Arlo hub component."""

    def __init__(self, hub):
        """Initialize the entity."""
        self.hub = hub
