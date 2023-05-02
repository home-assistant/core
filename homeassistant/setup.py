"""All methods needed to bootstrap a Home Assistant instance."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Generator, Iterable
import contextlib
from datetime import timedelta
import logging.handlers
from timeit import default_timer as timer
from types import ModuleType
from typing import Any

from . import config as conf_util, core, loader, requirements
from .config import async_notify_setup_error
from .const import (
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_START,
    PLATFORM_FORMAT,
    Platform,
)
from .core import CALLBACK_TYPE
from .exceptions import DependencyError, HomeAssistantError
from .helpers.typing import ConfigType
from .util import dt as dt_util, ensure_unique_string

_LOGGER = logging.getLogger(__name__)

ATTR_COMPONENT = "component"

BASE_PLATFORMS = {platform.value for platform in Platform}

# DATA_SETUP is a dict[str, asyncio.Task[bool]], indicating domains which are currently
# being setup or which failed to setup:
# - Tasks are added to DATA_SETUP by `async_setup_component`, the key is the domain
#   being setup and the Task is the `_async_setup_component` helper.
# - Tasks are removed from DATA_SETUP if setup was successful, that is,
#   the task returned True.
DATA_SETUP = "setup_tasks"

# DATA_SETUP_DONE is a dict [str, asyncio.Event], indicating components which
# will be setup:
# - Events are added to DATA_SETUP_DONE during bootstrap by
#   async_set_domains_to_be_loaded, the key is the domain which will be loaded.
# - Events are set and removed from DATA_SETUP_DONE when async_setup_component
#   is finished, regardless of if the setup was successful or not.
DATA_SETUP_DONE = "setup_done"

# DATA_SETUP_DONE is a dict [str, datetime], indicating when an attempt
# to setup a component started.
DATA_SETUP_STARTED = "setup_started"

# DATA_SETUP_TIME is a dict [str, timedelta], indicating how time was spent
# setting up a component.
DATA_SETUP_TIME = "setup_time"

DATA_DEPS_REQS = "deps_reqs_processed"

SLOW_SETUP_WARNING = 10
SLOW_SETUP_MAX_WAIT = 300


@core.callback
def async_set_domains_to_be_loaded(hass: core.HomeAssistant, domains: set[str]) -> None:
    """Set domains that are going to be loaded from the config.

    This allow us to:
     - Properly handle after_dependencies.
     - Keep track of domains which will load but have not yet finished loading
    """
    hass.data.setdefault(DATA_SETUP_DONE, {})
    hass.data[DATA_SETUP_DONE].update({domain: asyncio.Event() for domain in domains})


def setup_component(hass: core.HomeAssistant, domain: str, config: ConfigType) -> bool:
    """Set up a component and all its dependencies."""
    return asyncio.run_coroutine_threadsafe(
        async_setup_component(hass, domain, config), hass.loop
    ).result()


async def async_setup_component(
    hass: core.HomeAssistant, domain: str, config: ConfigType
) -> bool:
    """Set up a component and all its dependencies.

    This method is a coroutine.
    """
    if domain in hass.config.components:
        return True

    setup_tasks: dict[str, asyncio.Task[bool]] = hass.data.setdefault(DATA_SETUP, {})

    if domain in setup_tasks:
        return await setup_tasks[domain]

    task = setup_tasks[domain] = hass.async_create_task(
        _async_setup_component(hass, domain, config), f"setup component {domain}"
    )

    try:
        return await task
    finally:
        if domain in hass.data.get(DATA_SETUP_DONE, {}):
            hass.data[DATA_SETUP_DONE].pop(domain).set()


async def _async_process_dependencies(
    hass: core.HomeAssistant, config: ConfigType, integration: loader.Integration
) -> list[str]:
    """Ensure all dependencies are set up.

    Returns a list of dependencies which failed to set up.
    """
    dependencies_tasks = {
        dep: hass.loop.create_task(async_setup_component(hass, dep, config))
        for dep in integration.dependencies
        if dep not in hass.config.components
    }

    after_dependencies_tasks = {}
    to_be_loaded = hass.data.get(DATA_SETUP_DONE, {})
    for dep in integration.after_dependencies:
        if (
            dep not in dependencies_tasks
            and dep in to_be_loaded
            and dep not in hass.config.components
        ):
            after_dependencies_tasks[dep] = hass.loop.create_task(
                to_be_loaded[dep].wait()
            )

    if not dependencies_tasks and not after_dependencies_tasks:
        return []

    if dependencies_tasks:
        _LOGGER.debug(
            "Dependency %s will wait for dependencies %s",
            integration.domain,
            list(dependencies_tasks),
        )
    if after_dependencies_tasks:
        _LOGGER.debug(
            "Dependency %s will wait for after dependencies %s",
            integration.domain,
            list(after_dependencies_tasks),
        )

    async with hass.timeout.async_freeze(integration.domain):
        results = await asyncio.gather(
            *dependencies_tasks.values(), *after_dependencies_tasks.values()
        )

    failed = [
        domain for idx, domain in enumerate(dependencies_tasks) if not results[idx]
    ]

    if failed:
        _LOGGER.error(
            "Unable to set up dependencies of %s. Setup failed for dependencies: %s",
            integration.domain,
            ", ".join(failed),
        )

    return failed


async def _async_setup_component(
    hass: core.HomeAssistant, domain: str, config: ConfigType
) -> bool:
    """Set up a component for Home Assistant.

    This method is a coroutine.
    """
    integration: loader.Integration | None = None

    def log_error(msg: str) -> None:
        """Log helper."""
        if integration is None:
            custom = ""
            link = None
        else:
            custom = "" if integration.is_built_in else "custom integration "
            link = integration.documentation
        _LOGGER.error("Setup failed for %s%s: %s", custom, domain, msg)
        async_notify_setup_error(hass, domain, link)

    try:
        integration = await loader.async_get_integration(hass, domain)
    except loader.IntegrationNotFound:
        log_error("Integration not found.")
        return False

    if integration.disabled:
        log_error(f"Dependency is disabled - {integration.disabled}")
        return False

    # Validate all dependencies exist and there are no circular dependencies
    if not await integration.resolve_dependencies():
        return False

    # Process requirements as soon as possible, so we can import the component
    # without requiring imports to be in functions.
    try:
        await async_process_deps_reqs(hass, config, integration)
    except HomeAssistantError as err:
        log_error(str(err))
        return False

    # Some integrations fail on import because they call functions incorrectly.
    # So we do it before validating config to catch these errors.
    try:
        component = integration.get_component()
    except ImportError as err:
        log_error(f"Unable to import component: {err}")
        return False

    processed_config = await conf_util.async_process_component_config(
        hass, config, integration
    )

    if processed_config is None:
        log_error("Invalid config.")
        return False

    start = timer()
    _LOGGER.info("Setting up %s", domain)
    with async_start_setup(hass, [domain]):
        if hasattr(component, "PLATFORM_SCHEMA"):
            # Entity components have their own warning
            warn_task = None
        else:
            warn_task = hass.loop.call_later(
                SLOW_SETUP_WARNING,
                _LOGGER.warning,
                "Setup of %s is taking over %s seconds.",
                domain,
                SLOW_SETUP_WARNING,
            )

        task: Awaitable[bool] | None = None
        result: Any | bool = True
        try:
            if hasattr(component, "async_setup"):
                task = component.async_setup(hass, processed_config)
            elif hasattr(component, "setup"):
                # This should not be replaced with hass.async_add_executor_job because
                # we don't want to track this task in case it blocks startup.
                task = hass.loop.run_in_executor(
                    None, component.setup, hass, processed_config
                )
            elif not hasattr(component, "async_setup_entry"):
                log_error("No setup or config entry setup function defined.")
                return False

            if task:
                async with hass.timeout.async_timeout(SLOW_SETUP_MAX_WAIT, domain):
                    result = await task
        except asyncio.TimeoutError:
            _LOGGER.error(
                (
                    "Setup of %s is taking longer than %s seconds."
                    " Startup will proceed without waiting any longer"
                ),
                domain,
                SLOW_SETUP_MAX_WAIT,
            )
            return False
        # pylint: disable-next=broad-except
        except (asyncio.CancelledError, SystemExit, Exception):
            _LOGGER.exception("Error during setup of component %s", domain)
            async_notify_setup_error(hass, domain, integration.documentation)
            return False
        finally:
            end = timer()
            if warn_task:
                warn_task.cancel()
        _LOGGER.info("Setup of domain %s took %.1f seconds", domain, end - start)

        if result is False:
            log_error("Integration failed to initialize.")
            return False
        if result is not True:
            log_error(
                f"Integration {domain!r} did not return boolean if setup was "
                "successful. Disabling component."
            )
            return False

        # Flush out async_setup calling create_task. Fragile but covered by test.
        await asyncio.sleep(0)
        await hass.config_entries.flow.async_wait_import_flow_initialized(domain)

        # Add to components before the entry.async_setup
        # call to avoid a deadlock when forwarding platforms
        hass.config.components.add(domain)

        await asyncio.gather(
            *(
                asyncio.create_task(
                    entry.async_setup(hass, integration=integration),
                    name=f"config entry setup {entry.title} {entry.domain} {entry.entry_id}",
                )
                for entry in hass.config_entries.async_entries(domain)
            )
        )

    # Cleanup
    if domain in hass.data[DATA_SETUP]:
        hass.data[DATA_SETUP].pop(domain)

    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: domain})

    return True


async def async_prepare_setup_platform(
    hass: core.HomeAssistant, hass_config: ConfigType, domain: str, platform_name: str
) -> ModuleType | None:
    """Load a platform and makes sure dependencies are setup.

    This method is a coroutine.
    """
    platform_path = PLATFORM_FORMAT.format(domain=domain, platform=platform_name)

    def log_error(msg: str) -> None:
        """Log helper."""

        _LOGGER.error("Unable to prepare setup for platform %s: %s", platform_path, msg)
        async_notify_setup_error(hass, platform_path)

    try:
        integration = await loader.async_get_integration(hass, platform_name)
    except loader.IntegrationNotFound:
        log_error("Integration not found")
        return None

    # Process deps and reqs as soon as possible, so that requirements are
    # available when we import the platform.
    try:
        await async_process_deps_reqs(hass, hass_config, integration)
    except HomeAssistantError as err:
        log_error(str(err))
        return None

    try:
        platform = integration.get_platform(domain)
    except ImportError as exc:
        log_error(f"Platform not found ({exc}).")
        return None

    # Already loaded
    if platform_path in hass.config.components:
        return platform

    # Platforms cannot exist on their own, they are part of their integration.
    # If the integration is not set up yet, and can be set up, set it up.
    if integration.domain not in hass.config.components:
        try:
            component = integration.get_component()
        except ImportError as exc:
            log_error(f"Unable to import the component ({exc}).")
            return None

        if (
            hasattr(component, "setup") or hasattr(component, "async_setup")
        ) and not await async_setup_component(hass, integration.domain, hass_config):
            log_error("Unable to set up component.")
            return None

    return platform


async def async_process_deps_reqs(
    hass: core.HomeAssistant, config: ConfigType, integration: loader.Integration
) -> None:
    """Process all dependencies and requirements for a module.

    Module is a Python module of either a component or platform.
    """
    if (processed := hass.data.get(DATA_DEPS_REQS)) is None:
        processed = hass.data[DATA_DEPS_REQS] = set()
    elif integration.domain in processed:
        return

    if failed_deps := await _async_process_dependencies(hass, config, integration):
        raise DependencyError(failed_deps)

    async with hass.timeout.async_freeze(integration.domain):
        await requirements.async_get_integration_with_requirements(
            hass, integration.domain
        )

    processed.add(integration.domain)


@core.callback
def async_when_setup(
    hass: core.HomeAssistant,
    component: str,
    when_setup_cb: Callable[[core.HomeAssistant, str], Awaitable[None]],
) -> None:
    """Call a method when a component is setup."""
    _async_when_setup(hass, component, when_setup_cb, False)


@core.callback
def async_when_setup_or_start(
    hass: core.HomeAssistant,
    component: str,
    when_setup_cb: Callable[[core.HomeAssistant, str], Awaitable[None]],
) -> None:
    """Call a method when a component is setup or state is fired."""
    _async_when_setup(hass, component, when_setup_cb, True)


@core.callback
def _async_when_setup(
    hass: core.HomeAssistant,
    component: str,
    when_setup_cb: Callable[[core.HomeAssistant, str], Awaitable[None]],
    start_event: bool,
) -> None:
    """Call a method when a component is setup or the start event fires."""

    async def when_setup() -> None:
        """Call the callback."""
        try:
            await when_setup_cb(hass, component)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error handling when_setup callback for %s", component)

    if component in hass.config.components:
        hass.async_create_task(when_setup(), f"when setup {component}")
        return

    listeners: list[CALLBACK_TYPE] = []

    async def _matched_event(event: core.Event) -> None:
        """Call the callback when we matched an event."""
        for listener in listeners:
            listener()
        await when_setup()

    async def _loaded_event(event: core.Event) -> None:
        """Call the callback if we loaded the expected component."""
        if event.data[ATTR_COMPONENT] == component:
            await _matched_event(event)

    listeners.append(hass.bus.async_listen(EVENT_COMPONENT_LOADED, _loaded_event))
    if start_event:
        listeners.append(
            hass.bus.async_listen(EVENT_HOMEASSISTANT_START, _matched_event)
        )


@core.callback
def async_get_loaded_integrations(hass: core.HomeAssistant) -> set[str]:
    """Return the complete list of loaded integrations."""
    integrations = set()
    for component in hass.config.components:
        if "." not in component:
            integrations.add(component)
            continue
        domain, _, platform = component.partition(".")
        if domain in BASE_PLATFORMS:
            integrations.add(platform)
    return integrations


@contextlib.contextmanager
def async_start_setup(
    hass: core.HomeAssistant, components: Iterable[str]
) -> Generator[None, None, None]:
    """Keep track of when setup starts and finishes."""
    setup_started = hass.data.setdefault(DATA_SETUP_STARTED, {})
    started = dt_util.utcnow()
    unique_components: dict[str, str] = {}
    for domain in components:
        unique = ensure_unique_string(domain, setup_started)
        unique_components[unique] = domain
        setup_started[unique] = started

    yield

    setup_time: dict[str, timedelta] = hass.data.setdefault(DATA_SETUP_TIME, {})
    time_taken = dt_util.utcnow() - started
    for unique, domain in unique_components.items():
        del setup_started[unique]
        integration = domain.rpartition(".")[-1]
        if integration in setup_time:
            setup_time[integration] += time_taken
        else:
            setup_time[integration] = time_taken
