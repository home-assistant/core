"""
homeassistant.config
~~~~~~~~~~~~~~~~~~~~

Module to help with parsing and generating configuration files.
"""
import logging
import os

from homeassistant import HomeAssistantError
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_TEMPERATURE_UNIT, CONF_NAME,
    CONF_TIME_ZONE)
import homeassistant.util.location as loc_util


_LOGGER = logging.getLogger(__name__)


YAML_CONFIG_FILE = 'configuration.yaml'
CONF_CONFIG_FILE = 'home-assistant.conf'

DEFAULT_CONFIG = [
    # Tuples (attribute, default, auto detect property, description)
    (CONF_NAME, 'Home', None, 'Name of the location where Home Assistant is '
     'running'),
    (CONF_LATITUDE, None, 'latitude', 'Location required to calculate the time'
     ' the sun rises and sets'),
    (CONF_LONGITUDE, None, 'longitude', None),
    (CONF_TEMPERATURE_UNIT, 'C', None, 'C for Celcius, F for Fahrenheit'),
    (CONF_TIME_ZONE, 'UTC', 'time_zone', 'Pick yours from here: http://en.wiki'
     'pedia.org/wiki/List_of_tz_database_time_zones'),
]
DEFAULT_COMPONENTS = [
    'discovery', 'frontend', 'conversation', 'history', 'logbook', 'sun']


def ensure_config_exists(config_dir, detect_location=True):
    """ Ensures a config file exists in given config dir.
        Creating a default one if needed.
        Returns path to the config file. """
    config_path = find_config_file(config_dir)

    if config_path is None:
        _LOGGER.info("Unable to find configuration. Creating default one")
        config_path = create_default_config(config_dir, detect_location)

    return config_path


def create_default_config(config_dir, detect_location=True):
    """ Creates a default configuration file in given config dir.
        Returns path to new config file if success, None if failed. """
    config_path = os.path.join(config_dir, YAML_CONFIG_FILE)

    info = {attr: default for attr, default, *_ in DEFAULT_CONFIG}

    location_info = detect_location and loc_util.detect_location_info()

    if location_info:
        if location_info.use_fahrenheit:
            info[CONF_TEMPERATURE_UNIT] = 'F'

        for attr, default, prop, _ in DEFAULT_CONFIG:
            if prop is None:
                continue
            info[attr] = getattr(location_info, prop) or default

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

            for component in DEFAULT_COMPONENTS:
                config_file.write("{}:\n\n".format(component))

        return config_path

    except IOError:
        _LOGGER.exception(
            'Unable to write default configuration file %s', config_path)

        return None


def find_config_file(config_dir):
    """ Looks in given directory for supported config files. """
    for filename in (YAML_CONFIG_FILE, CONF_CONFIG_FILE):
        config_path = os.path.join(config_dir, filename)

        if os.path.isfile(config_path):
            return config_path

    return None


def load_config_file(config_path):
    """ Loads given config file. """
    config_ext = os.path.splitext(config_path)[1]

    if config_ext == '.yaml':
        return load_yaml_config_file(config_path)

    elif config_ext == '.conf':
        return load_conf_config_file(config_path)


def load_yaml_config_file(config_path):
    """ Parse a YAML configuration file. """
    import yaml

    def parse(fname):
        """ Parse a YAML file.  """
        try:
            with open(fname) as conf_file:
                # If configuration file is empty YAML returns None
                # We convert that to an empty dict
                return yaml.load(conf_file) or {}
        except yaml.YAMLError:
            error = 'Error reading YAML configuration file {}'.format(fname)
            _LOGGER.exception(error)
            raise HomeAssistantError(error)

    def yaml_include(loader, node):
        """
        Loads another YAML file and embeds it using the !include tag.

        Example:
            device_tracker: !include device_tracker.yaml
        """
        fname = os.path.join(os.path.dirname(loader.name), node.value)
        return parse(fname)

    yaml.add_constructor('!include', yaml_include)

    conf_dict = parse(config_path)

    if not isinstance(conf_dict, dict):
        _LOGGER.error(
            'The configuration file %s does not contain a dictionary',
            os.path.basename(config_path))
        raise HomeAssistantError()

    return conf_dict


def load_conf_config_file(config_path):
    """ Parse the old style conf configuration. """
    import configparser

    config_dict = {}

    config = configparser.ConfigParser()
    config.read(config_path)

    for section in config.sections():
        config_dict[section] = {}

        for key, val in config.items(section):
            config_dict[section][key] = val

    return config_dict
