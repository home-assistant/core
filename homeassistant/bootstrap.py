"""Provide methods to bootstrap a Home Assistant instance."""
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta
import logging
import logging.handlers
import os
import platform
import sys
import threading
from time import monotonic
from typing import TYPE_CHECKING, Any

import voluptuous as vol
import yarl

from . import config as conf_util, config_entries, core, loader
from .components import http
from .const import (
    REQUIRED_NEXT_PYTHON_HA_RELEASE,
    REQUIRED_NEXT_PYTHON_VER,
    SIGNAL_BOOTSTRAP_INTEGRATIONS,
)
from .exceptions import HomeAssistantError
from .helpers import (
    area_registry,
    device_registry,
    entity_registry,
    issue_registry,
    recorder,
)
from .helpers.dispatcher import async_dispatcher_send
from .helpers.typing import ConfigType
from .setup import (
    DATA_SETUP,
    DATA_SETUP_STARTED,
    DATA_SETUP_TIME,
    async_set_domains_to_be_loaded,
    async_setup_component,
)
from .util import dt as dt_util
from .util.logging import async_activate_log_queue_handler
from .util.package import async_get_user_site, is_virtual_env

if TYPE_CHECKING:
    from .runner import RuntimeConfig

_LOGGER = logging.getLogger(__name__)

ERROR_LOG_FILENAME = "home-assistant.log"

# hass.data key for logging information.
DATA_LOGGING = "logging"
DATA_REGISTRIES_LOADED = "bootstrap_registries_loaded"

LOG_SLOW_STARTUP_INTERVAL = 60
SLOW_STARTUP_CHECK_INTERVAL = 1

STAGE_1_TIMEOUT = 120
STAGE_2_TIMEOUT = 300
WRAP_UP_TIMEOUT = 300
COOLDOWN_TIME = 60

MAX_LOAD_CONCURRENTLY = 6

DEBUGGER_INTEGRATIONS = {"debugpy"}
CORE_INTEGRATIONS = {"homeassistant", "persistent_notification"}
LOGGING_INTEGRATIONS = {
    # Set log levels
    "logger",
    # Error logging
    "system_log",
    "sentry",
}
FRONTEND_INTEGRATIONS = {
    # Get the frontend up and running as soon as possible so problem
    # integrations can be removed and database migration status is
    # visible in frontend
    "frontend",
}
RECORDER_INTEGRATIONS = {
    # Setup after frontend
    # To record data
    "recorder",
}
DISCOVERY_INTEGRATIONS = ("bluetooth", "dhcp", "ssdp", "usb", "zeroconf")
STAGE_1_INTEGRATIONS = {
    # We need to make sure discovery integrations
    # update their deps before stage 2 integrations
    # load them inadvertently before their deps have
    # been updated which leads to using an old version
    # of the dep, or worse (import errors).
    *DISCOVERY_INTEGRATIONS,
    # To make sure we forward data to other instances
    "mqtt_eventstream",
    # To provide account link implementations
    "cloud",
    # Ensure supervisor is available
    "hassio",
}


async def async_setup_hass(
    runtime_config: RuntimeConfig,
) -> core.HomeAssistant | None:
    """Set up Home Assistant."""
    hass = core.HomeAssistant()
    hass.config.config_dir = runtime_config.config_dir

    async_enable_logging(
        hass,
        runtime_config.verbose,
        runtime_config.log_rotate_days,
        runtime_config.log_file,
        runtime_config.log_no_color,
    )

    hass.config.skip_pip = runtime_config.skip_pip
    hass.config.skip_pip_packages = runtime_config.skip_pip_packages
    if runtime_config.skip_pip or runtime_config.skip_pip_packages:
        _LOGGER.warning(
            "Skipping pip installation of required modules. This may cause issues"
        )

    if not await conf_util.async_ensure_config_exists(hass):
        _LOGGER.error("Error getting configuration path")
        return None

    _LOGGER.info("Config directory: %s", runtime_config.config_dir)

    config_dict = None
    basic_setup_success = False

    if not (safe_mode := runtime_config.safe_mode):
        await hass.async_add_executor_job(conf_util.process_ha_config_upgrade, hass)

        try:
            config_dict = await conf_util.async_hass_config_yaml(hass)
        except HomeAssistantError as err:
            _LOGGER.error(
                "Failed to parse configuration.yaml: %s. Activating safe mode",
                err,
            )
        else:
            if not is_virtual_env():
                await async_mount_local_lib_path(runtime_config.config_dir)

            basic_setup_success = (
                await async_from_config_dict(config_dict, hass) is not None
            )

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
        with contextlib.suppress(asyncio.TimeoutError):
            async with hass.timeout.async_timeout(10):
                await hass.async_stop()

        safe_mode = True
        old_config = hass.config
        old_logging = hass.data.get(DATA_LOGGING)

        hass = core.HomeAssistant()
        if old_logging:
            hass.data[DATA_LOGGING] = old_logging
        hass.config.skip_pip = old_config.skip_pip
        hass.config.skip_pip_packages = old_config.skip_pip_packages
        hass.config.internal_url = old_config.internal_url
        hass.config.external_url = old_config.external_url
        hass.config.config_dir = old_config.config_dir

    if safe_mode:
        _LOGGER.info("Starting in safe mode")
        hass.config.safe_mode = True

        http_conf = (await http.async_get_last_config(hass)) or {}

        await async_from_config_dict(
            {"safe_mode": {}, "http": http_conf},
            hass,
        )

    if runtime_config.open_ui:
        hass.add_job(open_hass_ui, hass)

    return hass


def open_hass_ui(hass: core.HomeAssistant) -> None:
    """Open the UI."""
    import webbrowser  # pylint: disable=import-outside-toplevel

    if hass.config.api is None or "frontend" not in hass.config.components:
        _LOGGER.warning("Cannot launch the UI because frontend not loaded")
        return

    scheme = "https" if hass.config.api.use_ssl else "http"
    url = str(
        yarl.URL.build(scheme=scheme, host="127.0.0.1", port=hass.config.api.port)
    )

    if not webbrowser.open(url):
        _LOGGER.warning(
            "Unable to open the Home Assistant UI in a browser. Open it yourself at %s",
            url,
        )


async def load_registries(hass: core.HomeAssistant) -> None:
    """Load the registries and cache the result of platform.uname().processor."""
    if DATA_REGISTRIES_LOADED in hass.data:
        return
    hass.data[DATA_REGISTRIES_LOADED] = None

    def _cache_uname_processor() -> None:
        """Cache the result of platform.uname().processor in the executor.

        Multiple modules call this function at startup which
        executes a blocking subprocess call. This is a problem for the
        asyncio event loop. By primeing the cache of uname we can
        avoid the blocking call in the event loop.
        """
        platform.uname().processor  # pylint: disable=expression-not-assigned

    # Load the registries and cache the result of platform.uname().processor
    await asyncio.gather(
        area_registry.async_load(hass),
        device_registry.async_load(hass),
        entity_registry.async_load(hass),
        issue_registry.async_load(hass),
        hass.async_add_executor_job(_cache_uname_processor),
    )


async def async_from_config_dict(
    config: ConfigType, hass: core.HomeAssistant
) -> core.HomeAssistant | None:
    """Try to configure Home Assistant from a configuration dictionary.

    Dynamically loads required components and its dependencies.
    This method is a coroutine.
    """
    start = monotonic()

    hass.config_entries = config_entries.ConfigEntries(hass, config)
    await hass.config_entries.async_initialize()
    await load_registries(hass)

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

    if (
        REQUIRED_NEXT_PYTHON_HA_RELEASE
        and sys.version_info[:3] < REQUIRED_NEXT_PYTHON_VER
    ):
        current_python_version = ".".join(str(x) for x in sys.version_info[:3])
        required_python_version = ".".join(str(x) for x in REQUIRED_NEXT_PYTHON_VER[:2])
        _LOGGER.warning(
            (
                "Support for the running Python version %s is deprecated and "
                "will be removed in Home Assistant %s; "
                "Please upgrade Python to %s"
            ),
            current_python_version,
            REQUIRED_NEXT_PYTHON_HA_RELEASE,
            required_python_version,
        )
        issue_registry.async_create_issue(
            hass,
            core.DOMAIN,
            "python_version",
            is_fixable=False,
            severity=issue_registry.IssueSeverity.WARNING,
            breaks_in_ha_version=REQUIRED_NEXT_PYTHON_HA_RELEASE,
            translation_key="python_version",
            translation_placeholders={
                "current_python_version": current_python_version,
                "required_python_version": required_python_version,
                "breaks_in_ha_version": REQUIRED_NEXT_PYTHON_HA_RELEASE,
            },
        )

    return hass


@core.callback
def async_enable_logging(
    hass: core.HomeAssistant,
    verbose: bool = False,
    log_rotate_days: int | None = None,
    log_file: str | None = None,
    log_no_color: bool = False,
) -> None:
    """Set up the logging.

    This method must be run in the event loop.
    """
    fmt = (
        "%(asctime)s.%(msecs)03d %(levelname)s (%(threadName)s) [%(name)s] %(message)s"
    )
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
        "Uncaught exception", exc_info=args  # type: ignore[arg-type]
    )
    threading.excepthook = lambda args: logging.getLogger(None).exception(
        "Uncaught thread exception",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),  # type: ignore[arg-type]
    )

    # Log errors to a file if we have write access to file or config dir
    if log_file is None:
        err_log_path = hass.config.path(ERROR_LOG_FILENAME)
    else:
        err_log_path = os.path.abspath(log_file)

    err_path_exists = os.path.isfile(err_log_path)
    err_dir = os.path.dirname(err_log_path)

    # Check if we can write to the error log if it exists or that
    # we can create files in the containing directory if not.
    if (err_path_exists and os.access(err_log_path, os.W_OK)) or (
        not err_path_exists and os.access(err_dir, os.W_OK)
    ):

        err_handler: logging.handlers.RotatingFileHandler | logging.handlers.TimedRotatingFileHandler
        if log_rotate_days:
            err_handler = logging.handlers.TimedRotatingFileHandler(
                err_log_path, when="midnight", backupCount=log_rotate_days
            )
        else:
            err_handler = logging.handlers.RotatingFileHandler(
                err_log_path, backupCount=1
            )

        try:
            err_handler.doRollover()
        except OSError as err:
            _LOGGER.error("Error rolling over log file: %s", err)

        err_handler.setLevel(logging.INFO if verbose else logging.WARNING)
        err_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

        logger = logging.getLogger("")
        logger.addHandler(err_handler)
        logger.setLevel(logging.INFO if verbose else logging.WARNING)

        # Save the log file location for access by other components.
        hass.data[DATA_LOGGING] = err_log_path
    else:
        _LOGGER.error("Unable to set up error log %s (access denied)", err_log_path)

    async_activate_log_queue_handler(hass)


async def async_mount_local_lib_path(config_dir: str) -> str:
    """Add local library to Python Path.

    This function is a coroutine.
    """
    deps_dir = os.path.join(config_dir, "deps")
    if (lib_dir := await async_get_user_site(deps_dir)) not in sys.path:
        sys.path.insert(0, lib_dir)
    return deps_dir


@core.callback
def _get_domains(hass: core.HomeAssistant, config: dict[str, Any]) -> set[str]:
    """Get domains of components to set up."""
    # Filter out the repeating and common config section [homeassistant]
    domains = {key.partition(" ")[0] for key in config if key != core.DOMAIN}

    # Add config entry domains
    if not hass.config.safe_mode:
        domains.update(hass.config_entries.async_domains())

    # Make sure the Hass.io component is loaded
    if "SUPERVISOR" in os.environ:
        domains.add("hassio")

    return domains


async def _async_watch_pending_setups(hass: core.HomeAssistant) -> None:
    """Periodic log of setups that are pending for longer than LOG_SLOW_STARTUP_INTERVAL."""
    loop_count = 0
    setup_started: dict[str, datetime] = hass.data[DATA_SETUP_STARTED]
    previous_was_empty = True
    while True:
        now = dt_util.utcnow()
        remaining_with_setup_started = {
            domain: (now - setup_started[domain]).total_seconds()
            for domain in setup_started
        }
        _LOGGER.debug("Integration remaining: %s", remaining_with_setup_started)
        if remaining_with_setup_started or not previous_was_empty:
            async_dispatcher_send(
                hass, SIGNAL_BOOTSTRAP_INTEGRATIONS, remaining_with_setup_started
            )
        previous_was_empty = not remaining_with_setup_started
        await asyncio.sleep(SLOW_STARTUP_CHECK_INTERVAL)
        loop_count += SLOW_STARTUP_CHECK_INTERVAL

        if loop_count >= LOG_SLOW_STARTUP_INTERVAL and setup_started:
            _LOGGER.warning(
                "Waiting on integrations to complete setup: %s",
                ", ".join(setup_started),
            )
            loop_count = 0
        _LOGGER.debug("Running timeout Zones: %s", hass.timeout.zones)


async def async_setup_multi_components(
    hass: core.HomeAssistant,
    domains: set[str],
    config: dict[str, Any],
) -> None:
    """Set up multiple domains. Log on failure."""
    futures = {
        domain: hass.async_create_task(async_setup_component(hass, domain, config))
        for domain in domains
    }
    await asyncio.wait(futures.values())
    errors = [domain for domain in domains if futures[domain].exception()]
    for domain in errors:
        exception = futures[domain].exception()
        assert exception is not None
        _LOGGER.error(
            "Error setting up integration %s - received exception",
            domain,
            exc_info=(type(exception), exception, exception.__traceback__),
        )


async def _async_set_up_integrations(
    hass: core.HomeAssistant, config: dict[str, Any]
) -> None:
    """Set up all the integrations."""
    hass.data[DATA_SETUP_STARTED] = {}
    setup_time: dict[str, timedelta] = hass.data.setdefault(DATA_SETUP_TIME, {})

    watch_task = asyncio.create_task(_async_watch_pending_setups(hass))

    domains_to_setup = _get_domains(hass, config)

    # Resolve all dependencies so we know all integrations
    # that will have to be loaded and start rightaway
    integration_cache: dict[str, loader.Integration] = {}
    to_resolve: set[str] = domains_to_setup
    while to_resolve:
        old_to_resolve: set[str] = to_resolve
        to_resolve = set()

        integrations_to_process = [
            int_or_exc
            for int_or_exc in (
                await loader.async_get_integrations(hass, old_to_resolve)
            ).values()
            if isinstance(int_or_exc, loader.Integration)
        ]
        resolve_dependencies_tasks = [
            itg.resolve_dependencies()
            for itg in integrations_to_process
            if not itg.all_dependencies_resolved
        ]

        if resolve_dependencies_tasks:
            await asyncio.gather(*resolve_dependencies_tasks)

        for itg in integrations_to_process:
            integration_cache[itg.domain] = itg

            for dep in itg.all_dependencies:
                if dep in domains_to_setup:
                    continue

                domains_to_setup.add(dep)
                to_resolve.add(dep)

    _LOGGER.info("Domains to be set up: %s", domains_to_setup)

    # Initialize recorder
    if "recorder" in domains_to_setup:
        recorder.async_initialize_recorder(hass)

    # Load logging as soon as possible
    if logging_domains := domains_to_setup & LOGGING_INTEGRATIONS:
        _LOGGER.info("Setting up logging: %s", logging_domains)
        await async_setup_multi_components(hass, logging_domains, config)

    # Setup frontend
    if frontend_domains := domains_to_setup & FRONTEND_INTEGRATIONS:
        _LOGGER.info("Setting up frontend: %s", frontend_domains)
        await async_setup_multi_components(hass, frontend_domains, config)

    # Setup recorder
    if recorder_domains := domains_to_setup & RECORDER_INTEGRATIONS:
        _LOGGER.info("Setting up recorder: %s", recorder_domains)
        await async_setup_multi_components(hass, recorder_domains, config)

    # Start up debuggers. Start these first in case they want to wait.
    if debuggers := domains_to_setup & DEBUGGER_INTEGRATIONS:
        _LOGGER.debug("Setting up debuggers: %s", debuggers)
        await async_setup_multi_components(hass, debuggers, config)

    # calculate what components to setup in what stage
    stage_1_domains: set[str] = set()

    # Find all dependencies of any dependency of any stage 1 integration that
    # we plan on loading and promote them to stage 1. This is done only to not
    # get misleading log messages
    deps_promotion: set[str] = STAGE_1_INTEGRATIONS
    while deps_promotion:
        old_deps_promotion = deps_promotion
        deps_promotion = set()

        for domain in old_deps_promotion:
            if domain not in domains_to_setup or domain in stage_1_domains:
                continue

            stage_1_domains.add(domain)

            if (dep_itg := integration_cache.get(domain)) is None:
                continue

            deps_promotion.update(dep_itg.all_dependencies)

    stage_2_domains = (
        domains_to_setup
        - logging_domains
        - frontend_domains
        - recorder_domains
        - debuggers
        - stage_1_domains
    )

    # Start setup
    if stage_1_domains:
        _LOGGER.info("Setting up stage 1: %s", stage_1_domains)
        try:
            async with hass.timeout.async_timeout(
                STAGE_1_TIMEOUT, cool_down=COOLDOWN_TIME
            ):
                await async_setup_multi_components(hass, stage_1_domains, config)
        except asyncio.TimeoutError:
            _LOGGER.warning("Setup timed out for stage 1 - moving forward")

    # Enables after dependencies
    async_set_domains_to_be_loaded(hass, stage_2_domains)

    if stage_2_domains:
        _LOGGER.info("Setting up stage 2: %s", stage_2_domains)
        try:
            async with hass.timeout.async_timeout(
                STAGE_2_TIMEOUT, cool_down=COOLDOWN_TIME
            ):
                await async_setup_multi_components(hass, stage_2_domains, config)
        except asyncio.TimeoutError:
            _LOGGER.warning("Setup timed out for stage 2 - moving forward")

    # Wrap up startup
    _LOGGER.debug("Waiting for startup to wrap up")
    try:
        async with hass.timeout.async_timeout(WRAP_UP_TIMEOUT, cool_down=COOLDOWN_TIME):
            await hass.async_block_till_done()
    except asyncio.TimeoutError:
        _LOGGER.warning("Setup timed out for bootstrap - moving forward")

    watch_task.cancel()
    async_dispatcher_send(hass, SIGNAL_BOOTSTRAP_INTEGRATIONS, {})

    _LOGGER.debug(
        "Integration setup times: %s",
        {
            integration: timedelta.total_seconds()
            for integration, timedelta in sorted(
                setup_time.items(), key=lambda item: item[1].total_seconds()
            )
        },
    )
