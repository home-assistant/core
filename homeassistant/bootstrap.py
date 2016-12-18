"""Provides methods to bootstrap a home assistant instance."""
import asyncio
import logging
import logging.handlers
import os
import sys
from collections import OrderedDict

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
from homeassistant.util.async import (
    run_coroutine_threadsafe, run_callback_threadsafe)
from homeassistant.util.logging import AsyncHandler
from homeassistant.util.yaml import clear_secret_cache
from homeassistant.const import EVENT_COMPONENT_LOADED, PLATFORM_FORMAT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    event_decorators, service, config_per_platform, extract_domain_configs)

_LOGGER = logging.getLogger(__name__)

ATTR_COMPONENT = 'component'

ERROR_LOG_FILENAME = 'home-assistant.log'
_PERSISTENT_ERRORS = {}
HA_COMPONENT_URL = '[{}](https://home-assistant.io/components/{}/)'


def setup_component(hass: core.HomeAssistant, domain: str,
                    config: Optional[Dict]=None) -> bool:
    """Setup a component and all its dependencies."""
    return run_coroutine_threadsafe(
        async_setup_component(hass, domain, config), loop=hass.loop).result()


@asyncio.coroutine
def async_setup_component(hass: core.HomeAssistant, domain: str,
                          config: Optional[Dict]=None) -> bool:
    """Setup a component and all its dependencies.

    This method is a coroutine.
    """
    if domain in hass.config.components:
        _LOGGER.debug('Component %s already set up.', domain)
        return True

    if not loader.PREPARED:
        yield from hass.loop.run_in_executor(None, loader.prepare, hass)

    if config is None:
        config = {}

    components = loader.load_order_component(domain)

    # OrderedSet is empty if component or dependencies could not be resolved
    if not components:
        _async_persistent_notification(hass, domain, True)
        return False

    for component in components:
        res = yield from _async_setup_component(hass, component, config)
        if not res:
            _LOGGER.error('Component %s failed to setup', component)
            _async_persistent_notification(hass, component, True)
            return False

    return True


def _handle_requirements(hass: core.HomeAssistant, component,
                         name: str) -> bool:
    """Install the requirements for a component.

    This method needs to run in an executor.
    """
    if hass.config.skip_pip or not hasattr(component, 'REQUIREMENTS'):
        return True

    for req in component.REQUIREMENTS:
        if not pkg_util.install_package(req, target=hass.config.path('deps')):
            _LOGGER.error('Not initializing %s because could not install '
                          'dependency %s', name, req)
            _async_persistent_notification(hass, name)
            return False

    return True


@asyncio.coroutine
def _async_setup_component(hass: core.HomeAssistant,
                           domain: str, config) -> bool:
    """Setup a component for Home Assistant.

    This method is a coroutine.
    """
    # pylint: disable=too-many-return-statements
    if domain in hass.config.components:
        return True

    setup_lock = hass.data.get('setup_lock')
    if setup_lock is None:
        setup_lock = hass.data['setup_lock'] = asyncio.Lock(loop=hass.loop)

    setup_progress = hass.data.get('setup_progress')
    if setup_progress is None:
        setup_progress = hass.data['setup_progress'] = []

    if domain in setup_progress:
        _LOGGER.error('Attempt made to setup %s during setup of %s',
                      domain, domain)
        _async_persistent_notification(hass, domain, True)
        return False

    try:
        # Used to indicate to discovery that a setup is ongoing and allow it
        # to wait till it is done.
        did_lock = False
        if not setup_lock.locked():
            yield from setup_lock.acquire()
            did_lock = True

        setup_progress.append(domain)
        config = yield from async_prepare_setup_component(hass, config, domain)

        if config is None:
            return False

        component = loader.get_component(domain)
        if component is None:
            _async_persistent_notification(hass, domain)
            return False

        async_comp = hasattr(component, 'async_setup')

        try:
            _LOGGER.info("Setting up %s", domain)
            if async_comp:
                result = yield from component.async_setup(hass, config)
            else:
                result = yield from hass.loop.run_in_executor(
                    None, component.setup, hass, config)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error during setup of component %s', domain)
            _async_persistent_notification(hass, domain, True)
            return False

        if result is False:
            _LOGGER.error('component %s failed to initialize', domain)
            _async_persistent_notification(hass, domain, True)
            return False
        elif result is not True:
            _LOGGER.error('component %s did not return boolean if setup '
                          'was successful. Disabling component.', domain)
            _async_persistent_notification(hass, domain, True)
            loader.set_component(domain, None)
            return False

        hass.config.components.append(component.DOMAIN)

        hass.bus.async_fire(
            EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: component.DOMAIN}
        )

        return True
    finally:
        setup_progress.remove(domain)
        if did_lock:
            setup_lock.release()


def prepare_setup_component(hass: core.HomeAssistant, config: dict,
                            domain: str):
    """Prepare setup of a component and return processed config."""
    return run_coroutine_threadsafe(
        async_prepare_setup_component(hass, config, domain), loop=hass.loop
    ).result()


@asyncio.coroutine
def async_prepare_setup_component(hass: core.HomeAssistant, config: dict,
                                  domain: str):
    """Prepare setup of a component and return processed config.

    This method is a coroutine.
    """
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
            async_log_exception(ex, domain, config, hass)
            return None

    elif hasattr(component, 'PLATFORM_SCHEMA'):
        platforms = []
        for p_name, p_config in config_per_platform(config, domain):
            # Validate component specific platform schema
            try:
                p_validated = component.PLATFORM_SCHEMA(p_config)
            except vol.Invalid as ex:
                async_log_exception(ex, domain, config, hass)
                continue

            # Not all platform components follow same pattern for platforms
            # So if p_name is None we are not going to validate platform
            # (the automation component is one of them)
            if p_name is None:
                platforms.append(p_validated)
                continue

            platform = yield from async_prepare_setup_platform(
                hass, config, domain, p_name)

            if platform is None:
                continue

            # Validate platform specific schema
            if hasattr(platform, 'PLATFORM_SCHEMA'):
                try:
                    # pylint: disable=no-member
                    p_validated = platform.PLATFORM_SCHEMA(p_validated)
                except vol.Invalid as ex:
                    async_log_exception(ex, '{}.{}'.format(domain, p_name),
                                        p_validated, hass)
                    continue

            platforms.append(p_validated)

        # Create a copy of the configuration with all config for current
        # component removed and add validated config back in.
        filter_keys = extract_domain_configs(config, domain)
        config = {key: value for key, value in config.items()
                  if key not in filter_keys}
        config[domain] = platforms

    res = yield from hass.loop.run_in_executor(
        None, _handle_requirements, hass, component, domain)
    if not res:
        return None

    return config


def prepare_setup_platform(hass: core.HomeAssistant, config, domain: str,
                           platform_name: str) -> Optional[ModuleType]:
    """Load a platform and makes sure dependencies are setup."""
    return run_coroutine_threadsafe(
        async_prepare_setup_platform(hass, config, domain, platform_name),
        loop=hass.loop
    ).result()


@asyncio.coroutine
def async_prepare_setup_platform(hass: core.HomeAssistant, config, domain: str,
                                 platform_name: str) \
                                 -> Optional[ModuleType]:
    """Load a platform and makes sure dependencies are setup.

    This method is a coroutine.
    """
    if not loader.PREPARED:
        yield from hass.loop.run_in_executor(None, loader.prepare, hass)

    platform_path = PLATFORM_FORMAT.format(domain, platform_name)

    platform = loader.get_platform(domain, platform_name)

    # Not found
    if platform is None:
        _LOGGER.error('Unable to find platform %s', platform_path)
        _async_persistent_notification(hass, platform_path)
        return None

    # Already loaded
    elif platform_path in hass.config.components:
        return platform

    # Load dependencies
    for component in getattr(platform, 'DEPENDENCIES', []):
        res = yield from async_setup_component(hass, component, config)
        if not res:
            _LOGGER.error(
                'Unable to prepare setup for platform %s because '
                'dependency %s could not be initialized', platform_path,
                component)
            _async_persistent_notification(hass, platform_path, True)
            return None

    res = yield from hass.loop.run_in_executor(
        None, _handle_requirements, hass, platform, platform_path)
    if not res:
        return None

    return platform


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

    @asyncio.coroutine
    def _async_init_from_config_dict(future):
        try:
            re_hass = yield from async_from_config_dict(
                config, hass, config_dir, enable_log, verbose, skip_pip,
                log_rotate_days)
            future.set_result(re_hass)
        # pylint: disable=broad-except
        except Exception as exc:
            future.set_exception(exc)

    # run task
    future = asyncio.Future(loop=hass.loop)
    hass.async_add_job(_async_init_from_config_dict(future))
    hass.loop.run_until_complete(future)

    return future.result()


@asyncio.coroutine
def async_from_config_dict(config: Dict[str, Any],
                           hass: core.HomeAssistant,
                           config_dir: Optional[str]=None,
                           enable_log: bool=True,
                           verbose: bool=False,
                           skip_pip: bool=False,
                           log_rotate_days: Any=None) \
                           -> Optional[core.HomeAssistant]:
    """Try to configure Home Assistant from a config dict.

    Dynamically loads required components and its dependencies.
    This method is a coroutine.
    """
    hass.async_track_tasks()
    setup_lock = hass.data.get('setup_lock')
    if setup_lock is None:
        setup_lock = hass.data['setup_lock'] = asyncio.Lock(loop=hass.loop)

    yield from setup_lock.acquire()

    core_config = config.get(core.DOMAIN, {})

    try:
        yield from conf_util.async_process_ha_core_config(hass, core_config)
    except vol.Invalid as ex:
        async_log_exception(ex, 'homeassistant', core_config, hass)
        return None

    yield from hass.loop.run_in_executor(
        None, conf_util.process_ha_config_upgrade, hass)

    if enable_log:
        enable_logging(hass, verbose, log_rotate_days)

    hass.config.skip_pip = skip_pip
    if skip_pip:
        _LOGGER.warning('Skipping pip installation of required modules. '
                        'This may cause issues.')

    if not loader.PREPARED:
        yield from hass.loop.run_in_executor(None, loader.prepare, hass)

    # Make a copy because we are mutating it.
    # Use OrderedDict in case original one was one.
    # Convert values to dictionaries if they are None
    new_config = OrderedDict()
    for key, value in config.items():
        new_config[key] = value or {}
    config = new_config

    # Filter out the repeating and common config section [homeassistant]
    components = set(key.split(' ')[0] for key in config.keys()
                     if key != core.DOMAIN)

    # setup components
    # pylint: disable=not-an-iterable
    res = yield from core_components.async_setup(hass, config)
    if not res:
        _LOGGER.error('Home Assistant core failed to initialize. '
                      'Further initialization aborted.')
        return hass

    yield from persistent_notification.async_setup(hass, config)

    _LOGGER.info('Home Assistant core initialized')

    # Give event decorators access to HASS
    event_decorators.HASS = hass
    service.HASS = hass

    # Setup the components
    for domain in loader.load_order_components(components):
        yield from _async_setup_component(hass, domain, config)

    setup_lock.release()

    yield from hass.async_stop_track_tasks()

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

    @asyncio.coroutine
    def _async_init_from_config_file(future):
        try:
            re_hass = yield from async_from_config_file(
                config_path, hass, verbose, skip_pip, log_rotate_days)
            future.set_result(re_hass)
        # pylint: disable=broad-except
        except Exception as exc:
            future.set_exception(exc)

    # run task
    future = asyncio.Future(loop=hass.loop)
    hass.loop.create_task(_async_init_from_config_file(future))
    hass.loop.run_until_complete(future)

    return future.result()


@asyncio.coroutine
def async_from_config_file(config_path: str,
                           hass: core.HomeAssistant,
                           verbose: bool=False,
                           skip_pip: bool=True,
                           log_rotate_days: Any=None):
    """Read the configuration file and try to start all the functionality.

    Will add functionality to 'hass' parameter.
    This method is a coroutine.
    """
    # Set config dir to directory holding config file
    config_dir = os.path.abspath(os.path.dirname(config_path))
    hass.config.config_dir = config_dir
    yield from hass.loop.run_in_executor(
        None, mount_local_lib_path, config_dir)

    enable_logging(hass, verbose, log_rotate_days)

    try:
        config_dict = yield from hass.loop.run_in_executor(
            None, conf_util.load_yaml_config_file, config_path)
    except HomeAssistantError:
        return None
    finally:
        clear_secret_cache()

    hass = yield from async_from_config_dict(
        config_dict, hass, enable_log=False, skip_pip=skip_pip)
    return hass


def enable_logging(hass: core.HomeAssistant, verbose: bool=False,
                   log_rotate_days=None) -> None:
    """Setup the logging.

    Async friendly.
    """
    logging.basicConfig(level=logging.INFO)
    fmt = ("%(log_color)s%(asctime)s %(levelname)s (%(threadName)s) "
           "[%(name)s] %(message)s%(reset)s")

    # suppress overly verbose logs from libraries that aren't helpful
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

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

    # AsyncHandler allready exists?
    if hass.data.get(core.DATA_ASYNCHANDLER):
        return

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

        async_handler = AsyncHandler(hass.loop, err_handler)
        hass.data[core.DATA_ASYNCHANDLER] = async_handler

        logger = logging.getLogger('')
        logger.addHandler(async_handler)
        logger.setLevel(logging.INFO)

    else:
        _LOGGER.error(
            'Unable to setup error log %s (access denied)', err_log_path)


def log_exception(ex, domain, config, hass):
    """Generate log exception for config validation."""
    run_callback_threadsafe(
        hass.loop, async_log_exception, ex, domain, config, hass).result()


@core.callback
def _async_persistent_notification(hass: core.HomeAssistant, component: str,
                                   link: Optional[bool]=False):
    """Print a persistent notification.

    This method must be run in the event loop.
    """
    _PERSISTENT_ERRORS[component] = _PERSISTENT_ERRORS.get(component) or link
    _lst = [HA_COMPONENT_URL.format(name.replace('_', '-'), name)
            if link else name for name, link in _PERSISTENT_ERRORS.items()]
    message = ('The following components and platforms could not be set up:\n'
               '* ' + '\n* '.join(list(_lst)) + '\nPlease check your config')
    persistent_notification.async_create(
        hass, message, 'Invalid config', 'invalid_config')


@core.callback
def async_log_exception(ex, domain, config, hass):
    """Generate log exception for config validation.

    This method must be run in the event loop.
    """
    message = 'Invalid config for [{}]: '.format(domain)
    if hass is not None:
        _async_persistent_notification(hass, domain, True)

    if 'extra keys not allowed' in ex.error_message:
        message += '[{}] is an invalid option for [{}]. Check: {}->{}.'\
                   .format(ex.path[-1], domain, domain,
                           '->'.join(str(m) for m in ex.path))
    else:
        message += '{}.'.format(humanize_error(config, ex))

    domain_config = config.get(domain, config)
    message += " (See {}:{}). ".format(
        getattr(domain_config, '__config_file__', '?'),
        getattr(domain_config, '__line__', '?'))

    if domain != 'homeassistant':
        message += ('Please check the docs at '
                    'https://home-assistant.io/components/{}/'.format(domain))

    _LOGGER.error(message)


def mount_local_lib_path(config_dir: str) -> str:
    """Add local library to Python Path.

    Async friendly.
    """
    deps_dir = os.path.join(config_dir, 'deps')
    if deps_dir not in sys.path:
        sys.path.insert(0, os.path.join(config_dir, 'deps'))
    return deps_dir
