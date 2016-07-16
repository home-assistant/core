"""Module to help with parsing and generating configuration files."""
import logging
import os
import shutil
from types import MappingProxyType

import voluptuous as vol

from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_TEMPERATURE_UNIT,
    CONF_TIME_ZONE, CONF_CUSTOMIZE, CONF_ELEVATION, TEMP_FAHRENHEIT,
    TEMP_CELSIUS, __version__)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.yaml import load_yaml
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import valid_entity_id, set_customize
from homeassistant.util import dt as date_util, location as loc_util

_LOGGER = logging.getLogger(__name__)

YAML_CONFIG_FILE = 'configuration.yaml'
VERSION_FILE = '.HA_VERSION'
CONFIG_DIR_NAME = '.homeassistant'

DEFAULT_CONFIG = (
    # Tuples (attribute, default, auto detect property, description)
    (CONF_NAME, 'Home', None, 'Name of the location where Home Assistant is '
     'running'),
    (CONF_LATITUDE, 0, 'latitude', 'Location required to calculate the time'
     ' the sun rises and sets'),
    (CONF_LONGITUDE, 0, 'longitude', None),
    (CONF_ELEVATION, 0, None, 'Impacts weather/sunrise data'),
    (CONF_TEMPERATURE_UNIT, 'C', None, 'C for Celsius, F for Fahrenheit'),
    (CONF_TIME_ZONE, 'UTC', 'time_zone', 'Pick yours from here: http://en.wiki'
     'pedia.org/wiki/List_of_tz_database_time_zones'),
)
DEFAULT_COMPONENTS = {
    'introduction:': 'Show links to resources in log and frontend',
    'frontend:': 'Enables the frontend',
    'updater:': 'Checks for available updates',
    'discovery:': 'Discover some devices automatically',
    'conversation:': 'Allows you to issue voice commands from the frontend',
    'history:': 'Enables support for tracking state changes over time.',
    'logbook:': 'View all events in a logbook',
    'sun:': 'Track the sun',
    'sensor:\n   platform: yr': 'Weather Prediction',
}


def _valid_customize(value):
    """Config validator for customize."""
    if not isinstance(value, dict):
        raise vol.Invalid('Expected dictionary')

    for key, val in value.items():
        if not valid_entity_id(key):
            raise vol.Invalid('Invalid entity ID: {}'.format(key))

        if not isinstance(val, dict):
            raise vol.Invalid('Value of {} is not a dictionary'.format(key))

    return value

CORE_CONFIG_SCHEMA = vol.Schema({
    CONF_NAME: vol.Coerce(str),
    CONF_LATITUDE: cv.latitude,
    CONF_LONGITUDE: cv.longitude,
    CONF_ELEVATION: vol.Coerce(int),
    CONF_TEMPERATURE_UNIT: cv.temperature_unit,
    CONF_TIME_ZONE: cv.time_zone,
    vol.Required(CONF_CUSTOMIZE,
                 default=MappingProxyType({})): _valid_customize,
})


def get_default_config_dir():
    """Put together the default configuration directory based on OS."""
    data_dir = os.getenv('APPDATA') if os.name == "nt" \
        else os.path.expanduser('~')
    return os.path.join(data_dir, CONFIG_DIR_NAME)


def ensure_config_exists(config_dir, detect_location=True):
    """Ensure a config file exists in given configuration directory.

    Creating a default one if needed.
    Return path to the config file.
    """
    config_path = find_config_file(config_dir)

    if config_path is None:
        print("Unable to find configuration. Creating default one in",
              config_dir)
        config_path = create_default_config(config_dir, detect_location)

    return config_path


def create_default_config(config_dir, detect_location=True):
    """Create a default configuration file in given configuration directory.

    Return path to new config file if success, None if failed.
    """
    config_path = os.path.join(config_dir, YAML_CONFIG_FILE)
    version_path = os.path.join(config_dir, VERSION_FILE)

    info = {attr: default for attr, default, _, _ in DEFAULT_CONFIG}

    location_info = detect_location and loc_util.detect_location_info()

    if location_info:
        if location_info.use_fahrenheit:
            info[CONF_TEMPERATURE_UNIT] = 'F'

        for attr, default, prop, _ in DEFAULT_CONFIG:
            if prop is None:
                continue
            info[attr] = getattr(location_info, prop) or default

        if location_info.latitude and location_info.longitude:
            info[CONF_ELEVATION] = loc_util.elevation(location_info.latitude,
                                                      location_info.longitude)

    # Writing files with YAML does not create the most human readable results
    # So we're hard coding a YAML template.
    try:
        with open(config_path, 'w') as config_file:
            config_file.write("homeassistant:\n")

            for attr, _, _, description in DEFAULT_CONFIG:
                if info[attr] is None:
                    continue
                elif description:
                    config_file.write("  # {}\n".format(description))
                config_file.write("  {}: {}\n".format(attr, info[attr]))

            config_file.write("\n")

            for component, description in DEFAULT_COMPONENTS.items():
                config_file.write("# {}\n".format(description))
                config_file.write("{}\n\n".format(component))

        with open(version_path, 'wt') as version_file:
            version_file.write(__version__)

        return config_path

    except IOError:
        print('Unable to create default configuration file', config_path)
        return None


def find_config_file(config_dir):
    """Look in given directory for supported configuration files."""
    config_path = os.path.join(config_dir, YAML_CONFIG_FILE)

    return config_path if os.path.isfile(config_path) else None


def load_yaml_config_file(config_path):
    """Parse a YAML configuration file."""
    conf_dict = load_yaml(config_path)

    if not isinstance(conf_dict, dict):
        msg = 'The configuration file {} does not contain a dictionary'.format(
            os.path.basename(config_path))
        _LOGGER.error(msg)
        raise HomeAssistantError(msg)

    return conf_dict


def process_ha_config_upgrade(hass):
    """Upgrade config if necessary."""
    version_path = hass.config.path(VERSION_FILE)

    try:
        with open(version_path, 'rt') as inp:
            conf_version = inp.readline().strip()
    except FileNotFoundError:
        # Last version to not have this file
        conf_version = '0.7.7'

    if conf_version == __version__:
        return

    _LOGGER.info('Upgrading config directory from %s to %s', conf_version,
                 __version__)

    lib_path = hass.config.path('deps')
    if os.path.isdir(lib_path):
        shutil.rmtree(lib_path)

    with open(version_path, 'wt') as outp:
        outp.write(__version__)


def process_ha_core_config(hass, config):
    """Process the [homeassistant] section from the config."""
    # pylint: disable=too-many-branches
    config = CORE_CONFIG_SCHEMA(config)
    hac = hass.config

    def set_time_zone(time_zone_str):
        """Helper method to set time zone."""
        if time_zone_str is None:
            return

        time_zone = date_util.get_time_zone(time_zone_str)

        if time_zone:
            hac.time_zone = time_zone
            date_util.set_default_time_zone(time_zone)
        else:
            _LOGGER.error('Received invalid time zone %s', time_zone_str)

    for key, attr in ((CONF_LATITUDE, 'latitude'),
                      (CONF_LONGITUDE, 'longitude'),
                      (CONF_NAME, 'location_name'),
                      (CONF_ELEVATION, 'elevation')):
        if key in config:
            setattr(hac, attr, config[key])

    if CONF_TIME_ZONE in config:
        set_time_zone(config.get(CONF_TIME_ZONE))

    set_customize(config.get(CONF_CUSTOMIZE) or {})

    if CONF_TEMPERATURE_UNIT in config:
        hac.temperature_unit = config[CONF_TEMPERATURE_UNIT]

    # Shortcut if no auto-detection necessary
    if None not in (hac.latitude, hac.longitude, hac.temperature_unit,
                    hac.time_zone, hac.elevation):
        return

    discovered = []

    # If we miss some of the needed values, auto detect them
    if None in (hac.latitude, hac.longitude, hac.temperature_unit,
                hac.time_zone):
        info = loc_util.detect_location_info()

        if info is None:
            _LOGGER.error('Could not detect location information')
            return

        if hac.latitude is None and hac.longitude is None:
            hac.latitude = info.latitude
            hac.longitude = info.longitude
            discovered.append(('latitude', hac.latitude))
            discovered.append(('longitude', hac.longitude))

        if hac.temperature_unit is None:
            if info.use_fahrenheit:
                hac.temperature_unit = TEMP_FAHRENHEIT
                discovered.append(('temperature_unit', 'F'))
            else:
                hac.temperature_unit = TEMP_CELSIUS
                discovered.append(('temperature_unit', 'C'))

        if hac.location_name is None:
            hac.location_name = info.city
            discovered.append(('name', info.city))

        if hac.time_zone is None:
            set_time_zone(info.time_zone)
            discovered.append(('time_zone', info.time_zone))

    if hac.elevation is None and hac.latitude is not None and \
       hac.longitude is not None:
        elevation = loc_util.elevation(hac.latitude, hac.longitude)
        hac.elevation = elevation
        discovered.append(('elevation', elevation))

    if discovered:
        _LOGGER.warning(
            'Incomplete core config. Auto detected %s',
            ', '.join('{}: {}'.format(key, val) for key, val in discovered))
