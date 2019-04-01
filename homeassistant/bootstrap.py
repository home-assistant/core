"""Provide methods to bootstrap a Home Assistant instance."""
import asyncio
import logging
import logging.handlers
import os
import sys
from time import time
from collections import OrderedDict
from typing import Any, Optional, Dict, Set

import voluptuous as vol

from homeassistant import core, config as conf_util, config_entries, loader
from homeassistant.components import (
    persistent_notification, homeassistant as core_component
)
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.setup import async_setup_component
from homeassistant.util.logging import AsyncHandler
from homeassistant.util.package import async_get_user_site, is_virtual_env
from homeassistant.util.yaml import clear_secret_cache
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

ERROR_LOG_FILENAME = 'home-assistant.log'

# hass.data key for logging information.
DATA_LOGGING = 'logging'

LOGGING_COMPONENT = {'logger', 'system_log'}

FIRST_INIT_COMPONENT = {
    'recorder',
    'mqtt',
    'mqtt_eventstream',
    'introduction',
    'frontend',
    'history',
}


def from_config_dict(config: Dict[str, Any],
                     hass: Optional[core.HomeAssistant] = None,
                     config_dir: Optional[str] = None,
                     enable_log: bool = True,
                     verbose: bool = False,
                     skip_pip: bool = False,
                     log_rotate_days: Any = None,
                     log_file: Any = None,
                     log_no_color: bool = False) \
                     -> Optional[core.HomeAssistant]:
    """Try to configure Home Assistant from a configuration dictionary.

    Dynamically loads required components and its dependencies.
    """
    if hass is None:
        hass = core.HomeAssistant()
        if config_dir is not None:
            config_dir = os.path.abspath(config_dir)
            hass.config.config_dir = config_dir
            if not is_virtual_env():
                hass.loop.run_until_complete(
                    async_mount_local_lib_path(config_dir))

    # run task
    hass = hass.loop.run_until_complete(
        async_from_config_dict(
            config, hass, config_dir, enable_log, verbose, skip_pip,
            log_rotate_days, log_file, log_no_color)
    )
    return hass


async def async_from_config_dict(config: Dict[str, Any],
                                 hass: core.HomeAssistant,
                                 config_dir: Optional[str] = None,
                                 enable_log: bool = True,
                                 verbose: bool = False,
                                 skip_pip: bool = False,
                                 log_rotate_days: Any = None,
                                 log_file: Any = None,
                                 log_no_color: bool = False) \
                           -> Optional[core.HomeAssistant]:
    """Try to configure Home Assistant from a configuration dictionary.

    Dynamically loads required components and its dependencies.
    This method is a coroutine.
    """
    start = time()

    if enable_log:
        async_enable_logging(hass, verbose, log_rotate_days, log_file,
                             log_no_color)

    hass.config.skip_pip = skip_pip
    if skip_pip:
        _LOGGER.warning("Skipping pip installation of required modules. "
                        "This may cause issues")

    core_config = config.get(core.DOMAIN, {})
    api_password = config.get('http', {}).get('api_password')
    trusted_networks = config.get('http', {}).get('trusted_networks')

    try:
        await conf_util.async_process_ha_core_config(
            hass, core_config, api_password, trusted_networks)
    except vol.Invalid as config_err:
        conf_util.async_log_exception(
            config_err, 'homeassistant', core_config, hass)
        return None
    except HomeAssistantError:
        _LOGGER.error("Home Assistant core failed to initialize. "
                      "Further initialization aborted")
        return None

    await hass.async_add_executor_job(
        conf_util.process_ha_config_upgrade, hass)

    # Make a copy because we are mutating it.
    config = OrderedDict(config)

    # Merge packages
    conf_util.merge_packages_config(
        hass, config, core_config.get(conf_util.CONF_PACKAGES, {}))

    hass.config_entries = config_entries.ConfigEntries(hass, config)
    await hass.config_entries.async_initialize()

    components = _get_components(hass, config)

    # Resolve all dependencies of all components.
    for component in list(components):
        try:
            components.update(loader.component_dependencies(hass, component))
        except loader.LoaderError:
            # Ignore it, or we'll break startup
            # It will be properly handled during setup.
            pass

    # setup components
    res = await core_component.async_setup(hass, config)
    if not res:
        _LOGGER.error("Home Assistant core failed to initialize. "
                      "Further initialization aborted")
        return hass

    await persistent_notification.async_setup(hass, config)

    _LOGGER.info("Home Assistant core initialized")

    # stage 0, load logging components
    for component in components:
        if component in LOGGING_COMPONENT:
            hass.async_create_task(
                async_setup_component(hass, component, config))

    await hass.async_block_till_done()

    # Kick off loading the registries. They don't need to be awaited.
    asyncio.gather(
        hass.helpers.device_registry.async_get_registry(),
        hass.helpers.entity_registry.async_get_registry(),
        hass.helpers.area_registry.async_get_registry())

    # stage 1
    for component in components:
        if component in FIRST_INIT_COMPONENT:
            hass.async_create_task(
                async_setup_component(hass, component, config))

    await hass.async_block_till_done()

    # stage 2
    for component in components:
        if component in FIRST_INIT_COMPONENT or component in LOGGING_COMPONENT:
            continue
        hass.async_create_task(async_setup_component(hass, component, config))

    await hass.async_block_till_done()

    stop = time()
    _LOGGER.info("Home Assistant initialized in %.2fs", stop-start)

    # TEMP: warn users for invalid slugs
    # Remove after 0.94 or 1.0
    if cv.INVALID_SLUGS_FOUND or cv.INVALID_ENTITY_IDS_FOUND:
        msg = []

        if cv.INVALID_ENTITY_IDS_FOUND:
            msg.append(
                "Your configuration contains invalid entity ID references. "
                "Please find and update the following. "
                "This will become a breaking change."
            )
            msg.append('\n'.join('- {} -> {}'.format(*item)
                                 for item
                                 in cv.INVALID_ENTITY_IDS_FOUND.items()))

        if cv.INVALID_SLUGS_FOUND:
            msg.append(
                "Your configuration contains invalid slugs. "
                "Please find and update the following. "
                "This will become a breaking change."
            )
            msg.append('\n'.join('- {} -> {}'.format(*item)
                                 for item in cv.INVALID_SLUGS_FOUND.items()))

        hass.components.persistent_notification.async_create(
            '\n\n'.join(msg), "Config Warning", "config_warning"
        )

    # TEMP: warn users of invalid extra keys
    # Remove after 0.92
    if cv.INVALID_EXTRA_KEYS_FOUND:
        msg = []
        msg.append(
            "Your configuration contains extra keys "
            "that the platform does not support (but were silently "
            "accepted before 0.88). Please find and remove the following."
            "This will become a breaking change."
        )
        msg.append('\n'.join('- {}'.format(it)
                             for it in cv.INVALID_EXTRA_KEYS_FOUND))

        hass.components.persistent_notification.async_create(
            '\n\n'.join(msg), "Config Warning", "config_warning"
        )

    return hass


def from_config_file(config_path: str,
                     hass: Optional[core.HomeAssistant] = None,
                     verbose: bool = False,
                     skip_pip: bool = True,
                     log_rotate_days: Any = None,
                     log_file: Any = None,
                     log_no_color: bool = False)\
        -> Optional[core.HomeAssistant]:
    """Read the configuration file and try to start all the functionality.

    Will add functionality to 'hass' parameter if given,
    instantiates a new Home Assistant object if 'hass' is not given.
    """
    if hass is None:
        hass = core.HomeAssistant()

    # run task
    hass = hass.loop.run_until_complete(
        async_from_config_file(
            config_path, hass, verbose, skip_pip,
            log_rotate_days, log_file, log_no_color)
    )

    return hass


async def async_from_config_file(config_path: str,
                                 hass: core.HomeAssistant,
                                 verbose: bool = False,
                                 skip_pip: bool = True,
                                 log_rotate_days: Any = None,
                                 log_file: Any = None,
                                 log_no_color: bool = False)\
        -> Optional[core.HomeAssistant]:
    """Read the configuration file and try to start all the functionality.

    Will add functionality to 'hass' parameter.
    This method is a coroutine.
    """
    # Set config dir to directory holding config file
    config_dir = os.path.abspath(os.path.dirname(config_path))
    hass.config.config_dir = config_dir

    if not is_virtual_env():
        await async_mount_local_lib_path(config_dir)

    async_enable_logging(hass, verbose, log_rotate_days, log_file,
                         log_no_color)

    try:
        config_dict = await hass.async_add_executor_job(
            conf_util.load_yaml_config_file, config_path)
    except HomeAssistantError as err:
        _LOGGER.error("Error loading %s: %s", config_path, err)
        return None
    finally:
        clear_secret_cache()

    return await async_from_config_dict(
        config_dict, hass, enable_log=False, skip_pip=skip_pip)


@core.callback
def async_enable_logging(hass: core.HomeAssistant,
                         verbose: bool = False,
                         log_rotate_days: Optional[int] = None,
                         log_file: Optional[str] = None,
                         log_no_color: bool = False) -> None:
    """Set up the logging.

    This method must be run in the event loop.
    """
    fmt = ("%(asctime)s %(levelname)s (%(threadName)s) "
           "[%(name)s] %(message)s")
    datefmt = '%Y-%m-%d %H:%M:%S'

    if not log_no_color:
        try:
            from colorlog import ColoredFormatter
            # basicConfig must be called after importing colorlog in order to
            # ensure that the handlers it sets up wraps the correct streams.
            logging.basicConfig(level=logging.INFO)

            colorfmt = "%(log_color)s{}%(reset)s".format(fmt)
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

    # If the above initialization failed for any reason, setup the default
    # formatting.  If the above succeeds, this wil result in a no-op.
    logging.basicConfig(format=fmt, datefmt=datefmt, level=logging.INFO)

    # Suppress overly verbose logs from libraries that aren't helpful
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

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
                err_log_path, when='midnight',
                backupCount=log_rotate_days)  # type: logging.FileHandler
        else:
            err_handler = logging.FileHandler(
                err_log_path, mode='w', delay=True)

        err_handler.setLevel(logging.INFO if verbose else logging.WARNING)
        err_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

        async_handler = AsyncHandler(hass.loop, err_handler)

        async def async_stop_async_handler(_: Any) -> None:
            """Cleanup async handler."""
            logging.getLogger('').removeHandler(async_handler)  # type: ignore
            await async_handler.async_close(blocking=True)

        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_CLOSE, async_stop_async_handler)

        logger = logging.getLogger('')
        logger.addHandler(async_handler)  # type: ignore
        logger.setLevel(logging.INFO)

        # Save the log file location for access by other components.
        hass.data[DATA_LOGGING] = err_log_path
    else:
        _LOGGER.error(
            "Unable to set up error log %s (access denied)", err_log_path)


async def async_mount_local_lib_path(config_dir: str) -> str:
    """Add local library to Python Path.

    This function is a coroutine.
    """
    deps_dir = os.path.join(config_dir, 'deps')
    lib_dir = await async_get_user_site(deps_dir)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    return deps_dir


@core.callback
def _get_components(hass: core.HomeAssistant,
                    config: Dict[str, Any]) -> Set[str]:
    """Get components to set up."""
    # Filter out the repeating and common config section [homeassistant]
    components = set(key.split(' ')[0] for key in config.keys()
                     if key != core.DOMAIN)

    # Add config entry domains
    components.update(hass.config_entries.async_domains())  # type: ignore

    # Make sure the Hass.io component is loaded
    if 'HASSIO' in os.environ:
        components.add('hassio')

    return components
