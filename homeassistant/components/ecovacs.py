"""Parent component for Ecovacs Deebot vacuums.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/ecovacs/
"""

import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_TIMEOUT, \
    CONF_DEVICES, EVENT_HOMEASSISTANT_STOP

REQUIREMENTS = ['sucks==0.8.1']

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ecovacs"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DEVICES, default=[]):
            vol.All(cv.ensure_list, [dict]),
    })
}, extra=vol.ALLOW_EXTRA)

ECOVACS_DEVICES = "ecovacs_devices"
# TODO: const or generated?
ECOVACS_API_DEVICEID = "6d6ce034ef01ae6c66b21729ffa3b23e"

def setup(hass, config):
    """Set up the Ecovacs component."""
    _LOGGER.info("Creating new Ecovacs component")

    if ECOVACS_DEVICES not in hass.data:
        hass.data[ECOVACS_DEVICES] = []

    from sucks import EcoVacsAPI, VacBot

    # Convenient hack for debugging to pipe sucks logging to the Hass logger
    import sucks
    sucks.logging = _LOGGER

    ecovacs_api = EcoVacsAPI(ECOVACS_API_DEVICEID,
                             config[DOMAIN].get(CONF_USERNAME),
                             EcoVacsAPI.md5(config[DOMAIN].get(CONF_PASSWORD)),
                             'us', #TODO: Make configurable
                             'na') #TODO: Make configurable

    devices = ecovacs_api.devices()
    _LOGGER.debug("Ecobot devices: %s", devices)

    for device in devices:
        _LOGGER.info("Discovered Ecovacs device on account: %s",
                     device['nick'])
        vacbot = VacBot(ecovacs_api.uid,
                        ecovacs_api.REALM,
                        ecovacs_api.resource,
                        ecovacs_api.user_access_token,
                        device,
                        'na') #TODO: Make configurable
        hass.data[ECOVACS_DEVICES].append(vacbot)

    # pylint: disable=unused-argument
    def stop(event: object) -> None:
        for device in hass.data[ECOVACS_DEVICES]:
            _LOGGER.info("Shutting down connection to Ecovacs device %s",
                         device.vacuum['nick'])
            device.disconnect()

    # Listen for HA stop to disconnect.
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop)

    if hass.data[ECOVACS_DEVICES]:
        _LOGGER.debug("Starting vacuum components")
        # discovery.load_platform(hass, "sensor", DOMAIN, {}, config)
        discovery.load_platform(hass, "vacuum", DOMAIN, {}, config)

    return True
