"""Provide methods to bootstrap a Home Assistant instance."""
import asyncio
import logging
import logging.handlers
import os
import sys
from time import time
from collections import OrderedDict

from typing import Any, Optional, Dict

import voluptuous as vol

from homeassistant import (
    core, config as conf_util, config_entries, loader,
    components as core_components)
from homeassistant.components import persistent_notification
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.setup import async_setup_component
from homeassistant.util.logging import AsyncHandler
from homeassistant.util.package import async_get_user_site, get_user_site
from homeassistant.util.yaml import clear_secret_cache
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.signal import async_register_signal_handling

_LOGGER = logging.getLogger(__name__)

ERROR_LOG_FILENAME = 'home-assistant.log'

# hass.data key for logging information.
DATA_LOGGING = 'logging'

FIRST_INIT_COMPONENT = set((
    'system_log', 'recorder', 'mqtt', 'mqtt_eventstream', 'logger',
    'introduction', 'frontend', 'history'))


def from_config_dict(config: Dict[str, Any],
                     hass: Optional[core.HomeAssistant] = None,
                     config_dir: Optional[str] = None,
                     enable_log: bool = True,
                     verbose: bool = False,
                     skip_pip: bool = False,
                     log_rotate_days: Any = None,
                     log_file: Any = None) \
                     -> Optional[core.HomeAssistant]:
    """Try to configure Home Assistant from a configuration dictionary.

    Dynamically loads required components and its dependencies.
    """
    if hass is None:
        hass = core.HomeAssistant()
        if config_dir is not None:
            config_dir = os.path.abspath(config_dir)
            hass.config.config_dir = config_dir
            hass.loop.run_until_complete(
                async_mount_local_lib_path(config_dir, hass.loop))

    # run task
    hass = hass.loop.run_until_complete(
        async_from_config_dict(
            config, hass, config_dir, enable_log, verbose, skip_pip,
            log_rotate_days, log_file)
    )

    return hass


@asyncio.coroutine
def async_from_config_dict(config: Dict[str, Any],
                           hass: core.HomeAssistant,
                           config_dir: Optional[str] = None,
                           enable_log: bool = True,
                           verbose: bool = False,
                           skip_pip: bool = False,
                           log_rotate_days: Any = None,
                           log_file: Any = None) \
                           -> Optional[core.HomeAssistant]:
    """Try to configure Home Assistant from a configuration dictionary.

    Dynamically loads required components and its dependencies.
    This method is a coroutine.
    """
    start = time()

    if enable_log:
        async_enable_logging(hass, verbose, log_rotate_days, log_file)

    if sys.version_info[:2] < (3, 5):
        _LOGGER.warning(
            'Python 3.4 support has been deprecated and will be removed in '
            'the beginning of 2018. Please upgrade Python or your operating '
            'system. More info: https://home-assistant.io/blog/2017/10/06/'
            'deprecating-python-3.4-support/'
        )

    core_config = config.get(core.DOMAIN, {})

    try:
        yield from conf_util.async_process_ha_core_config(hass, core_config)
    except vol.Invalid as ex:
        conf_util.async_log_exception(ex, 'homeassistant', core_config, hass)
        return None

    yield from hass.async_add_job(conf_util.process_ha_config_upgrade, hass)

    hass.config.skip_pip = skip_pip
    if skip_pip:
        _LOGGER.warning("Skipping pip installation of required modules. "
                        "This may cause issues")

    if not loader.PREPARED:
        yield from hass.async_add_job(loader.prepare, hass)

    # Merge packages
    conf_util.merge_packages_config(
        config, core_config.get(conf_util.CONF_PACKAGES, {}))

    # Make a copy because we are mutating it.
    # Use OrderedDict in case original one was one.
    # Convert values to dictionaries if they are None
    new_config = OrderedDict()
    for key, value in config.items():
        new_config[key] = value or {}
    config = new_config

    hass.config_entries = config_entries.ConfigEntries(hass, config)
    yield from hass.config_entries.async_load()

    # Filter out the repeating and common config section [homeassistant]
    components = set(key.split(' ')[0] for key in config.keys()
                     if key != core.DOMAIN)
    components.update(hass.config_entries.async_domains())

    # setup components
    # pylint: disable=not-an-iterable
    res = yield from core_components.async_setup(hass, config)
    if not res:
        _LOGGER.error("Home Assistant core failed to initialize. "
                      "further initialization aborted")
        return hass

    yield from persistent_notification.async_setup(hass, config)

    _LOGGER.info("Home Assistant core initialized")

    # stage 1
    for component in components:
        if component not in FIRST_INIT_COMPONENT:
            continue
        hass.async_add_job(async_setup_component(hass, component, config))

    yield from hass.async_block_till_done()

    # stage 2
    for component in components:
        if component in FIRST_INIT_COMPONENT:
            continue
        hass.async_add_job(async_setup_component(hass, component, config))

    yield from hass.async_block_till_done()

    stop = time()
    _LOGGER.info("Home Assistant initialized in %.2fs", stop-start)

    async_register_signal_handling(hass)
    return hass


def from_config_file(config_path: str,
                     hass: Optional[core.HomeAssistant] = None,
                     verbose: bool = False,
                     skip_pip: bool = True,
                     log_rotate_days: Any = None,
                     log_file: Any = None):
    """Read the configuration file and try to start all the functionality.

    Will add functionality to 'hass' parameter if given,
    instantiates a new Home Assistant object if 'hass' is not given.
    """
    if hass is None:
        hass = core.HomeAssistant()

    # run task
    hass = hass.loop.run_until_complete(
        async_from_config_file(
            config_path, hass, verbose, skip_pip, log_rotate_days, log_file)
    )

    return hass


@asyncio.coroutine
def async_from_config_file(config_path: str,
                           hass: core.HomeAssistant,
                           verbose: bool = False,
                           skip_pip: bool = True,
                           log_rotate_days: Any = None,
                           log_file: Any = None):
    """Read the configuration file and try to start all the functionality.

    Will add functionality to 'hass' parameter.
    This method is a coroutine.
    """
    # Set config dir to directory holding config file
    config_dir = os.path.abspath(os.path.dirname(config_path))
    hass.config.config_dir = config_dir
    yield from async_mount_local_lib_path(config_dir, hass.loop)

    async_enable_logging(hass, verbose, log_rotate_days, log_file)

    try:
        config_dict = yield from hass.async_add_job(
            conf_util.load_yaml_config_file, config_path)
    except HomeAssistantError as err:
        _LOGGER.error("Error loading %s: %s", config_path, err)
        return None
    finally:
        clear_secret_cache()

    hass = yield from async_from_config_dict(
        config_dict, hass, enable_log=False, skip_pip=skip_pip)
    return hass


@core.callback
def async_enable_logging(hass: core.HomeAssistant, verbose: bool = False,
                         log_rotate_days=None, log_file=None) -> None:
    """Set up the logging.

    This method must be run in the event loop.
    """
    logging.basicConfig(level=logging.INFO)
    fmt = ("%(asctime)s %(levelname)s (%(threadName)s) "
           "[%(name)s] %(message)s")
    colorfmt = "%(log_color)s{}%(reset)s".format(fmt)
    datefmt = '%Y-%m-%d %H:%M:%S'

    # Suppress overly verbose logs from libraries that aren't helpful
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

    try:
        from colorlog import ColoredFormatter
        logging.getLogger().handlers[0].setFormatter(ColoredFormatter(
            colorfmt,
            datefmt=datefmt,
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
    if log_file is None:
        err_log_path = hass.config.path(ERROR_LOG_FILENAME)
    else:
        err_log_path = os.path.abspath(log_file)

    err_path_exists = os.path.isfile(err_log_path)
    err_dir = os.path.dirname(err_log_path)

    # Check if we can write to the error log if it exists or that
    # we can create files in the containing directory if not.
    if (err_path_exists and os.access(err_log_path, os.W_OK)) or \
       (not err_path_exists and os.access(err_dir, os.W_OK)):

        if log_rotate_days:
            err_handler = logging.handlers.TimedRotatingFileHandler(
                err_log_path, when='midnight', backupCount=log_rotate_days)
        else:
            err_handler = logging.FileHandler(
                err_log_path, mode='w', delay=True)

        err_handler.setLevel(logging.INFO if verbose else logging.WARNING)
        err_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

        async_handler = AsyncHandler(hass.loop, err_handler)

        @asyncio.coroutine
        def async_stop_async_handler(event):
            """Cleanup async handler."""
            logging.getLogger('').removeHandler(async_handler)
            yield from async_handler.async_close(blocking=True)

        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_CLOSE, async_stop_async_handler)

        logger = logging.getLogger('')
        logger.addHandler(async_handler)
        logger.setLevel(logging.INFO)

        # Save the log file location for access by other components.
        hass.data[DATA_LOGGING] = err_log_path
    else:
        _LOGGER.error(
            "Unable to setup error log %s (access denied)", err_log_path)


def mount_local_lib_path(config_dir: str) -> str:
    """Add local library to Python Path."""
    deps_dir = os.path.join(config_dir, 'deps')
    lib_dir = get_user_site(deps_dir)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    return deps_dir


@asyncio.coroutine
def async_mount_local_lib_path(config_dir: str,
                               loop: asyncio.AbstractEventLoop) -> str:
    """Add local library to Python Path.

    This function is a coroutine.
    """
    deps_dir = os.path.join(config_dir, 'deps')
    lib_dir = yield from async_get_user_site(deps_dir, loop=loop)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    return deps_dir
