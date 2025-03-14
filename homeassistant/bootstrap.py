"""Provide methods to bootstrap a Home Assistant instance."""

from __future__ import annotations

import asyncio
from collections import defaultdict
import contextlib
from functools import partial
from itertools import chain
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import mimetypes
from operator import contains, itemgetter
import os
import platform
import sys
import threading
from time import monotonic
from typing import TYPE_CHECKING, Any

# Import cryptography early since import openssl is not thread-safe
# _frozen_importlib._DeadlockError: deadlock detected by _ModuleLock('cryptography.hazmat.backends.openssl.backend')
import cryptography.hazmat.backends.openssl.backend  # noqa: F401
import voluptuous as vol
import yarl

from . import (
    block_async_io,
    config as conf_util,
    config_entries,
    core,
    loader,
    requirements,
)

# Pre-import frontend deps which have no requirements here to avoid
# loading them at run time and blocking the event loop. We do this ahead
# of time so that we do not have to flag frontend deps with `import_executor`
# as it would create a thundering heard of executor jobs trying to import
# frontend deps at the same time.
from .components import (
    api as api_pre_import,  # noqa: F401
    auth as auth_pre_import,  # noqa: F401
    config as config_pre_import,  # noqa: F401
    default_config as default_config_pre_import,  # noqa: F401
    device_automation as device_automation_pre_import,  # noqa: F401
    diagnostics as diagnostics_pre_import,  # noqa: F401
    file_upload as file_upload_pre_import,  # noqa: F401
    group as group_pre_import,  # noqa: F401
    history as history_pre_import,  # noqa: F401
    http,  # not named pre_import since it has requirements
    image_upload as image_upload_import,  # noqa: F401 - not named pre_import since it has requirements
    logbook as logbook_pre_import,  # noqa: F401
    lovelace as lovelace_pre_import,  # noqa: F401
    onboarding as onboarding_pre_import,  # noqa: F401
    recorder as recorder_import,  # noqa: F401 - not named pre_import since it has requirements
    repairs as repairs_pre_import,  # noqa: F401
    search as search_pre_import,  # noqa: F401
    sensor as sensor_pre_import,  # noqa: F401
    system_log as system_log_pre_import,  # noqa: F401
    webhook as webhook_pre_import,  # noqa: F401
    websocket_api as websocket_api_pre_import,  # noqa: F401
)
from .components.sensor import recorder as sensor_recorder  # noqa: F401
from .const import (
    BASE_PLATFORMS,
    FORMAT_DATETIME,
    KEY_DATA_LOGGING as DATA_LOGGING,
    REQUIRED_NEXT_PYTHON_HA_RELEASE,
    REQUIRED_NEXT_PYTHON_VER,
    SIGNAL_BOOTSTRAP_INTEGRATIONS,
)
from .core_config import async_process_ha_core_config
from .exceptions import HomeAssistantError
from .helpers import (
    area_registry,
    backup,
    category_registry,
    config_validation as cv,
    device_registry,
    entity,
    entity_registry,
    floor_registry,
    frame,
    issue_registry,
    label_registry,
    recorder,
    restore_state,
    template,
    translation,
)
from .helpers.dispatcher import async_dispatcher_send_internal
from .helpers.storage import get_internal_store_manager
from .helpers.system_info import async_get_system_info
from .helpers.typing import ConfigType
from .loader import Integration
from .setup import (
    # _setup_started is marked as protected to make it clear
    # that it is not part of the public API and should not be used
    # by integrations. It is only used for internal tracking of
    # which integrations are being set up.
    _setup_started,
    async_get_setup_timings,
    async_notify_setup_error,
    async_set_domains_to_be_loaded,
    async_setup_component,
)
from .util.async_ import create_eager_task
from .util.hass_dict import HassKey
from .util.logging import async_activate_log_queue_handler
from .util.package import async_get_user_site, is_docker_env, is_virtual_env
from .util.system_info import is_official_image

with contextlib.suppress(ImportError):
    # Ensure anyio backend is imported to avoid it being imported in the event loop
    from anyio._backends import _asyncio  # noqa: F401

with contextlib.suppress(ImportError):
    # httpx will import trio if it is installed which does
    # blocking I/O in the event loop. We want to avoid that.
    import trio  # noqa: F401


if TYPE_CHECKING:
    from .runner import RuntimeConfig

_LOGGER = logging.getLogger(__name__)

SETUP_ORDER_SORT_KEY = partial(contains, BASE_PLATFORMS)


ERROR_LOG_FILENAME = "home-assistant.log"

# hass.data key for logging information.
DATA_REGISTRIES_LOADED: HassKey[None] = HassKey("bootstrap_registries_loaded")

LOG_SLOW_STARTUP_INTERVAL = 60
SLOW_STARTUP_CHECK_INTERVAL = 1

STAGE_0_SUBSTAGE_TIMEOUT = 60
STAGE_1_TIMEOUT = 120
STAGE_2_TIMEOUT = 300
WRAP_UP_TIMEOUT = 300
COOLDOWN_TIME = 60

# Core integrations are unconditionally loaded
CORE_INTEGRATIONS = {"homeassistant", "persistent_notification"}

# Integrations that are loaded right after the core is set up
LOGGING_AND_HTTP_DEPS_INTEGRATIONS = {
    # isal is loaded right away before `http` to ensure if its
    # enabled, that `isal` is up to date.
    "isal",
    # Set log levels
    "logger",
    # Ensure network config is available
    # before hassio or any other integration is
    # loaded that might create an aiohttp client session
    "network",
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
# Stage 0 is divided into substages. Each substage has a name, a set of integrations and a timeout.
# The substage containing recorder should have no timeout, as it could cancel a database migration.
# Recorder freezes "recorder" timeout during a migration, but it does not freeze other timeouts.
# The substages preceding it should also have no timeout, until we ensure that the recorder
# is not accidentally promoted as a dependency of any of the integrations in them.
# If we add timeouts to the frontend substages, we should make sure they don't apply in recovery mode.
STAGE_0_INTEGRATIONS = (
    # Load logging and http deps as soon as possible
    ("logging, http deps", LOGGING_AND_HTTP_DEPS_INTEGRATIONS, None),
    # Setup frontend
    ("frontend", FRONTEND_INTEGRATIONS, None),
    # Setup recorder
    ("recorder", {"recorder"}, None),
    # Start up debuggers. Start these first in case they want to wait.
    ("debugger", {"debugpy"}, STAGE_0_SUBSTAGE_TIMEOUT),
    # Zeroconf is used for mdns resolution in aiohttp client helper.
    ("zeroconf", {"zeroconf"}, STAGE_0_SUBSTAGE_TIMEOUT),
)

DISCOVERY_INTEGRATIONS = ("bluetooth", "dhcp", "ssdp", "usb")
# Stage 1 integrations are not to be preimported in bootstrap.
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

DEFAULT_INTEGRATIONS = {
    # These integrations are set up unless recovery mode is activated.
    #
    # Integrations providing core functionality:
    "analytics",  # Needed for onboarding
    "application_credentials",
    "backup",
    "frontend",
    "hardware",
    "logger",
    "network",
    "system_health",
    #
    # Key-feature:
    "automation",
    "person",
    "scene",
    "script",
    "tag",
    "zone",
    #
    # Built-in helpers:
    "counter",
    "input_boolean",
    "input_button",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "schedule",
    "timer",
}
DEFAULT_INTEGRATIONS_RECOVERY_MODE = {
    # These integrations are set up if recovery mode is activated.
    "frontend",
}
DEFAULT_INTEGRATIONS_SUPERVISOR = {
    # These integrations are set up if using the Supervisor
    "hassio",
}

CRITICAL_INTEGRATIONS = {
    # Recovery mode is activated if these integrations fail to set up
    "frontend",
}

#
# Storage keys we are likely to load during startup
# in order of when we expect to load them.
#
# If they do not exist they will not be loaded
#
PRELOAD_STORAGE = [
    "core.logger",
    "core.network",
    "http.auth",
    "image",
    "lovelace_dashboards",
    "lovelace_resources",
    "core.uuid",
    "lovelace.map",
    "bluetooth.passive_update_processor",
    "bluetooth.remote_scanners",
    "assist_pipeline.pipelines",
    "core.analytics",
    "auth_module.totp",
    "backup",
]


async def async_setup_hass(
    runtime_config: RuntimeConfig,
) -> core.HomeAssistant | None:
    """Set up Home Assistant."""

    async def create_hass() -> core.HomeAssistant:
        """Create the hass object and do basic setup."""
        hass = core.HomeAssistant(runtime_config.config_dir)
        loader.async_setup(hass)

        await async_enable_logging(
            hass,
            runtime_config.verbose,
            runtime_config.log_rotate_days,
            runtime_config.log_file,
            runtime_config.log_no_color,
        )

        if runtime_config.debug or hass.loop.get_debug():
            hass.config.debug = True

        hass.config.safe_mode = runtime_config.safe_mode
        hass.config.skip_pip = runtime_config.skip_pip
        hass.config.skip_pip_packages = runtime_config.skip_pip_packages

        return hass

    hass = await create_hass()

    if runtime_config.skip_pip or runtime_config.skip_pip_packages:
        _LOGGER.warning(
            "Skipping pip installation of required modules. This may cause issues"
        )

    if not await conf_util.async_ensure_config_exists(hass):
        _LOGGER.error("Error getting configuration path")
        return None

    _LOGGER.info("Config directory: %s", runtime_config.config_dir)

    block_async_io.enable()

    if not (recovery_mode := runtime_config.recovery_mode):
        config_dict = None
        basic_setup_success = False

        await hass.async_add_executor_job(conf_util.process_ha_config_upgrade, hass)

        try:
            config_dict = await conf_util.async_hass_config_yaml(hass)
        except HomeAssistantError as err:
            _LOGGER.error(
                "Failed to parse configuration.yaml: %s. Activating recovery mode",
                err,
            )
        else:
            if not is_virtual_env():
                await async_mount_local_lib_path(runtime_config.config_dir)

            basic_setup_success = (
                await async_from_config_dict(config_dict, hass) is not None
            )

        if config_dict is None:
            recovery_mode = True
            await hass.async_stop(force=True)
            hass = await create_hass()

        elif not basic_setup_success:
            _LOGGER.warning(
                "Unable to set up core integrations. Activating recovery mode"
            )
            recovery_mode = True
            await hass.async_stop(force=True)
            hass = await create_hass()

        elif any(
            domain not in hass.config.components for domain in CRITICAL_INTEGRATIONS
        ):
            _LOGGER.warning(
                "Detected that %s did not load. Activating recovery mode",
                ",".join(CRITICAL_INTEGRATIONS),
            )

            old_config = hass.config
            old_logging = hass.data.get(DATA_LOGGING)

            recovery_mode = True
            await hass.async_stop(force=True)
            hass = await create_hass()

            if old_logging:
                hass.data[DATA_LOGGING] = old_logging
            hass.config.debug = old_config.debug
            hass.config.skip_pip = old_config.skip_pip
            hass.config.skip_pip_packages = old_config.skip_pip_packages
            hass.config.internal_url = old_config.internal_url
            hass.config.external_url = old_config.external_url
            # Setup loader cache after the config dir has been set
            loader.async_setup(hass)

    if recovery_mode:
        _LOGGER.info("Starting in recovery mode")
        hass.config.recovery_mode = True

        http_conf = (await http.async_get_last_config(hass)) or {}

        await async_from_config_dict(
            {"recovery_mode": {}, "http": http_conf},
            hass,
        )
    elif hass.config.safe_mode:
        _LOGGER.info("Starting in safe mode")

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


def _init_blocking_io_modules_in_executor() -> None:
    """Initialize modules that do blocking I/O in executor."""
    # Cache the result of platform.uname().processor in the executor.
    # Multiple modules call this function at startup which
    # executes a blocking subprocess call. This is a problem for the
    # asyncio event loop. By priming the cache of uname we can
    # avoid the blocking call in the event loop.
    _ = platform.uname().processor
    # Initialize the mimetypes module to avoid blocking calls
    # to the filesystem to load the mime.types file.
    mimetypes.init()
    # Initialize is_official_image and is_docker_env to avoid blocking calls
    # to the filesystem.
    is_official_image()
    is_docker_env()


async def async_load_base_functionality(hass: core.HomeAssistant) -> None:
    """Load the registries and modules that will do blocking I/O."""
    if DATA_REGISTRIES_LOADED in hass.data:
        return
    hass.data[DATA_REGISTRIES_LOADED] = None
    entity.async_setup(hass)
    frame.async_setup(hass)
    template.async_setup(hass)
    translation.async_setup(hass)
    await asyncio.gather(
        create_eager_task(get_internal_store_manager(hass).async_initialize()),
        create_eager_task(area_registry.async_load(hass)),
        create_eager_task(category_registry.async_load(hass)),
        create_eager_task(device_registry.async_load(hass)),
        create_eager_task(entity_registry.async_load(hass)),
        create_eager_task(floor_registry.async_load(hass)),
        create_eager_task(issue_registry.async_load(hass)),
        create_eager_task(label_registry.async_load(hass)),
        hass.async_add_executor_job(_init_blocking_io_modules_in_executor),
        create_eager_task(template.async_load_custom_templates(hass)),
        create_eager_task(restore_state.async_load(hass)),
        create_eager_task(hass.config_entries.async_initialize()),
        create_eager_task(async_get_system_info(hass)),
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
    # Prime custom component cache early so we know if registry entries are tied
    # to a custom integration
    await loader.async_get_custom_components(hass)
    await async_load_base_functionality(hass)

    # Set up core.
    _LOGGER.debug("Setting up %s", CORE_INTEGRATIONS)

    if not all(
        await asyncio.gather(
            *(
                create_eager_task(
                    async_setup_component(hass, domain, config),
                    name=f"bootstrap setup {domain}",
                    loop=hass.loop,
                )
                for domain in CORE_INTEGRATIONS
            )
        )
    ):
        _LOGGER.error("Home Assistant core failed to initialize. ")
        return None

    _LOGGER.debug("Home Assistant core initialized")

    core_config = config.get(core.DOMAIN, {})

    try:
        await async_process_ha_core_config(hass, core_config)
    except vol.Invalid as config_err:
        conf_util.async_log_schema_error(config_err, core.DOMAIN, core_config, hass)
        async_notify_setup_error(hass, core.DOMAIN)
        return None
    except HomeAssistantError:
        _LOGGER.error(
            "Home Assistant core failed to initialize. Further initialization aborted"
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
            f"python_version_{required_python_version}",
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


async def async_enable_logging(
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

    if not log_no_color:
        try:
            # pylint: disable-next=import-outside-toplevel
            from colorlog import ColoredFormatter

            # basicConfig must be called after importing colorlog in order to
            # ensure that the handlers it sets up wraps the correct streams.
            logging.basicConfig(level=logging.INFO)

            colorfmt = f"%(log_color)s{fmt}%(reset)s"
            logging.getLogger().handlers[0].setFormatter(
                ColoredFormatter(
                    colorfmt,
                    datefmt=FORMAT_DATETIME,
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
    logging.basicConfig(format=fmt, datefmt=FORMAT_DATETIME, level=logging.INFO)

    # Capture warnings.warn(...) and friends messages in logs.
    # The standard destination for them is stderr, which may end up unnoticed.
    # This way they're where other messages are, and can be filtered as usual.
    logging.captureWarnings(True)

    # Suppress overly verbose logs from libraries that aren't helpful
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    sys.excepthook = lambda *args: logging.getLogger().exception(
        "Uncaught exception", exc_info=args
    )
    threading.excepthook = lambda args: logging.getLogger().exception(
        "Uncaught thread exception",
        exc_info=(  # type: ignore[arg-type]
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
        ),
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
        err_handler = await hass.async_add_executor_job(
            _create_log_file, err_log_path, log_rotate_days
        )

        err_handler.setFormatter(logging.Formatter(fmt, datefmt=FORMAT_DATETIME))

        logger = logging.getLogger()
        logger.addHandler(err_handler)
        logger.setLevel(logging.INFO if verbose else logging.WARNING)

        # Save the log file location for access by other components.
        hass.data[DATA_LOGGING] = err_log_path
    else:
        _LOGGER.error("Unable to set up error log %s (access denied)", err_log_path)

    async_activate_log_queue_handler(hass)


def _create_log_file(
    err_log_path: str, log_rotate_days: int | None
) -> RotatingFileHandler | TimedRotatingFileHandler:
    """Create log file and do roll over."""
    err_handler: RotatingFileHandler | TimedRotatingFileHandler
    if log_rotate_days:
        err_handler = TimedRotatingFileHandler(
            err_log_path, when="midnight", backupCount=log_rotate_days
        )
    else:
        err_handler = _RotatingFileHandlerWithoutShouldRollOver(
            err_log_path, backupCount=1
        )
        try:
            err_handler.doRollover()
        except OSError as err:
            _LOGGER.error("Error rolling over log file: %s", err)

    return err_handler


class _RotatingFileHandlerWithoutShouldRollOver(RotatingFileHandler):
    """RotatingFileHandler that does not check if it should roll over on every log."""

    def shouldRollover(self, record: logging.LogRecord) -> bool:
        """Never roll over.

        The shouldRollover check is expensive because it has to stat
        the log file for every log record. Since we do not set maxBytes
        the result of this check is always False.
        """
        return False


async def async_mount_local_lib_path(config_dir: str) -> str:
    """Add local library to Python Path.

    This function is a coroutine.
    """
    deps_dir = os.path.join(config_dir, "deps")
    if (lib_dir := await async_get_user_site(deps_dir)) not in sys.path:
        sys.path.insert(0, lib_dir)
    return deps_dir


def _get_domains(hass: core.HomeAssistant, config: dict[str, Any]) -> set[str]:
    """Get domains of components to set up."""
    # Filter out the repeating and common config section [homeassistant]
    domains = {
        domain for key in config if (domain := cv.domain_key(key)) != core.DOMAIN
    }

    # Add config entry and default domains
    if not hass.config.recovery_mode:
        domains.update(DEFAULT_INTEGRATIONS)
        domains.update(hass.config_entries.async_domains())
    else:
        domains.update(DEFAULT_INTEGRATIONS_RECOVERY_MODE)

    # Add domains depending on if the Supervisor is used or not
    if "SUPERVISOR" in os.environ:
        domains.update(DEFAULT_INTEGRATIONS_SUPERVISOR)

    return domains


async def _async_resolve_domains_and_preload(
    hass: core.HomeAssistant, config: dict[str, Any]
) -> tuple[dict[str, Integration], dict[str, Integration]]:
    """Resolve all dependencies and return integrations to set up.

    The return value is a tuple of two dictionaries:
    - The first dictionary contains integrations
      specified by the configuration (including config entries).
    - The second dictionary contains the same integrations as the first dictionary
      together with all their dependencies.
    """
    domains_to_setup = _get_domains(hass, config)
    platform_integrations = conf_util.extract_platform_integrations(
        config, BASE_PLATFORMS
    )
    # Ensure base platforms that have platform integrations are added to `domains`,
    # so they can be setup first instead of discovering them later when a config
    # entry setup task notices that it's needed and there is already a long line
    # to use the import executor.
    #
    # For example if we have
    # sensor:
    #   - platform: template
    #
    # `template` has to be loaded to validate the config for sensor
    # so we want to start loading `sensor` as soon as we know
    # it will be needed. The more platforms under `sensor:`, the longer
    # it will take to finish setup for `sensor` because each of these
    # platforms has to be imported before we can validate the config.
    #
    # Thankfully we are migrating away from the platform pattern
    # so this will be less of a problem in the future.
    domains_to_setup.update(platform_integrations)

    # Additionally process base platforms since we do not require the manifest
    # to list them as dependencies.
    # We want to later avoid lock contention when multiple integrations try to load
    # their manifests at once.
    # Also process integrations that are defined under base platforms
    # to speed things up.
    additional_domains_to_process = {
        *BASE_PLATFORMS,
        *chain.from_iterable(platform_integrations.values()),
    }

    # Resolve all dependencies so we know all integrations
    # that will have to be loaded and start right-away
    integrations_or_excs = await loader.async_get_integrations(
        hass, {*domains_to_setup, *additional_domains_to_process}
    )
    # Eliminate those missing or with invalid manifest
    integrations_to_process = {
        domain: itg
        for domain, itg in integrations_or_excs.items()
        if isinstance(itg, Integration)
    }
    integrations_dependencies = await loader.resolve_integrations_dependencies(
        hass, integrations_to_process.values()
    )
    # Eliminate those without valid dependencies
    integrations_to_process = {
        domain: integrations_to_process[domain] for domain in integrations_dependencies
    }

    integrations_to_setup = {
        domain: itg
        for domain, itg in integrations_to_process.items()
        if domain in domains_to_setup
    }
    all_integrations_to_setup = integrations_to_setup.copy()
    all_integrations_to_setup.update(
        (dep, loader.async_get_loaded_integration(hass, dep))
        for domain in integrations_to_setup
        for dep in integrations_dependencies[domain].difference(
            all_integrations_to_setup
        )
    )

    # Gather requirements for all integrations,
    # their dependencies and after dependencies.
    # To gather all the requirements we must ignore exceptions here.
    # The exceptions will be detected and handled later in the bootstrap process.
    integrations_after_dependencies = (
        await loader.resolve_integrations_after_dependencies(
            hass, integrations_to_process.values(), ignore_exceptions=True
        )
    )
    integrations_requirements = {
        domain: itg.requirements for domain, itg in integrations_to_process.items()
    }
    integrations_requirements.update(
        (dep, loader.async_get_loaded_integration(hass, dep).requirements)
        for deps in integrations_after_dependencies.values()
        for dep in deps.difference(integrations_requirements)
    )
    all_requirements = set(chain.from_iterable(integrations_requirements.values()))

    # Optimistically check if requirements are already installed
    # ahead of setting up the integrations so we can prime the cache
    # We do not wait for this since it's an optimization only
    hass.async_create_background_task(
        requirements.async_load_installed_versions(hass, all_requirements),
        "check installed requirements",
        eager_start=True,
    )

    # Start loading translations for all integrations we are going to set up
    # in the background so they are ready when we need them. This avoids a
    # lot of waiting for the translation load lock and a thundering herd of
    # tasks trying to load the same translations at the same time as each
    # integration is loaded.
    #
    # We do not wait for this since as soon as the task runs it will
    # hold the translation load lock and if anything is fast enough to
    # wait for the translation load lock, loading will be done by the
    # time it gets to it.
    translations_to_load = {*all_integrations_to_setup, *additional_domains_to_process}
    hass.async_create_background_task(
        translation.async_load_integrations(hass, translations_to_load),
        "load translations",
        eager_start=True,
    )

    # Preload storage for all integrations we are going to set up
    # so we do not have to wait for it to be loaded when we need it
    # in the setup process.
    hass.async_create_background_task(
        get_internal_store_manager(hass).async_preload(
            [*PRELOAD_STORAGE, *all_integrations_to_setup]
        ),
        "preload storage",
        eager_start=True,
    )

    return integrations_to_setup, all_integrations_to_setup


async def _async_set_up_integrations(
    hass: core.HomeAssistant, config: dict[str, Any]
) -> None:
    """Set up all the integrations."""
    watcher = _WatchPendingSetups(hass, _setup_started(hass))
    watcher.async_start()

    integrations, all_integrations = await _async_resolve_domains_and_preload(
        hass, config
    )
    all_domains = set(all_integrations)
    domains = set(integrations)

    _LOGGER.info(
        "Domains to be set up: %s | %s",
        domains,
        all_domains - domains,
    )

    # Initialize recorder
    if "recorder" in all_domains:
        recorder.async_initialize_recorder(hass)

    # Initialize backup
    if "backup" in all_domains:
        backup.async_initialize_backup(hass)

    stages: list[tuple[str, set[str], int | None]] = [
        *(
            (name, domain_group, timeout)
            for name, domain_group, timeout in STAGE_0_INTEGRATIONS
        ),
        ("1", STAGE_1_INTEGRATIONS, STAGE_1_TIMEOUT),
        ("2", domains, STAGE_2_TIMEOUT),
    ]

    _LOGGER.info("Setting up stage 0")
    for name, domain_group, timeout in stages:
        stage_domains_unfiltered = domain_group & all_domains
        if not stage_domains_unfiltered:
            _LOGGER.info("Nothing to set up in stage %s: %s", name, domain_group)
            continue

        stage_domains = stage_domains_unfiltered - hass.config.components
        if not stage_domains:
            _LOGGER.info("Already set up stage %s: %s", name, stage_domains_unfiltered)
            continue

        stage_dep_domains_unfiltered = {
            dep
            for domain in stage_domains
            for dep in all_integrations[domain].all_dependencies
            if dep not in stage_domains
        }
        stage_dep_domains = stage_dep_domains_unfiltered - hass.config.components

        stage_all_domains = stage_domains | stage_dep_domains
        stage_all_integrations = {
            domain: all_integrations[domain] for domain in stage_all_domains
        }
        # Detect all cycles
        stage_integrations_after_dependencies = (
            await loader.resolve_integrations_after_dependencies(
                hass, stage_all_integrations.values(), stage_all_domains
            )
        )
        stage_all_domains = set(stage_integrations_after_dependencies)
        stage_domains &= stage_all_domains
        stage_dep_domains &= stage_all_domains

        _LOGGER.info(
            "Setting up stage %s: %s | %s\nDependencies: %s | %s",
            name,
            stage_domains,
            stage_domains_unfiltered - stage_domains,
            stage_dep_domains,
            stage_dep_domains_unfiltered - stage_dep_domains,
        )

        async_set_domains_to_be_loaded(hass, stage_all_domains)

        if timeout is None:
            await _async_setup_multi_components(hass, stage_all_domains, config)
            continue
        try:
            async with hass.timeout.async_timeout(timeout, cool_down=COOLDOWN_TIME):
                await _async_setup_multi_components(hass, stage_all_domains, config)
        except TimeoutError:
            _LOGGER.warning(
                "Setup timed out for stage %s waiting on %s - moving forward",
                name,
                hass._active_tasks,  # noqa: SLF001
            )

    # Wrap up startup
    _LOGGER.debug("Waiting for startup to wrap up")
    try:
        async with hass.timeout.async_timeout(WRAP_UP_TIMEOUT, cool_down=COOLDOWN_TIME):
            await hass.async_block_till_done()
    except TimeoutError:
        _LOGGER.warning(
            "Setup timed out for bootstrap waiting on %s - moving forward",
            hass._active_tasks,  # noqa: SLF001
        )

    watcher.async_stop()

    if _LOGGER.isEnabledFor(logging.DEBUG):
        setup_time = async_get_setup_timings(hass)
        _LOGGER.debug(
            "Integration setup times: %s",
            dict(sorted(setup_time.items(), key=itemgetter(1), reverse=True)),
        )


class _WatchPendingSetups:
    """Periodic log and dispatch of setups that are pending."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        setup_started: dict[tuple[str, str | None], float],
    ) -> None:
        """Initialize the WatchPendingSetups class."""
        self._hass = hass
        self._setup_started = setup_started
        self._duration_count = 0
        self._handle: asyncio.TimerHandle | None = None
        self._previous_was_empty = True
        self._loop = hass.loop

    def _async_watch(self) -> None:
        """Periodic log of setups that are pending."""
        now = monotonic()
        self._duration_count += SLOW_STARTUP_CHECK_INTERVAL

        remaining_with_setup_started: defaultdict[str, float] = defaultdict(float)
        for integration_group, start_time in self._setup_started.items():
            domain, _ = integration_group
            remaining_with_setup_started[domain] += now - start_time

        if remaining_with_setup_started:
            _LOGGER.debug("Integration remaining: %s", remaining_with_setup_started)
        elif waiting_tasks := self._hass._active_tasks:  # noqa: SLF001
            _LOGGER.debug("Waiting on tasks: %s", waiting_tasks)
        self._async_dispatch(remaining_with_setup_started)
        if (
            self._setup_started
            and self._duration_count % LOG_SLOW_STARTUP_INTERVAL == 0
        ):
            # We log every LOG_SLOW_STARTUP_INTERVAL until all integrations are done
            # once we take over LOG_SLOW_STARTUP_INTERVAL (60s) to start up
            _LOGGER.warning(
                "Waiting on integrations to complete setup: %s",
                self._setup_started,
            )

        _LOGGER.debug("Running timeout Zones: %s", self._hass.timeout.zones)
        self._async_schedule_next()

    def _async_dispatch(self, remaining_with_setup_started: dict[str, float]) -> None:
        """Dispatch the signal."""
        if remaining_with_setup_started or not self._previous_was_empty:
            async_dispatcher_send_internal(
                self._hass, SIGNAL_BOOTSTRAP_INTEGRATIONS, remaining_with_setup_started
            )
        self._previous_was_empty = not remaining_with_setup_started

    def _async_schedule_next(self) -> None:
        """Schedule the next call."""
        self._handle = self._loop.call_later(
            SLOW_STARTUP_CHECK_INTERVAL, self._async_watch
        )

    def async_start(self) -> None:
        """Start watching."""
        self._async_schedule_next()

    def async_stop(self) -> None:
        """Stop watching."""
        self._async_dispatch({})
        if self._handle:
            self._handle.cancel()
            self._handle = None


async def _async_setup_multi_components(
    hass: core.HomeAssistant,
    domains: set[str],
    config: dict[str, Any],
) -> None:
    """Set up multiple domains. Log on failure."""
    # Create setup tasks for base platforms first since everything will have
    # to wait to be imported, and the sooner we can get the base platforms
    # loaded the sooner we can start loading the rest of the integrations.
    futures = {
        domain: hass.async_create_task_internal(
            async_setup_component(hass, domain, config),
            f"setup component {domain}",
            eager_start=True,
        )
        for domain in sorted(domains, key=SETUP_ORDER_SORT_KEY, reverse=True)
    }
    results = await asyncio.gather(*futures.values(), return_exceptions=True)
    for idx, domain in enumerate(futures):
        result = results[idx]
        if isinstance(result, BaseException):
            _LOGGER.error(
                "Error setting up integration %s - received exception",
                domain,
                exc_info=(type(result), result, result.__traceback__),
            )
