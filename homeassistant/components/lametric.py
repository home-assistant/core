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
    try:
        conf = config[DOMAIN]
        lmn = HassLaMetricManager(client_id=conf[CONF_CLIENT_ID],
                                  client_secret=conf[CONF_CLIENT_SECRET])
        devices = HassLaMetricManager.manager().get_devices()
    except Exception as exception:
        _LOGGER.error("Could not setup LaMetric platform: %s", exception)
        return False

    found = False
    hass.data[DOMAIN] = lmn
    hass.data[LAMETRIC_DEVICES] = []
    for dev in devices:
        _LOGGER.debug("Discovered LaMetric device: %s", dev)
        hass.data[LAMETRIC_DEVICES].append(dev)
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
        HassLaMetricManager.lmn = LaMetricManager(client_id, client_secret)
        HassLaMetricManager._client_id = client_id
        HassLaMetricManager._client_secret = client_secret

    @classmethod
    def reconnect(cls):
        """
        Reconnect to LaMetric.

        This is usually necessary when the OAuth token is expired.
        """
        from lmnotify import LaMetricManager
        _LOGGER.debug("Reconnecting to LaMetric")
        HassLaMetricManager.lmn = \
            LaMetricManager(HassLaMetricManager._client_id,
                            HassLaMetricManager._client_secret)

    @classmethod
    def manager(cls):
        """Return the global LaMetricManager instance."""
        return cls.lmn
