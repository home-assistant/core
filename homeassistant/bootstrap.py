"""
homeassistant.bootstrap
~~~~~~~~~~~~~~~~~~~~~~~
Provides methods to bootstrap a home assistant instance.

Each method will return a tuple (bus, statemachine).

After bootstrapping you can add your own components or
start by calling homeassistant.start_home_assistant(bus)
"""

import os
import configparser
import yaml
import io
import logging
from collections import defaultdict

import homeassistant
import homeassistant.loader as loader
import homeassistant.components as core_components
import homeassistant.components.group as group
from homeassistant.const import EVENT_COMPONENT_LOADED

_LOGGER = logging.getLogger(__name__)

ATTR_COMPONENT = "component"


def setup_component(hass, domain, config=None):
    """ Setup a component for Home Assistant. """
    # Check if already loaded
    if domain in hass.components:
        return

    _ensure_loader_prepared(hass)

    if config is None:
        config = defaultdict(dict)

    component = loader.get_component(domain)

    try:
        if component.setup(hass, config):
            hass.components.append(component.DOMAIN)

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
        setup_component(hass, domain, config)

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
        hass.config_dir = os.path.abspath(os.path.dirname(config_path))

    config_dict = {}
    # check config file type
    if os.path.splitext(config_path)[1] == '.yaml':
        # Read yaml
        config_dict = yaml.load(io.open(config_path, 'r'))
    else:
        # Read config
        config = configparser.ConfigParser()
        config.read(config_path)

        for section in config.sections():
            config_dict[section] = {}

            for key, val in config.items(section):
                config_dict[section][key] = val

    return from_config_dict(config_dict, hass)


def enable_logging(hass):
    """ Setup the logging for home assistant. """
    logging.basicConfig(level=logging.INFO)

    # Log errors to a file if we have write access to file or config dir
    err_log_path = hass.get_config_path("home-assistant.log")
    err_path_exists = os.path.isfile(err_log_path)

    # Check if we can write to the error log if it exists or that
    # we can create files in the containing directory if not.
    if (err_path_exists and os.access(err_log_path, os.W_OK)) or \
       (not err_path_exists and os.access(hass.config_dir, os.W_OK)):

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


def _ensure_loader_prepared(hass):
    """ Ensure Home Assistant loader is prepared. """
    if not loader.PREPARED:
        loader.prepare(hass)
