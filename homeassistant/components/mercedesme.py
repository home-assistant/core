"""
Support for MercedesME System.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mercedesme/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL)
from homeassistant.helpers import discovery

REQUIREMENTS = ['mercedesmejsonpy==0.1.1']

_LOGGER = logging.getLogger(__name__)

DATA_MME = 'mercedesme'
DOMAIN = 'mercedesme'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=30):
            vol.All(cv.positive_int, vol.Clamp(min=10))
    })
}, extra=vol.ALLOW_EXTRA)

NOTIFICATION_ID = 'mercedesme_integration_notification'
NOTIFICATION_TITLE = 'Mercedes me integration setup'


def setup(hass, config):
    """Set up MercedesMe System."""
    from mercedesmejsonpy import controller as mbmeAPI
    from mercedesmejsonpy import Exceptions as mbmeExc

    try:
        hass.data[DATA_MME] = {
            'controller': mbmeAPI.Controller(
                config[DATA_MME][CONF_USERNAME],
                config[DATA_MME][CONF_PASSWORD],
                config[DATA_MME][CONF_SCAN_INTERVAL])
        }
    except mbmeExc.MercedesMeException as ex:
        if ex.code == 401:
            hass.components.persistent_notification.create(
                "Error:<br />Please check username and password."
                "You will need to restart Home Assistant after fixing.",
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)
        else:
            hass.components.persistent_notification.create(
                "Error:<br />Can't communicate with Mercedes me API.<br />"
                "Error code: {} Reason: {}"
                "You will need to restart Home Assistant after fixing."
                "".format(ex.code, ex.message),
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)

        _LOGGER.error("Unable to communicate with Mercedes me API: %s",
                      ex.message)
        return False

    if hass.data[DATA_MME]["controller"].is_valid_session:
        discovery.load_platform(hass, 'sensor', DATA_MME, {}, config)
        discovery.load_platform(hass, 'device_tracker', DATA_MME, {}, config)
        discovery.load_platform(hass, 'binary_sensor', DATA_MME, {}, config)
        return True

    return False
