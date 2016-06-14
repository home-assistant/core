"""Provides methods to bootstrap a home assistant instance."""

import logging
import logging.handlers
import os
import shutil
import sys
from collections import defaultdict
from threading import RLock

import voluptuous as vol

import homeassistant.components as core_components
import homeassistant.components.group as group
import homeassistant.config as config_util
import homeassistant.core as core
import homeassistant.helpers.config_validation as cv
import homeassistant.loader as loader
import homeassistant.util.dt as date_util
import homeassistant.util.location as loc_util
import homeassistant.util.package as pkg_util
from homeassistant.const import (
    CONF_CUSTOMIZE, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME,
    CONF_TEMPERATURE_UNIT, CONF_TIME_ZONE, EVENT_COMPONENT_LOADED,
    TEMP_CELSIUS, TEMP_FAHRENHEIT, PLATFORM_FORMAT, __version__)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    event_decorators, service, config_per_platform, extract_domain_configs)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
_SETUP_LOCK = RLock()
_CURRENT_SETUP = []

ATTR_COMPONENT = 'component'

ERROR_LOG_FILENAME = 'home-assistant.log'


def setup_component(hass, domain, config=None):
    """Setup a component and all its dependencies."""
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
        if not _setup_component(hass, component, config):
            return False

    return True


def _handle_requirements(hass, component, name):
    """Install the requirements for a component."""
    if hass.config.skip_pip or not hasattr(component, 'REQUIREMENTS'):
        return True

    for req in component.REQUIREMENTS:
        if not pkg_util.install_package(req, target=hass.config.path('deps')):
            _LOGGER.error('Not initializing %s because could not install '
                          'dependency %s', name, req)
            return False

    return True


def _setup_component(hass, domain, config):
    """Setup a component for Home Assistant."""
    # pylint: disable=too-many-return-statements,too-many-branches
    if domain in hass.config.components:
        return True

    with _SETUP_LOCK:
        # It might have been loaded while waiting for lock
        if domain in hass.config.components:
            return True

        if domain in _CURRENT_SETUP:
            _LOGGER.error('Attempt made to setup %s during setup of %s',
                          domain, domain)
            return False

        component = loader.get_component(domain)
        missing_deps = [dep for dep in getattr(component, 'DEPENDENCIES', [])
                        if dep not in hass.config.components]

        if missing_deps:
            _LOGGER.error(
                'Not initializing %s because not all dependencies loaded: %s',
                domain, ", ".join(missing_deps))
            return False

        if hasattr(component, 'CONFIG_SCHEMA'):
            try:
                config = component.CONFIG_SCHEMA(config)
            except vol.MultipleInvalid as ex:
                cv.log_exception(_LOGGER, ex, domain, config)
                return False

        elif hasattr(component, 'PLATFORM_SCHEMA'):
            platforms = []
            for p_name, p_config in config_per_platform(config, domain):
                # Validate component specific platform schema
                try:
                    p_validated = component.PLATFORM_SCHEMA(p_config)
                except vol.MultipleInvalid as ex:
                    cv.log_exception(_LOGGER, ex, domain, p_config)
                    return False

                # Not all platform components follow same pattern for platforms
                # So if p_name is None we are not going to validate platform
                # (the automation component is one of them)
                if p_name is None:
                    platforms.append(p_validated)
                    continue

                platform = prepare_setup_platform(hass, config, domain,
                                                  p_name)

                if platform is None:
                    return False

                # Validate platform specific schema
                if hasattr(platform, 'PLATFORM_SCHEMA'):
                    try:
                        p_validated = platform.PLATFORM_SCHEMA(p_validated)
                    except vol.MultipleInvalid as ex:
                        cv.log_exception(_LOGGER, ex, '{}.{}'
                                         .format(domain, p_name), p_validated)
                        return False

                platforms.append(p_validated)

            # Create a copy of the configuration with all config for current
            # component removed and add validated config back in.
            filter_keys = extract_domain_configs(config, domain)
            config = {key: value for key, value in config.items()
                      if key not in filter_keys}
            config[domain] = platforms

        if not _handle_requirements(hass, component, domain):
            return False

        _CURRENT_SETUP.append(domain)

        try:
            if not component.setup(hass, config):
                _LOGGER.error('component %s failed to initialize', domain)
                return False
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error during setup of component %s', domain)
            return False
        finally:
            _CURRENT_SETUP.remove(domain)

        hass.config.components.append(component.DOMAIN)

        # Assumption: if a component does not depend on groups
        # it communicates with devices
        if group.DOMAIN not in getattr(component, 'DEPENDENCIES', []):
            hass.pool.add_worker()

        hass.bus.fire(
            EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: component.DOMAIN})

        return True


def prepare_setup_platform(hass, config, domain, platform_name):
    """Load a platform and makes sure dependencies are setup."""
    _ensure_loader_prepared(hass)

    platform_path = PLATFORM_FORMAT.format(domain, platform_name)

    platform = loader.get_platform(domain, platform_name)

    # Not found
    if platform is None:
        _LOGGER.error('Unable to find platform %s', platform_path)
        return None

    # Already loaded
    elif platform_path in hass.config.components:
        return platform

    # Load dependencies
    for component in getattr(platform, 'DEPENDENCIES', []):
        if not setup_component(hass, component, config):
            _LOGGER.error(
                'Unable to prepare setup for platform %s because '
                'dependency %s could not be initialized', platform_path,
                component)
            return None

    if not _handle_requirements(hass, platform, platform_path):
        return None

    return platform


def mount_local_lib_path(config_dir):
    """Add local library to Python Path."""
    sys.path.insert(0, os.path.join(config_dir, 'deps'))


# pylint: disable=too-many-branches, too-many-statements, too-many-arguments
def from_config_dict(config, hass=None, config_dir=None, enable_log=True,
                     verbose=False, skip_pip=False,
                     log_rotate_days=None):
    """Try to configure Home Assistant from a config dict.

    Dynamically loads required components and its dependencies.
    """
    if hass is None:
        hass = core.HomeAssistant()
        if config_dir is not None:
            config_dir = os.path.abspath(config_dir)
            hass.config.config_dir = config_dir
            mount_local_lib_path(config_dir)

    core_config = config.get(core.DOMAIN, {})

    try:
        process_ha_core_config(hass, config_util.CORE_CONFIG_SCHEMA(
            core_config))
    except vol.MultipleInvalid as ex:
        cv.log_exception(_LOGGER, ex, 'homeassistant', core_config)
        return None

    process_ha_config_upgrade(hass)

    if enable_log:
        enable_logging(hass, verbose, log_rotate_days)

    hass.config.skip_pip = skip_pip
    if skip_pip:
        _LOGGER.warning('Skipping pip installation of required modules. '
                        'This may cause issues.')

    _ensure_loader_prepared(hass)

    # Make a copy because we are mutating it.
    # Convert it to defaultdict so components can always have config dict
    # Convert values to dictionaries if they are None
    config = defaultdict(
        dict, {key: value or {} for key, value in config.items()})

    # Filter out the repeating and common config section [homeassistant]
    components = set(key.split(' ')[0] for key in config.keys()
                     if key != core.DOMAIN)

    if not core_components.setup(hass, config):
        _LOGGER.error('Home Assistant core failed to initialize. '
                      'Further initialization aborted.')

        return hass

    _LOGGER.info('Home Assistant core initialized')

    # Give event decorators access to HASS
    event_decorators.HASS = hass
    service.HASS = hass

    # Setup the components
    for domain in loader.load_order_components(components):
        _setup_component(hass, domain, config)

    return hass


def from_config_file(config_path, hass=None, verbose=False, skip_pip=True,
                     log_rotate_days=None):
    """Read the configuration file and try to start all the functionality.

    Will add functionality to 'hass' parameter if given,
    instantiates a new Home Assistant object if 'hass' is not given.
    """
    if hass is None:
        hass = core.HomeAssistant()

    # Set config dir to directory holding config file
    config_dir = os.path.abspath(os.path.dirname(config_path))
    hass.config.config_dir = config_dir
    mount_local_lib_path(config_dir)

    enable_logging(hass, verbose, log_rotate_days)

    try:
        config_dict = config_util.load_yaml_config_file(config_path)
    except HomeAssistantError:
        return None

    return from_config_dict(config_dict, hass, enable_log=False,
                            skip_pip=skip_pip)


def enable_logging(hass, verbose=False, log_rotate_days=None):
    """Setup the logging."""
    logging.basicConfig(level=logging.INFO)
    fmt = ("%(log_color)s%(asctime)s %(levelname)s (%(threadName)s) "
           "[%(name)s] %(message)s%(reset)s")
    try:
        from colorlog import ColoredFormatter
        logging.getLogger().handlers[0].setFormatter(ColoredFormatter(
            fmt,
            datefmt='%y-%m-%d %H:%M:%S',
            reset=True,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red',
            }
        ))
    except ImportError:
        pass

    # Log errors to a file if we have write access to file or config dir
    err_log_path = hass.config.path(ERROR_LOG_FILENAME)
    err_path_exists = os.path.isfile(err_log_path)

    # Check if we can write to the error log if it exists or that
    # we can create files in the containing directory if not.
    if (err_path_exists and os.access(err_log_path, os.W_OK)) or \
       (not err_path_exists and os.access(hass.config.config_dir, os.W_OK)):

        if log_rotate_days:
            err_handler = logging.handlers.TimedRotatingFileHandler(
                err_log_path, when='midnight', backupCount=log_rotate_days)
        else:
            err_handler = logging.FileHandler(
                err_log_path, mode='w', delay=True)

        err_handler.setLevel(logging.INFO if verbose else logging.WARNING)
        err_handler.setFormatter(
            logging.Formatter('%(asctime)s %(name)s: %(message)s',
                              datefmt='%y-%m-%d %H:%M:%S'))
        logger = logging.getLogger('')
        logger.addHandler(err_handler)
        logger.setLevel(logging.INFO)

    else:
        _LOGGER.error(
            'Unable to setup error log %s (access denied)', err_log_path)


def process_ha_config_upgrade(hass):
    """Upgrade config if necessary."""
    version_path = hass.config.path('.HA_VERSION')

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

    # This was where dependencies were installed before v0.18
    # Probably should keep this around until ~v0.20.
    lib_path = hass.config.path('lib')
    if os.path.isdir(lib_path):
        shutil.rmtree(lib_path)

    lib_path = hass.config.path('deps')
    if os.path.isdir(lib_path):
        shutil.rmtree(lib_path)

    with open(version_path, 'wt') as outp:
        outp.write(__version__)


def process_ha_core_config(hass, config):
    """Process the [homeassistant] section from the config."""
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
                      (CONF_NAME, 'location_name')):
        if key in config:
            setattr(hac, attr, config[key])

    if CONF_TIME_ZONE in config:
        set_time_zone(config.get(CONF_TIME_ZONE))

    for entity_id, attrs in config.get(CONF_CUSTOMIZE).items():
        Entity.overwrite_attribute(entity_id, attrs.keys(), attrs.values())

    if CONF_TEMPERATURE_UNIT in config:
        hac.temperature_unit = config[CONF_TEMPERATURE_UNIT]

    # If we miss some of the needed values, auto detect them
    if None not in (
            hac.latitude, hac.longitude, hac.temperature_unit, hac.time_zone):
        return

    _LOGGER.warning('Incomplete core config. Auto detecting location and '
                    'temperature unit')

    info = loc_util.detect_location_info()

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
            hac.temperature_unit = TEMP_CELSIUS

    if hac.location_name is None:
        hac.location_name = info.city

    if hac.time_zone is None:
        set_time_zone(info.time_zone)


def _ensure_loader_prepared(hass):
    """Ensure Home Assistant loader is prepared."""
    if not loader.PREPARED:
        loader.prepare(hass)
