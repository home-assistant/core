"""Provides methods to bootstrap a home assistant instance."""

import logging
import logging.handlers
import os
import sys
from collections import defaultdict
from threading import RLock

from types import ModuleType
from typing import Any, Optional, Dict

import voluptuous as vol
from voluptuous.humanize import humanize_error

import homeassistant.components as core_components
from homeassistant.components import persistent_notification
import homeassistant.config as conf_util
import homeassistant.core as core
import homeassistant.loader as loader
import homeassistant.util.package as pkg_util
from homeassistant.util.yaml import clear_secret_cache
from homeassistant.const import EVENT_COMPONENT_LOADED, PLATFORM_FORMAT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    event_decorators, service, config_per_platform, extract_domain_configs)

_LOGGER = logging.getLogger(__name__)
_SETUP_LOCK = RLock()
_CURRENT_SETUP = []

ATTR_COMPONENT = 'component'

ERROR_LOG_FILENAME = 'home-assistant.log'


def setup_component(hass: core.HomeAssistant, domain: str,
                    config: Optional[Dict]=None) -> bool:
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


def _handle_requirements(hass: core.HomeAssistant, component,
                         name: str) -> bool:
    """Install the requirements for a component."""
    if hass.config.skip_pip or not hasattr(component, 'REQUIREMENTS'):
        return True

    for req in component.REQUIREMENTS:
        if not pkg_util.install_package(req, target=hass.config.path('deps')):
            _LOGGER.error('Not initializing %s because could not install '
                          'dependency %s', name, req)
            return False

    return True


def _setup_component(hass: core.HomeAssistant, domain: str, config) -> bool:
    """Setup a component for Home Assistant."""
    # pylint: disable=too-many-return-statements,too-many-branches
    # pylint: disable=too-many-statements
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

        config = prepare_setup_component(hass, config, domain)

        if config is None:
            return False

        component = loader.get_component(domain)
        _CURRENT_SETUP.append(domain)

        try:
            result = component.setup(hass, config)
            if result is False:
                _LOGGER.error('component %s failed to initialize', domain)
                return False
            elif result is not True:
                _LOGGER.error('component %s did not return boolean if setup '
                              'was successful. Disabling component.', domain)
                loader.set_component(domain, None)
                return False
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error during setup of component %s', domain)
            return False
        finally:
            _CURRENT_SETUP.remove(domain)

        hass.config.components.append(component.DOMAIN)

        # Assumption: if a component does not depend on groups
        # it communicates with devices
        if 'group' not in getattr(component, 'DEPENDENCIES', []) and \
           hass.pool.worker_count <= 10:
            hass.pool.add_worker()

        hass.bus.fire(
            EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: component.DOMAIN}
        )

        return True


def prepare_setup_component(hass: core.HomeAssistant, config: dict,
                            domain: str):
    """Prepare setup of a component and return processed config."""
    # pylint: disable=too-many-return-statements
    component = loader.get_component(domain)
    missing_deps = [dep for dep in getattr(component, 'DEPENDENCIES', [])
                    if dep not in hass.config.components]

    if missing_deps:
        _LOGGER.error(
            'Not initializing %s because not all dependencies loaded: %s',
            domain, ", ".join(missing_deps))
        return None

    if hasattr(component, 'CONFIG_SCHEMA'):
        try:
            config = component.CONFIG_SCHEMA(config)
        except vol.Invalid as ex:
            log_exception(ex, domain, config)
            return None

    elif hasattr(component, 'PLATFORM_SCHEMA'):
        platforms = []
        for p_name, p_config in config_per_platform(config, domain):
            # Validate component specific platform schema
            try:
                p_validated = component.PLATFORM_SCHEMA(p_config)
            except vol.Invalid as ex:
                log_exception(ex, domain, config)
                return None

            # Not all platform components follow same pattern for platforms
            # So if p_name is None we are not going to validate platform
            # (the automation component is one of them)
            if p_name is None:
                platforms.append(p_validated)
                continue

            platform = prepare_setup_platform(hass, config, domain,
                                              p_name)

            if platform is None:
                return None

            # Validate platform specific schema
            if hasattr(platform, 'PLATFORM_SCHEMA'):
                try:
                    p_validated = platform.PLATFORM_SCHEMA(p_validated)
                except vol.Invalid as ex:
                    log_exception(ex, '{}.{}'.format(domain, p_name),
                                  p_validated)
                    return None

            platforms.append(p_validated)

        # Create a copy of the configuration with all config for current
        # component removed and add validated config back in.
        filter_keys = extract_domain_configs(config, domain)
        config = {key: value for key, value in config.items()
                  if key not in filter_keys}
        config[domain] = platforms

    if not _handle_requirements(hass, component, domain):
        return None

    return config


def prepare_setup_platform(hass: core.HomeAssistant, config, domain: str,
                           platform_name: str) -> Optional[ModuleType]:
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


# pylint: disable=too-many-branches, too-many-statements, too-many-arguments
def from_config_dict(config: Dict[str, Any],
                     hass: Optional[core.HomeAssistant]=None,
                     config_dir: Optional[str]=None,
                     enable_log: bool=True,
                     verbose: bool=False,
                     skip_pip: bool=False,
                     log_rotate_days: Any=None) \
                     -> Optional[core.HomeAssistant]:
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
        conf_util.process_ha_core_config(hass, core_config)
    except vol.Invalid as ex:
        log_exception(ex, 'homeassistant', core_config)
        return None

    conf_util.process_ha_config_upgrade(hass)

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

    # Setup in a thread to avoid blocking
    def component_setup():
        """Set up a component."""
        if not core_components.setup(hass, config):
            _LOGGER.error('Home Assistant core failed to initialize. '
                          'Further initialization aborted.')
            return hass

        persistent_notification.setup(hass, config)

        _LOGGER.info('Home Assistant core initialized')

        # Give event decorators access to HASS
        event_decorators.HASS = hass
        service.HASS = hass

        # Setup the components
        for domain in loader.load_order_components(components):
            _setup_component(hass, domain, config)

    hass.loop.run_until_complete(
        hass.loop.run_in_executor(None, component_setup)
    )
    return hass


def from_config_file(config_path: str,
                     hass: Optional[core.HomeAssistant]=None,
                     verbose: bool=False,
                     skip_pip: bool=True,
                     log_rotate_days: Any=None):
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
        config_dict = conf_util.load_yaml_config_file(config_path)
    except HomeAssistantError:
        return None
    finally:
        clear_secret_cache()

    return from_config_dict(config_dict, hass, enable_log=False,
                            skip_pip=skip_pip)


def enable_logging(hass: core.HomeAssistant, verbose: bool=False,
                   log_rotate_days=None) -> None:
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


def _ensure_loader_prepared(hass: core.HomeAssistant) -> None:
    """Ensure Home Assistant loader is prepared."""
    if not loader.PREPARED:
        loader.prepare(hass)


def log_exception(ex, domain, config):
    """Generate log exception for config validation."""
    message = 'Invalid config for [{}]: '.format(domain)

    if 'extra keys not allowed' in ex.error_message:
        message += '[{}] is an invalid option for [{}]. Check: {}->{}.'\
                   .format(ex.path[-1], domain, domain,
                           '->'.join('%s' % m for m in ex.path))
    else:
        message += '{}.'.format(humanize_error(config, ex))

    if hasattr(config, '__line__'):
        message += " (See {}:{})".format(
            config.__config_file__, config.__line__ or '?')

    if domain != 'homeassistant':
        message += (' Please check the docs at '
                    'https://home-assistant.io/components/{}/'.format(domain))

    _LOGGER.error(message)


def mount_local_lib_path(config_dir: str) -> str:
    """Add local library to Python Path."""
    deps_dir = os.path.join(config_dir, 'deps')
    if deps_dir not in sys.path:
        sys.path.insert(0, os.path.join(config_dir, 'deps'))
    return deps_dir
