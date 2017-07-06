"""
Support for LaMetric time.

This is the base platform to support LaMetric components:
Notify, Light, Mediaplayer

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/lametric/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['lmnotify==0.0.4']

_LOGGER = logging.getLogger(__name__)

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'

DOMAIN = 'lametric'
LAMETRIC_DEVICES = 'LAMETRIC_DEVICES'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


# pylint: disable=broad-except
def setup(hass, config):
    """Set up the LaMetricManager."""
    _LOGGER.debug("Setting up LaMetric platform")
    conf = config[DOMAIN]
    hlmn = HassLaMetricManager(client_id=conf[CONF_CLIENT_ID],
                               client_secret=conf[CONF_CLIENT_SECRET])
    devices = hlmn.manager().get_devices()

    found = False
    hass.data[DOMAIN] = hlmn
    for dev in devices:
        _LOGGER.debug("Discovered LaMetric device: %s", dev)
        found = True

    return found


class HassLaMetricManager():
    """
    A class that encapsulated requests to the LaMetric manager.

    As the original class does not have a re-connect feature that is needed
    for applications running for a long time as the OAuth tokens expire. This
    class implements this reconnect() feature.
    """

    def __init__(self, client_id, client_secret):
        """Initialize HassLaMetricManager and connect to LaMetric."""
        from lmnotify import LaMetricManager

        _LOGGER.debug("Connecting to LaMetric")
        self.lmn = LaMetricManager(client_id, client_secret)
        self._client_id = client_id
        self._client_secret = client_secret

    def reconnect(self):
        """
        Reconnect to LaMetric.

        This is usually necessary when the OAuth token is expired.
        """
        from lmnotify import LaMetricManager
        _LOGGER.debug("Reconnecting to LaMetric")
        self.lmn = LaMetricManager(self._client_id,
                                   self._client_secret)

    def manager(self):
        """Return the global LaMetricManager instance."""
        return self.lmn
