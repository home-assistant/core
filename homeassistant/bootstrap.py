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
import logging
from collections import defaultdict

import homeassistant
import homeassistant.loader as loader
import homeassistant.components as core_components


# pylint: disable=too-many-branches, too-many-statements
def from_config_dict(config, hass=None):
    """
    Tries to configure Home Assistant from a config dict.

    Dynamically loads required components and its dependencies.
    """
    if hass is None:
        hass = homeassistant.HomeAssistant()

    logger = logging.getLogger(__name__)

    loader.prepare(hass)

    # Make a copy because we are mutating it.
    # Convert it to defaultdict so components can always have config dict
    config = defaultdict(dict, config)

    # Filter out the repeating and common config section [homeassistant]
    components = (key for key in config.keys()
                  if ' ' not in key and key != homeassistant.DOMAIN)

    if not core_components.setup(hass, config):
        logger.error(("Home Assistant core failed to initialize. "
                      "Further initialization aborted."))

        return hass

    logger.info("Home Assistant core initialized")

    # Setup the components

    # We assume that all components that load before the group component loads
    # are components that poll devices. As their tasks are IO based, we will
    # add an extra worker for each of them.
    add_worker = True

    for domain in loader.load_order_components(components):
        component = loader.get_component(domain)

        try:
            if component.setup(hass, config):
                logger.info("component %s initialized", domain)

                add_worker = add_worker and domain != "group"

                if add_worker:
                    hass.pool.add_worker()

            else:
                logger.error("component %s failed to initialize", domain)

        except Exception:  # pylint: disable=broad-except
            logger.exception("Error during setup of component %s", domain)

    return hass


def from_config_file(config_path, hass=None, enable_logging=True):
    """
    Reads the configuration file and tries to start all the required
    functionality. Will add functionality to 'hass' parameter if given,
    instantiates a new Home Assistant object if 'hass' is not given.
    """
    if hass is None:
        hass = homeassistant.HomeAssistant()

        # Set config dir to directory holding config file
        hass.config_dir = os.path.abspath(os.path.dirname(config_path))

    if enable_logging:
        # Setup the logging for home assistant.
        logging.basicConfig(level=logging.INFO)

        # Log errors to a file if we have write access to file or config dir
        err_log_path = hass.get_config_path("home-assistant.log")
        err_path_exists = os.path.isfile(err_log_path)

        # Check if we can write to the error log if it exists or that
        # we can create files in the containgin directory if not.
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
            logging.getLogger(__name__).error(
                "Unable to setup error log %s (access denied)", err_log_path)

    # Read config
    config = configparser.ConfigParser()
    config.read(config_path)

    config_dict = {}

    for section in config.sections():
        config_dict[section] = {}

        for key, val in config.items(section):
            config_dict[section][key] = val

    return from_config_dict(config_dict, hass)
