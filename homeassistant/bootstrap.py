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
from itertools import chain

import homeassistant
import homeassistant.loader as loader
import homeassistant.components as core_components
import homeassistant.components.group as group


# pylint: disable=too-many-branches, too-many-statements
def from_config_dict(config, hass=None):
    """
    Tries to configure Home Assistant from a config dict.

    Dynamically loads required components and its dependencies.
    """
    if hass is None:
        hass = homeassistant.HomeAssistant()

    logger = logging.getLogger(__name__)

    # Make a copy because we are mutating it.
    # Convert it to defaultdict so components can always have config dict
    config = defaultdict(dict, config)

    # List of loaded components
    components = {}

    # List of components to validate
    to_validate = []

    # List of validated components
    validated = []

    # List of components we are going to load
    to_load = [key for key in config.keys() if key != homeassistant.DOMAIN]

    loader.prepare(hass)

    # Load required components
    while to_load:
        domain = to_load.pop()

        component = loader.get_component(domain)

        # if None it does not exist, error already thrown by get_component
        if component is not None:
            components[domain] = component

            # Special treatment for GROUP, we want to load it as late as
            # possible. We do this by loading it if all other to be loaded
            # modules depend on it.
            if component.DOMAIN == group.DOMAIN:
                pass

            # Components with no dependencies are valid
            elif not component.DEPENDENCIES:
                validated.append(domain)

            # If dependencies we'll validate it later
            else:
                to_validate.append(domain)

                # Make sure to load all dependencies that are not being loaded
                for dependency in component.DEPENDENCIES:
                    if dependency not in chain(components.keys(), to_load):
                        to_load.append(dependency)

    # Validate dependencies
    group_added = False

    while to_validate:
        newly_validated = []

        for domain in to_validate:
            if all(domain in validated for domain
                   in components[domain].DEPENDENCIES):

                newly_validated.append(domain)

        # We validated new domains this iteration, add them to validated
        if newly_validated:

            # Add newly validated domains to validated
            validated.extend(newly_validated)

            # remove domains from to_validate
            for domain in newly_validated:
                to_validate.remove(domain)

            newly_validated.clear()

        # Nothing validated this iteration. Add group dependency and try again.
        elif not group_added:
            group_added = True
            validated.append(group.DOMAIN)

        # Group has already been added and we still can't validate all.
        # Report missing deps as error and skip loading of these domains
        else:
            for domain in to_validate:
                missing_deps = [dep for dep in components[domain].DEPENDENCIES
                                if dep not in validated]

                logger.error(
                    "Could not validate all dependencies for %s: %s",
                    domain, ", ".join(missing_deps))

            break

    # Make sure we load groups if not in list yet.
    if not group_added:
        validated.append(group.DOMAIN)

        if group.DOMAIN not in components:
            components[group.DOMAIN] = \
                loader.get_component(group.DOMAIN)

    # Setup the components
    if core_components.setup(hass, config):
        logger.info("Home Assistant core initialized")

        for domain in validated:
            component = components[domain]

            try:
                if component.setup(hass, config):
                    logger.info("component %s initialized", domain)
                else:
                    logger.error("component %s failed to initialize", domain)

            except Exception:  # pylint: disable=broad-except
                logger.exception("Error during setup of component %s", domain)

    else:
        logger.error(("Home Assistant core failed to initialize. "
                      "Further initialization aborted."))

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

            err_handler.setLevel(logging.ERROR)
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
