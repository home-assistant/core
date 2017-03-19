"""
Component for interacting with a Lutron Caseta system.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/lutron_caseta/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_HOST,
                                 CONF_USERNAME,
                                 CONF_PASSWORD)
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['https://github.com/gurumitts/'
                'pylutron-caseta/archive/v0.2.0.zip#'
                'pylutron-caseta==v0.2.0', 'paramiko==2.1.2']

_LOGGER = logging.getLogger(__name__)

LUTRON_CASETA_SMARTBRIDGE = 'lutron_smartbridge'
LUTRON_CASETA_DEVICES = 'lutron_devices'

DOMAIN = 'lutron_caseta'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, base_config):
    """Setup the Lutron component."""
    from pylutron_caseta.smartbridge import Smartbridge

    hass.data[LUTRON_CASETA_SMARTBRIDGE] = None
    hass.data[LUTRON_CASETA_DEVICES] = None

    config = base_config.get(DOMAIN)

    hass.data[LUTRON_CASETA_SMARTBRIDGE] = Smartbridge(
        hostname=config[CONF_HOST],
        username=config[CONF_USERNAME],
        password=config[CONF_PASSWORD]
    )
    _LOGGER.debug("Connected to Lutron smartbridge at %s",
                  config[CONF_HOST])
    caseta_devices = hass.data[LUTRON_CASETA_SMARTBRIDGE].get_devices()

    # WallDimmer will be home-assistant lights
    # WallSwitch switches should be trivial to add
    components = {"light": [], "switch": []}

    for device_id in caseta_devices:
        if caseta_devices[device_id]["type"] == "WallDimmer":
            components["light"].append(caseta_devices[device_id])
        if caseta_devices[device_id]["type"] == "WallSwitch":
            components["switch"].append(caseta_devices[device_id])
        # More Lutron devices can be added here

    hass.data[LUTRON_CASETA_DEVICES] = components
    _LOGGER.debug(hass.data[LUTRON_CASETA_DEVICES])

    for component in components:
        if len(components[component]) > 0:
            discovery.load_platform(hass, component,
                                    DOMAIN, None, base_config)
    return True


class LutronCasetaDevice(Entity):
    """Common base class for all Caseta devices."""

    def __init__(self, device, bridge):
        """Set up the base class.

        [:param]device the device metadata
        [:param]bridge the smartbridge object
        """
        self._prev_brightness = None
        self._device_id = device["device_id"]
        self._device_type = device["type"]
        self._device_name = device["name"]
        self._state = None
        self._smartbridge = bridge
        self._smartbridge.add_subscriber(self._device_id,
                                         self._update_callback)
        self.update()

    def _update_callback(self):
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        return self._device_name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        attr['Lutron Integration ID'] = self._device_id
        return attr
