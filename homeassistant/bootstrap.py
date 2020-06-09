"""Provide methods to bootstrap a Home Assistant instance."""
import asyncio
import contextlib
import logging
import logging.handlers
import os
import sys
from time import monotonic
from typing import Any, Dict, Optional, Set

from async_timeout import timeout
import voluptuous as vol

from homeassistant import config as conf_util, config_entries, core, loader
from homeassistant.components import http
from homeassistant.const import (
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_HOMEASSISTANT_STOP,
    REQUIRED_NEXT_PYTHON_DATE,
    REQUIRED_NEXT_PYTHON_VER,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import DATA_SETUP, async_setup_component
from homeassistant.util.logging import AsyncHandler
from homeassistant.util.package import async_get_user_site, is_virtual_env
from homeassistant.util.yaml import clear_secret_cache

_LOGGER = logging.getLogger(__name__)

ERROR_LOG_FILENAME = "home-assistant.log"

# hass.data key for logging information.
DATA_LOGGING = "logging"

DEBUGGER_INTEGRATIONS = {"ptvsd"}
CORE_INTEGRATIONS = ("homeassistant", "persistent_notification")
LOGGING_INTEGRATIONS = {"logger", "system_log", "sentry"}
STAGE_1_INTEGRATIONS = {
    # To record data
    "recorder",
    # To make sure we forward data to other instances
    "mqtt_eventstream",
    # To provide account link implementations
    "cloud",
}


async def async_setup_hass(
    *,
    config_dir: str,
    verbose: bool,
    log_rotate_days: int,
    log_file: str,
    log_no_color: bool,
    skip_pip: bool,
    safe_mode: bool,
) -> Optional[core.HomeAssistant]:
    """Set up Home Assistant."""
    hass = core.HomeAssistant()
    hass.config.config_dir = config_dir

    async_enable_logging(hass, verbose, log_rotate_days, log_file, log_no_color)

    hass.config.skip_pip = skip_pip
    if skip_pip:
        _LOGGER.warning(
            "Skipping pip installation of required modules. This may cause issues"
        )

    if not await conf_util.async_ensure_config_exists(hass):
        _LOGGER.error("Error getting configuration path")
        return None

    _LOGGER.info("Config directory: %s", config_dir)

    config_dict = None
    basic_setup_success = False

    if not safe_mode:
        await hass.async_add_executor_job(conf_util.process_ha_config_upgrade, hass)

        try:
            config_dict = await conf_util.async_hass_config_yaml(hass)
        except HomeAssistantError as err:
            _LOGGER.error(
                "Failed to parse configuration.yaml: %s. Activating safe mode", err
            )
        else:
            if not is_virtual_env():
                await async_mount_local_lib_path(config_dir)

            basic_setup_success = (
                await async_from_config_dict(config_dict, hass) is not None
            )
        finally:
            clear_secret_cache()

    if config_dict is None:
        safe_mode = True

    elif not basic_setup_success:
        _LOGGER.warning("Unable to set up core integrations. Activating safe mode")
        safe_mode = True

    elif (
        "frontend" in hass.data.get(DATA_SETUP, {})
        and "frontend" not in hass.config.components
    ):
        _LOGGER.warning("Detected that frontend did not load. Activating safe mode")
        # Ask integrations to shut down. It's messy but we can't
        # do a clean stop without knowing what is broken
        hass.async_track_tasks()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP, {})
        with contextlib.suppress(asyncio.TimeoutError):
            async with timeout(10):
                await hass.async_block_till_done()

        safe_mode = True
        hass = core.HomeAssistant()
        hass.config.config_dir = config_dir

    if safe_mode:
        _LOGGER.info("Starting in AIS dom safe mode")
        hass.config.safe_mode = True

        ais_conf = await (conf_util.async_ais_config_yaml(hass)) or {}
        # http_conf = (await http.async_get_last_config(hass)) or {}

        await async_from_config_dict({"safe_mode": {}, "http": ais_conf["http"]}, hass)

    return hass


async def async_from_config_dict(
    config: ConfigType, hass: core.HomeAssistant
) -> Optional[core.HomeAssistant]:
    """Try to configure Home Assistant from a configuration dictionary.

    Dynamically loads required components and its dependencies.
    This method is a coroutine.
    """
    start = monotonic()

    hass.config_entries = config_entries.ConfigEntries(hass, config)
    await hass.config_entries.async_initialize()

    # Set up core.
    _LOGGER.debug("Setting up %s", CORE_INTEGRATIONS)

    if not all(
        await asyncio.gather(
            *(
                async_setup_component(hass, domain, config)
                for domain in CORE_INTEGRATIONS
            )
        )
    ):
        _LOGGER.error("Home Assistant core failed to initialize. ")
        return None

    _LOGGER.debug("Home Assistant core initialized")

    core_config = config.get(core.DOMAIN, {})

    try:
        await conf_util.async_process_ha_core_config(hass, core_config)
    except vol.Invalid as config_err:
        conf_util.async_log_exception(config_err, "homeassistant", core_config, hass)
        return None
    except HomeAssistantError:
        _LOGGER.error(
            "Home Assistant core failed to initialize. "
            "Further initialization aborted"
        )
        return None

    await _async_set_up_integrations(hass, config)

    stop = monotonic()
    _LOGGER.info("Home Assistant initialized in %.2fs", stop - start)
    from homeassistant.components.ais_dom import ais_global

    ais_global.say_direct(
        "Asystent domowy, inicjalizacja: %.2f sekundy. Trwa uruchamianie konfiguracji. Poczekaj..."
        % (stop - start)
    )

    if REQUIRED_NEXT_PYTHON_DATE and sys.version_info[:3] < REQUIRED_NEXT_PYTHON_VER:
        msg = (
            "Support for the running Python version "
            f"{'.'.join(str(x) for x in sys.version_info[:3])} is deprecated and will "
            f"be removed in the first release after {REQUIRED_NEXT_PYTHON_DATE}. "
            "Please upgrade Python to "
            f"{'.'.join(str(x) for x in REQUIRED_NEXT_PYTHON_VER)} or "
            "higher."
        )
        _LOGGER.warning(msg)
        hass.components.persistent_notification.async_create(
            msg, "Python version", "python_version"
        )

    return hass


@core.callback
def async_enable_logging(
    hass: core.HomeAssistant,
    verbose: bool = False,
    log_rotate_days: Optional[int] = None,
    log_file: Optional[str] = None,
    log_no_color: bool = False,
) -> None:
    """Set up the logging.

    This method must be run in the event loop.
    """
    fmt = "%(asctime)s %(levelname)s (%(threadName)s) [%(name)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    if not log_no_color:
        try:
            # pylint: disable=import-outside-toplevel
            from colorlog import ColoredFormatter

            # basicConfig must be called after importing colorlog in order to
            # ensure that the handlers it sets up wraps the correct streams.
            logging.basicConfig(level=logging.INFO)

            colorfmt = f"%(log_color)s{fmt}%(reset)s"
            logging.getLogger().handlers[0].setFormatter(
                ColoredFormatter(
                    colorfmt,
                    datefmt=datefmt,
                    reset=True,
                    log_colors={
                        "DEBUG": "cyan",
                        "INFO": "green",
                        "WARNING": "yellow",
                        "ERROR": "red",
                        "CRITICAL": "red",
                    },
                )
            )
        except ImportError:
            pass

    # If the above initialization failed for any reason, setup the default
    # formatting.  If the above succeeds, this will result in a no-op.
    logging.basicConfig(format=fmt, datefmt=datefmt, level=logging.INFO)

    # Suppress overly verbose logs from libraries that aren't helpful
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

    sys.excepthook = lambda *args: logging.getLogger(None).exception(
        "Uncaught exception", exc_info=args  # type: ignore
    )

    # AIS dom fix
    try:
        import json
        from homeassistant.components.ais_dom import ais_global

        with open(
            "/data/data/pl.sviete.dom/files/home/AIS/.dom/.ais_log_settings_info"
        ) as json_file:
            ais_logs_settings = json.load(json_file)
            log_drive = ais_logs_settings["logDrive"]
    except Exception:
        # no log settings file is present
        return
    log_rotate_days = 10
    if "logRotating" in ais_logs_settings:
        log_rotate_days = ais_logs_settings["logRotating"]
    log_file = ais_global.G_REMOTE_DRIVES_DOM_PATH + "/" + log_drive + "/ais.log"
    # Log errors to a file if we have write access to file or config dir
    err_log_path = os.path.abspath(log_file)

    err_path_exists = os.path.isfile(err_log_path)
    err_dir = os.path.dirname(err_log_path)
    # check if this is correct external drive
    from homeassistant.components import ais_usb

    err_path_is_external_drive = ais_usb.is_usb_url_valid_external_drive(err_dir)

    # Check if we can write to the error log if it exists or that
    # we can create files in the containing directory if not.
    if err_path_is_external_drive and (
        (err_path_exists and os.access(err_log_path, os.W_OK))
        or (not err_path_exists and os.access(err_dir, os.W_OK))
    ):

        if log_rotate_days:
            err_handler: logging.FileHandler = logging.handlers.TimedRotatingFileHandler(
                err_log_path, when="midnight", backupCount=int(log_rotate_days)
            )
        else:
            err_handler = logging.FileHandler(err_log_path, mode="w", delay=True)

        err_handler.setLevel(logging.INFO if verbose else logging.WARNING)
        err_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

        async_handler = AsyncHandler(hass.loop, err_handler)

        async def async_stop_async_handler(_: Any) -> None:
            """Cleanup async handler."""
            print("Cleanup async handler.")
            # just to be sure
            log = logging.getLogger()  # root logger
            log.disabled = True
            for hdlr in log.handlers[:]:  # remove all old handlers
                hdlr.flush()
                hdlr.close()
                log.removeHandler(hdlr)
            logging.getLogger("").removeHandler(async_handler)  # type: ignore
            await async_handler.async_close(blocking=True)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, async_stop_async_handler)
        hass.bus.async_listen("ais_stop_logs_event", async_stop_async_handler)

        logger = logging.getLogger("")
        logger.addHandler(async_handler)  # type: ignore
        logger.setLevel(logging.INFO)

        # Save the log file location for access by other components.
        hass.data[DATA_LOGGING] = err_log_path
    else:
        _LOGGER.error("Unable to set up error log %s (access denied)", err_log_path)


async def async_mount_local_lib_path(config_dir: str) -> str:
    """Add local library to Python Path.

    This function is a coroutine.
    """
    deps_dir = os.path.join(config_dir, "deps")
    lib_dir = await async_get_user_site(deps_dir)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    return deps_dir


@core.callback
def _get_domains(hass: core.HomeAssistant, config: Dict[str, Any]) -> Set[str]:
    """Get domains of components to set up."""
    # Filter out the repeating and common config section [homeassistant]
    domains = {key.split(" ")[0] for key in config.keys() if key != core.DOMAIN}

    # Add config entry domains
    if not hass.config.safe_mode:
        domains.update(hass.config_entries.async_domains())

    # Make sure the Hass.io component is loaded
    if "HASSIO" in os.environ:
        domains.add("hassio")

    return domains


async def _async_set_up_integrations(
    hass: core.HomeAssistant, config: Dict[str, Any]
) -> None:
    """Set up all the integrations."""

    async def async_setup_multi_components(domains: Set[str]) -> None:
        """Set up multiple domains. Log on failure."""
        futures = {
            domain: hass.async_create_task(async_setup_component(hass, domain, config))
            for domain in domains
        }
        await asyncio.wait(futures.values())
        errors = [domain for domain in domains if futures[domain].exception()]
        for domain in errors:
            exception = futures[domain].exception()
            _LOGGER.error(
                "Error setting up integration %s - received exception",
                domain,
                exc_info=(type(exception), exception, exception.__traceback__),
            )

    domains = _get_domains(hass, config)

    # Start up debuggers. Start these first in case they want to wait.
    debuggers = domains & DEBUGGER_INTEGRATIONS
    if debuggers:
        _LOGGER.debug("Starting up debuggers %s", debuggers)
        await async_setup_multi_components(debuggers)
        domains -= DEBUGGER_INTEGRATIONS

    # Resolve all dependencies of all components so we can find the logging
    # and integrations that need faster initialization.
    resolved_domains_task = asyncio.gather(
        *(loader.async_component_dependencies(hass, domain) for domain in domains),
        return_exceptions=True,
    )

    # Finish resolving domains
    for dep_domains in await resolved_domains_task:
        # Result is either a set or an exception. We ignore exceptions
        # It will be properly handled during setup of the domain.
        if isinstance(dep_domains, set):
            domains.update(dep_domains)

    # setup components
    logging_domains = domains & LOGGING_INTEGRATIONS
    stage_1_domains = domains & STAGE_1_INTEGRATIONS
    stage_2_domains = domains - logging_domains - stage_1_domains

    if logging_domains:
        _LOGGER.info("Setting up %s", logging_domains)

        await async_setup_multi_components(logging_domains)

    # Kick off loading the registries. They don't need to be awaited.
    asyncio.gather(
        hass.helpers.device_registry.async_get_registry(),
        hass.helpers.entity_registry.async_get_registry(),
        hass.helpers.area_registry.async_get_registry(),
    )

    if stage_1_domains:
        await async_setup_multi_components(stage_1_domains)

    # Load all integrations
    after_dependencies: Dict[str, Set[str]] = {}

    for int_or_exc in await asyncio.gather(
        *(loader.async_get_integration(hass, domain) for domain in stage_2_domains),
        return_exceptions=True,
    ):
        # Exceptions are handled in async_setup_component.
        if isinstance(int_or_exc, loader.Integration) and int_or_exc.after_dependencies:
            after_dependencies[int_or_exc.domain] = set(int_or_exc.after_dependencies)

    last_load = None
    while stage_2_domains:
        domains_to_load = set()

        for domain in stage_2_domains:
            after_deps = after_dependencies.get(domain)
            # Load if integration has no after_dependencies or they are
            # all loaded
            if not after_deps or not after_deps - hass.config.components:
                domains_to_load.add(domain)

        if not domains_to_load or domains_to_load == last_load:
            break

        _LOGGER.debug("Setting up %s", domains_to_load)

        await async_setup_multi_components(domains_to_load)

        last_load = domains_to_load
        stage_2_domains -= domains_to_load

    # These are stage 2 domains that never have their after_dependencies
    # satisfied.
    if stage_2_domains:
        _LOGGER.debug("Final set up: %s", stage_2_domains)

        await async_setup_multi_components(stage_2_domains)

    # Wrap up startup
    await hass.async_block_till_done()
