"""
homeassistant.bootstrap
~~~~~~~~~~~~~~~~~~~~~~~
Provides methods to bootstrap a home assistant instance.

Each method will return a tuple (bus, statemachine).

After bootstrapping you can add your own components or
start by calling homeassistant.start_home_assistant(bus)
"""

import os
import logging
from collections import defaultdict

import homeassistant
import homeassistant.util as util
import homeassistant.util.dt as date_util
import homeassistant.config as config_util
import homeassistant.loader as loader
import homeassistant.components as core_components
import homeassistant.components.group as group
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    EVENT_COMPONENT_LOADED, CONF_LATITUDE, CONF_LONGITUDE,
    CONF_TEMPERATURE_UNIT, CONF_NAME, CONF_TIME_ZONE, CONF_CUSTOMIZE,
    TEMP_CELCIUS, TEMP_FAHRENHEIT)

_LOGGER = logging.getLogger(__name__)

ATTR_COMPONENT = "component"


def setup_component(hass, domain, config=None):
    """ Setup a component and all its dependencies. """

    if domain in hass.config.components:
        return True

    _ensure_loader_prepared(hass)

    if config is None:
        config = defaultdict(dict)

    components = loader.load_order_component(domain)

    # OrderedSet is empty if component or dependencies could not be resolved
    if not components:
        return False

    for component in components:
        if component in hass.config.components:
            continue

        if not _setup_component(hass, component, config):
            return False

    return True


def _setup_component(hass, domain, config):
    """ Setup a component for Home Assistant. """
    component = loader.get_component(domain)

    missing_deps = [dep for dep in component.DEPENDENCIES
                    if dep not in hass.config.components]

    if missing_deps:
        _LOGGER.error(
            "Not initializing %s because not all dependencies loaded: %s",
            domain, ", ".join(missing_deps))

        return False

    try:
        if component.setup(hass, config):
            hass.config.components.append(component.DOMAIN)

            # Assumption: if a component does not depend on groups
            # it communicates with devices
            if group.DOMAIN not in component.DEPENDENCIES:
                hass.pool.add_worker()

            hass.bus.fire(
                EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: component.DOMAIN})

            return True

        else:
            _LOGGER.error("component %s failed to initialize", domain)

    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Error during setup of component %s", domain)

    return False


# pylint: disable=too-many-branches, too-many-statements
def from_config_dict(config, hass=None):
    """
    Tries to configure Home Assistant from a config dict.

    Dynamically loads required components and its dependencies.
    """
    if hass is None:
        hass = homeassistant.HomeAssistant()

    process_ha_core_config(hass, config.get(homeassistant.DOMAIN, {}))

    enable_logging(hass)

    _ensure_loader_prepared(hass)

    # Make a copy because we are mutating it.
    # Convert it to defaultdict so components can always have config dict
    # Convert values to dictionaries if they are None
    config = defaultdict(
        dict, {key: value or {} for key, value in config.items()})

    # Filter out the repeating and common config section [homeassistant]
    components = (key for key in config.keys()
                  if ' ' not in key and key != homeassistant.DOMAIN)

    if not core_components.setup(hass, config):
        _LOGGER.error("Home Assistant core failed to initialize. "
                      "Further initialization aborted.")

        return hass

    _LOGGER.info("Home Assistant core initialized")

    # Setup the components
    for domain in loader.load_order_components(components):
        _setup_component(hass, domain, config)

    return hass


def from_config_file(config_path, hass=None):
    """
    Reads the configuration file and tries to start all the required
    functionality. Will add functionality to 'hass' parameter if given,
    instantiates a new Home Assistant object if 'hass' is not given.
    """
    if hass is None:
        hass = homeassistant.HomeAssistant()

    # Set config dir to directory holding config file
    hass.config.config_dir = os.path.abspath(os.path.dirname(config_path))

    config_dict = config_util.load_config_file(config_path)

    return from_config_dict(config_dict, hass)


def enable_logging(hass):
    """ Setup the logging for home assistant. """
    logging.basicConfig(level=logging.INFO)

    # Log errors to a file if we have write access to file or config dir
    err_log_path = hass.config.path("home-assistant.log")
    err_path_exists = os.path.isfile(err_log_path)

    # Check if we can write to the error log if it exists or that
    # we can create files in the containing directory if not.
    if (err_path_exists and os.access(err_log_path, os.W_OK)) or \
       (not err_path_exists and os.access(hass.config.config_dir, os.W_OK)):

        err_handler = logging.FileHandler(
            err_log_path, mode='w', delay=True)

        err_handler.setLevel(logging.WARNING)
        err_handler.setFormatter(
            logging.Formatter('%(asctime)s %(name)s: %(message)s',
                              datefmt='%H:%M %d-%m-%y'))
        logging.getLogger('').addHandler(err_handler)

    else:
        _LOGGER.error(
            "Unable to setup error log %s (access denied)", err_log_path)


def process_ha_core_config(hass, config):
    """ Processes the [homeassistant] section from the config. """
    hac = hass.config

    def set_time_zone(time_zone_str):
        """ Helper method to set time zone in HA. """
        if time_zone_str is None:
            return

        time_zone = date_util.get_time_zone(time_zone_str)

        if time_zone:
            hac.time_zone = time_zone
            date_util.set_default_time_zone(time_zone)
        else:
            _LOGGER.error("Received invalid time zone %s", time_zone_str)

    for key, attr in ((CONF_LATITUDE, 'latitude'),
                      (CONF_LONGITUDE, 'longitude'),
                      (CONF_NAME, 'location_name')):
        if key in config:
            setattr(hac, attr, config[key])

    set_time_zone(config.get(CONF_TIME_ZONE))

    for entity_id, attrs in config.get(CONF_CUSTOMIZE, {}).items():
        Entity.overwrite_attribute(entity_id, attrs.keys(), attrs.values())

    if CONF_TEMPERATURE_UNIT in config:
        unit = config[CONF_TEMPERATURE_UNIT]

        if unit == 'C':
            hac.temperature_unit = TEMP_CELCIUS
        elif unit == 'F':
            hac.temperature_unit = TEMP_FAHRENHEIT

    # If we miss some of the needed values, auto detect them
    if None not in (
            hac.latitude, hac.longitude, hac.temperature_unit, hac.time_zone):
        return

    _LOGGER.info('Auto detecting location and temperature unit')

    info = util.detect_location_info()

    if info is None:
        _LOGGER.error('Could not detect location information')
        return

    if hac.latitude is None and hac.longitude is None:
        hac.latitude = info.latitude
        hac.longitude = info.longitude

    if hac.temperature_unit is None:
        if info.use_fahrenheit:
            hac.temperature_unit = TEMP_FAHRENHEIT
        else:
            hac.temperature_unit = TEMP_CELCIUS

    if hac.location_name is None:
        hac.location_name = info.city

    if hac.time_zone is None:
        set_time_zone(info.time_zone)


def _ensure_loader_prepared(hass):
    """ Ensure Home Assistant loader is prepared. """
    if not loader.PREPARED:
        loader.prepare(hass)
