"""
Support for Neato botvac connected vacuum cleaners.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/neato/
"""
import logging
from datetime import timedelta
from urllib.error import HTTPError

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import discovery
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pybotvac==0.0.10']

DOMAIN = 'neato'
NEATO_ROBOTS = 'neato_robots'
NEATO_LOGIN = 'neato_login'
NEATO_MAP_DATA = 'neato_map_data'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

STATES = {
    1: 'Idle',
    2: 'Busy',
    3: 'Pause',
    4: 'Error'
}

MODE = {
    1: 'Eco',
    2: 'Turbo'
}

ACTION = {
    0: 'No action',
    1: 'House cleaning',
    2: 'Spot cleaning',
    3: 'Manual cleaning',
    4: 'Docking',
    5: 'User menu active',
    6: 'Cleaning cancelled',
    7: 'Updating...',
    8: 'Copying logs...',
    9: 'Calculating position...',
    10: 'IEC test',
    11: 'Map cleaning',
    12: 'Exploring map (creating a persistent map)',
    13: 'Acquiring Persistent Map IDs',
    14: 'Creating & Uploading Map',
    15: 'Suspended Exploration'
}

ERRORS = {
    'ui_error_brush_stuck': 'Brush stuck',
    'ui_error_brush_overloaded': 'Brush overloaded',
    'ui_error_bumper_stuck': 'Bumper stuck',
    'ui_error_dust_bin_missing': 'Dust bin missing',
    'ui_error_dust_bin_full': 'Dust bin full',
    'ui_error_dust_bin_emptied': 'Dust bin emptied',
    'ui_error_navigation_backdrop_leftbump': 'Clear my path',
    'ui_error_navigation_noprogress': 'Clear my path',
    'ui_error_navigation_origin_unclean': 'Clear my path',
    'ui_error_navigation_pathproblems_returninghome': 'Cannot return to base',
    'ui_error_navigation_falling': 'Clear my path',
    'ui_error_picked_up': 'Picked up',
    'ui_error_stuck': 'Stuck!',
    'dustbin_full': 'Dust bin full',
    'dustbin_missing': 'Dust bin missing',
    'maint_brush_stuck': 'Brush stuck',
    'maint_brush_overload': 'Brush overloaded',
    'maint_bumper_stuck': 'Bumper stuck',
    'maint_vacuum_stuck': 'Vacuum is stuck',
    'maint_left_drop_stuck': 'Vacuum is stuck',
    'maint_left_wheel_stuck': 'Vacuum is stuck',
    'maint_right_drop_stuck': 'Vacuum is stuck',
    'maint_right_wheel_stuck': 'Vacuum is stuck',
    'not_on_charge_base': 'Not on the charge base',
    'nav_robot_falling': 'Clear my path',
    'nav_no_path': 'Clear my path',
    'nav_path_problem': 'Clear my path'
}

ALERTS = {
    'ui_alert_dust_bin_full': 'Please empty dust bin',
    'ui_alert_recovering_location': 'Returning to start',
    'dustbin_full': 'Please empty dust bin',
    'maint_brush_change': 'Change the brush',
    'maint_filter_change': 'Change the filter',
    'clean_completed_to_start': 'Cleaning completed'
}


def setup(hass, config):
    """Set up the Neato component."""
    from pybotvac import Account

    hass.data[NEATO_LOGIN] = NeatoHub(hass, config[DOMAIN], Account)
    hub = hass.data[NEATO_LOGIN]
    if not hub.login():
        _LOGGER.debug("Failed to login to Neato API")
        return False
    hub.update_robots()
    for component in ('camera', 'vacuum', 'switch'):
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


class NeatoHub:
    """A My Neato hub wrapper class."""

    def __init__(self, hass, domain_config, neato):
        """Initialize the Neato hub."""
        self.config = domain_config
        self._neato = neato
        self._hass = hass

        self.my_neato = neato(
            domain_config[CONF_USERNAME],
            domain_config[CONF_PASSWORD])
        self._hass.data[NEATO_ROBOTS] = self.my_neato.robots
        self._hass.data[NEATO_MAP_DATA] = self.my_neato.maps

    def login(self):
        """Login to My Neato."""
        try:
            _LOGGER.debug("Trying to connect to Neato API")
            self.my_neato = self._neato(
                self.config[CONF_USERNAME], self.config[CONF_PASSWORD])
            return True
        except HTTPError:
            _LOGGER.error("Unable to connect to Neato API")
            return False

    @Throttle(timedelta(seconds=300))
    def update_robots(self):
        """Update the robot states."""
        _LOGGER.debug("Running HUB.update_robots %s",
                      self._hass.data[NEATO_ROBOTS])
        self._hass.data[NEATO_ROBOTS] = self.my_neato.robots
        self._hass.data[NEATO_MAP_DATA] = self.my_neato.maps

    def download_map(self, url):
        """Download a new map image."""
        map_image_data = self.my_neato.get_map_image(url)
        return map_image_data
