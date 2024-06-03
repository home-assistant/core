"""All methods needed to bootstrap a Home Assistant instance."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable, Generator, Mapping
import contextlib
import contextvars
from enum import StrEnum
from functools import partial
import logging.handlers
import time
from types import ModuleType
from typing import Any, Final, TypedDict

from . import config as conf_util, core, loader, requirements
from .const import (
    BASE_PLATFORMS,  # noqa: F401
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_START,
    PLATFORM_FORMAT,
)
from .core import (
    CALLBACK_TYPE,
    DOMAIN as HOMEASSISTANT_DOMAIN,
    Event,
    HomeAssistant,
    callback,
)
from .exceptions import DependencyError, HomeAssistantError
from .helpers import singleton, translation
from .helpers.issue_registry import IssueSeverity, async_create_issue
from .helpers.typing import ConfigType
from .util.async_ import create_eager_task
from .util.hass_dict import HassKey

current_setup_group: contextvars.ContextVar[tuple[str, str | None] | None] = (
    contextvars.ContextVar("current_setup_group", default=None)
)


_LOGGER = logging.getLogger(__name__)

ATTR_COMPONENT: Final = "component"


# DATA_SETUP is a dict, indicating domains which are currently
# being setup or which failed to setup:
# - Tasks are added to DATA_SETUP by `async_setup_component`, the key is the domain
#   being setup and the Task is the `_async_setup_component` helper.
# - Tasks are removed from DATA_SETUP if setup was successful, that is,
#   the task returned True.
DATA_SETUP: HassKey[dict[str, asyncio.Future[bool]]] = HassKey("setup_tasks")

# DATA_SETUP_DONE is a dict, indicating components which will be setup:
# - Events are added to DATA_SETUP_DONE during bootstrap by
#   async_set_domains_to_be_loaded, the key is the domain which will be loaded.
# - Events are set and removed from DATA_SETUP_DONE when async_setup_component
#   is finished, regardless of if the setup was successful or not.
DATA_SETUP_DONE: HassKey[dict[str, asyncio.Future[bool]]] = HassKey("setup_done")

# DATA_SETUP_STARTED is a dict, indicating when an attempt
# to setup a component started.
DATA_SETUP_STARTED: HassKey[dict[tuple[str, str | None], float]] = HassKey(
    "setup_started"
)

# DATA_SETUP_TIME is a defaultdict, indicating how time was spent
# setting up a component.
DATA_SETUP_TIME: HassKey[
    defaultdict[str, defaultdict[str | None, defaultdict[SetupPhases, float]]]
] = HassKey("setup_time")

DATA_DEPS_REQS: HassKey[set[str]] = HassKey("deps_reqs_processed")

DATA_PERSISTENT_ERRORS: HassKey[dict[str, str | None]] = HassKey(
    "bootstrap_persistent_errors"
)

NOTIFY_FOR_TRANSLATION_KEYS = [
    "config_validation_err",
    "platform_config_validation_err",
]

SLOW_SETUP_WARNING = 10
SLOW_SETUP_MAX_WAIT = 300


class EventComponentLoaded(TypedDict):
    """EventComponentLoaded data."""

    component: str


@callback
def async_notify_setup_error(
    hass: HomeAssistant, component: str, display_link: str | None = None
) -> None:
    """Print a persistent notification.

    This method must be run in the event loop.
    """
    # pylint: disable-next=import-outside-toplevel
    from .components import persistent_notification

    if (errors := hass.data.get(DATA_PERSISTENT_ERRORS)) is None:
        errors = hass.data[DATA_PERSISTENT_ERRORS] = {}

    errors[component] = errors.get(component) or display_link

    message = "The following integrations and platforms could not be set up:\n\n"

    for name, link in errors.items():
        show_logs = f"[Show logs](/config/logs?filter={name})"
        part = f"[{name}]({link})" if link else name
        message += f" - {part} ({show_logs})\n"

    message += "\nPlease check your config and [logs](/config/logs)."

    persistent_notification.async_create(
        hass, message, "Invalid config", "invalid_config"
    )


@core.callback
def async_set_domains_to_be_loaded(hass: core.HomeAssistant, domains: set[str]) -> None:
    """Set domains that are going to be loaded from the config.

    This allow us to:
     - Properly handle after_dependencies.
     - Keep track of domains which will load but have not yet finished loading
    """
    setup_done_futures = hass.data.setdefault(DATA_SETUP_DONE, {})
    setup_done_futures.update({domain: hass.loop.create_future() for domain in domains})


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

    setup_futures = hass.data.setdefault(DATA_SETUP, {})
    setup_done_futures = hass.data.setdefault(DATA_SETUP_DONE, {})

    if existing_setup_future := setup_futures.get(domain):
        return await existing_setup_future

    setup_future = hass.loop.create_future()
    setup_futures[domain] = setup_future

    try:
        result = await _async_setup_component(hass, domain, config)
        setup_future.set_result(result)
        if setup_done_future := setup_done_futures.pop(domain, None):
            setup_done_future.set_result(result)
    except BaseException as err:
        futures = [setup_future]
        if setup_done_future := setup_done_futures.pop(domain, None):
            futures.append(setup_done_future)
        for future in futures:
            # If the setup call is cancelled it likely means
            # Home Assistant is shutting down so the future might
            # already be done which will cause this to raise
            # an InvalidStateError which is appropriate because
            # the component setup was cancelled and is in an
            # indeterminate state.
            future.set_exception(err)
            with contextlib.suppress(BaseException):
                # Clear the flag as its normal that nothing
                # will wait for this future to be resolved
                # if there are no concurrent setup attempts
                await future
        raise
    return result


async def _async_process_dependencies(
    hass: core.HomeAssistant, config: ConfigType, integration: loader.Integration
) -> list[str]:
    """Ensure all dependencies are set up.

    Returns a list of dependencies which failed to set up.
    """
    setup_futures = hass.data.setdefault(DATA_SETUP, {})

    dependencies_tasks = {
        dep: setup_futures.get(dep)
        or create_eager_task(
            async_setup_component(hass, dep, config),
            name=f"setup {dep} as dependency of {integration.domain}",
            loop=hass.loop,
        )
        for dep in integration.dependencies
        if dep not in hass.config.components
    }

    after_dependencies_tasks: dict[str, asyncio.Future[bool]] = {}
    to_be_loaded = hass.data.get(DATA_SETUP_DONE, {})
    for dep in integration.after_dependencies:
        if (
            dep not in dependencies_tasks
            and dep in to_be_loaded
            and dep not in hass.config.components
        ):
            after_dependencies_tasks[dep] = to_be_loaded[dep]

    if not dependencies_tasks and not after_dependencies_tasks:
        return []

    if dependencies_tasks:
        _LOGGER.debug(
            "Dependency %s will wait for dependencies %s",
            integration.domain,
            dependencies_tasks.keys(),
        )
    if after_dependencies_tasks:
        _LOGGER.debug(
            "Dependency %s will wait for after dependencies %s",
            integration.domain,
            after_dependencies_tasks.keys(),
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
            "Unable to set up dependencies of '%s'. Setup failed for dependencies: %s",
            integration.domain,
            failed,
        )

    return failed


def _log_error_setup_error(
    hass: HomeAssistant,
    domain: str,
    integration: loader.Integration | None,
    msg: str,
    exc_info: Exception | None = None,
) -> None:
    """Log helper."""
    if integration is None:
        custom = ""
        link = None
    else:
        custom = "" if integration.is_built_in else "custom integration "
        link = integration.documentation
    _LOGGER.error("Setup failed for %s'%s': %s", custom, domain, msg, exc_info=exc_info)
    async_notify_setup_error(hass, domain, link)


async def _async_setup_component(
    hass: core.HomeAssistant, domain: str, config: ConfigType
) -> bool:
    """Set up a component for Home Assistant.

    This method is a coroutine.
    """
    try:
        integration = await loader.async_get_integration(hass, domain)
    except loader.IntegrationNotFound:
        _log_error_setup_error(hass, domain, None, "Integration not found.")
        return False

    log_error = partial(_log_error_setup_error, hass, domain, integration)

    if integration.disabled:
        log_error(f"Dependency is disabled - {integration.disabled}")
        return False

    integration_set = {domain}

    load_translations_task: asyncio.Task[None] | None = None
    if integration.has_translations and not translation.async_translations_loaded(
        hass, integration_set
    ):
        # For most cases we expect the translations are already
        # loaded since we try to load them in bootstrap ahead of time.
        # If for some reason the background task in bootstrap was too slow
        # or the integration was added after bootstrap, we will load them here.
        load_translations_task = create_eager_task(
            translation.async_load_integrations(hass, integration_set), loop=hass.loop
        )
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
        component = await integration.async_get_component()
    except ImportError as err:
        log_error(f"Unable to import component: {err}", err)
        return False

    integration_config_info = await conf_util.async_process_component_config(
        hass, config, integration, component
    )
    conf_util.async_handle_component_errors(hass, integration_config_info, integration)
    processed_config = conf_util.async_drop_config_annotations(
        integration_config_info, integration
    )
    for platform_exception in integration_config_info.exception_info_list:
        if platform_exception.translation_key not in NOTIFY_FOR_TRANSLATION_KEYS:
            continue
        async_notify_setup_error(
            hass, platform_exception.platform_path, platform_exception.integration_link
        )
    if processed_config is None:
        log_error("Invalid config.")
        return False

    # Detect attempt to setup integration which can be setup only from config entry
    if (
        domain in processed_config
        and not hasattr(component, "async_setup")
        and not hasattr(component, "setup")
        and not hasattr(component, "CONFIG_SCHEMA")
    ):
        _LOGGER.error(
            (
                "The '%s' integration does not support YAML setup, please remove it "
                "from your configuration"
            ),
            domain,
        )
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"config_entry_only_{domain}",
            is_fixable=False,
            severity=IssueSeverity.ERROR,
            issue_domain=domain,
            translation_key="config_entry_only",
            translation_placeholders={
                "domain": domain,
                "add_integration": f"/config/integrations/dashboard/add?domain={domain}",
            },
        )

    _LOGGER.info("Setting up %s", domain)

    with async_start_setup(hass, integration=domain, phase=SetupPhases.SETUP):
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
        except TimeoutError:
            _LOGGER.error(
                (
                    "Setup of '%s' is taking longer than %s seconds."
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
            if warn_task:
                warn_task.cancel()
        if result is False:
            log_error("Integration failed to initialize.")
            return False
        if result is not True:
            log_error(
                f"Integration {domain!r} did not return boolean if setup was "
                "successful. Disabling component."
            )
            return False

        if load_translations_task:
            await load_translations_task

    if integration.platforms_exists(("config_flow",)):
        # If the integration has a config_flow, wait for import flows.
        # As these are all created with eager tasks, we do not sleep here,
        # as the tasks will always be started before we reach this point.
        await hass.config_entries.flow.async_wait_import_flow_initialized(domain)

    # Add to components before the entry.async_setup
    # call to avoid a deadlock when forwarding platforms
    hass.config.components.add(domain)

    if entries := hass.config_entries.async_entries(
        domain, include_ignore=False, include_disabled=False
    ):
        await asyncio.gather(
            *(
                create_eager_task(
                    entry.async_setup_locked(hass, integration=integration),
                    name=(
                        f"config entry setup {entry.title} {entry.domain} "
                        f"{entry.entry_id}"
                    ),
                    loop=hass.loop,
                )
                for entry in entries
            )
        )

    # Cleanup
    hass.data[DATA_SETUP].pop(domain, None)

    hass.bus.async_fire_internal(
        EVENT_COMPONENT_LOADED, EventComponentLoaded(component=domain)
    )

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

        _LOGGER.error(
            "Unable to prepare setup for platform '%s': %s", platform_path, msg
        )
        async_notify_setup_error(hass, platform_path)

    try:
        integration = await loader.async_get_integration(hass, platform_name)
    except loader.IntegrationNotFound:
        log_error("Integration not found")
        return None

    # Platforms cannot exist on their own, they are part of their integration.
    # If the integration is not set up yet, and can be set up, set it up.
    #
    # We do this before we import the platform so the platform already knows
    # where the top level component is.
    #
    if load_top_level_component := integration.domain not in hass.config.components:
        # Process deps and reqs as soon as possible, so that requirements are
        # available when we import the platform. We only do this if the integration
        # is not in hass.config.components yet, as we already processed them in
        # async_setup_component if it is.
        try:
            await async_process_deps_reqs(hass, hass_config, integration)
        except HomeAssistantError as err:
            log_error(str(err))
            return None

        try:
            component = await integration.async_get_component()
        except ImportError as exc:
            log_error(f"Unable to import the component ({exc}).")
            return None

    if not integration.platforms_exists((domain,)):
        log_error(
            f"Platform not found (No module named '{integration.pkg_path}.{domain}')"
        )
        return None

    try:
        platform = await integration.async_get_platform(domain)
    except ImportError as exc:
        log_error(f"Platform not found ({exc}).")
        return None

    # Already loaded
    if platform_path in hass.config.components:
        return platform

    # Platforms cannot exist on their own, they are part of their integration.
    # If the integration is not set up yet, and can be set up, set it up.
    if load_top_level_component:
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
        except Exception:
            _LOGGER.exception("Error handling when_setup callback for %s", component)

    if component in hass.config.components:
        hass.async_create_task_internal(
            when_setup(), f"when setup {component}", eager_start=True
        )
        return

    listeners: list[CALLBACK_TYPE] = []

    async def _matched_event(event: Event[Any]) -> None:
        """Call the callback when we matched an event."""
        for listener in listeners:
            listener()
        await when_setup()

    @callback
    def _async_is_component_filter(event_data: EventComponentLoaded) -> bool:
        """Check if the event is for the component."""
        return event_data[ATTR_COMPONENT] == component

    listeners.append(
        hass.bus.async_listen(
            EVENT_COMPONENT_LOADED,
            _matched_event,
            event_filter=_async_is_component_filter,
        )
    )
    if start_event:
        listeners.append(
            hass.bus.async_listen(EVENT_HOMEASSISTANT_START, _matched_event)
        )


@core.callback
def async_get_loaded_integrations(hass: core.HomeAssistant) -> set[str]:
    """Return the complete list of loaded integrations."""
    return hass.config.all_components


class SetupPhases(StrEnum):
    """Constants for setup time measurements."""

    SETUP = "setup"
    """Set up of a component in __init__.py."""
    CONFIG_ENTRY_SETUP = "config_entry_setup"
    """Set up of a config entry in __init__.py."""
    PLATFORM_SETUP = "platform_setup"
    """Set up of a platform integration.

    ex async_setup_platform or setup_platform or
    a legacy platform like device_tracker.legacy
    """
    CONFIG_ENTRY_PLATFORM_SETUP = "config_entry_platform_setup"
    """Set up of a platform in a config entry after the config entry is setup.

    This is only for platforms that are not awaited in async_setup_entry.
    """
    WAIT_BASE_PLATFORM_SETUP = "wait_base_component"
    """Wait time for the base component to be setup."""
    WAIT_IMPORT_PLATFORMS = "wait_import_platforms"
    """Wait time for the platforms to import."""
    WAIT_IMPORT_PACKAGES = "wait_import_packages"
    """Wait time for the packages to import."""


@singleton.singleton(DATA_SETUP_STARTED)
def _setup_started(
    hass: core.HomeAssistant,
) -> dict[tuple[str, str | None], float]:
    """Return the setup started dict."""
    return {}


@contextlib.contextmanager
def async_pause_setup(
    hass: core.HomeAssistant, phase: SetupPhases
) -> Generator[None, None, None]:
    """Keep track of time we are blocked waiting for other operations.

    We want to count the time we wait for importing and
    setting up the base components so we can subtract it
    from the total setup time.
    """
    if not (running := current_setup_group.get()) or running not in _setup_started(
        hass
    ):
        # This means we are likely in a late platform setup
        # that is running in a task so we do not want
        # to subtract out the time later as nothing is waiting
        # for the code inside the context manager to finish.
        yield
        return

    started = time.monotonic()
    try:
        yield
    finally:
        time_taken = time.monotonic() - started
        integration, group = running
        # Add negative time for the time we waited
        _setup_times(hass)[integration][group][phase] = -time_taken
        _LOGGER.debug(
            "Adding wait for %s for %s (%s) of %.2f",
            phase,
            integration,
            group,
            time_taken,
        )


@singleton.singleton(DATA_SETUP_TIME)
def _setup_times(
    hass: core.HomeAssistant,
) -> defaultdict[str, defaultdict[str | None, defaultdict[SetupPhases, float]]]:
    """Return the setup timings default dict."""
    return defaultdict(lambda: defaultdict(lambda: defaultdict(float)))


@contextlib.contextmanager
def async_start_setup(
    hass: core.HomeAssistant,
    integration: str,
    phase: SetupPhases,
    group: str | None = None,
) -> Generator[None, None, None]:
    """Keep track of when setup starts and finishes.

    :param hass: Home Assistant instance
    :param integration: The integration that is being setup
    :param phase: The phase of setup
    :param group: The group (config entry/platform instance) that is being setup

      A group is a group of setups that run in parallel.

    """
    if hass.is_stopping or hass.state is core.CoreState.running:
        # Don't track setup times when we are shutting down or already running
        # as we present the timings as "Integration startup time", and we
        # don't want to add all the setup retry times to that.
        yield
        return

    setup_started = _setup_started(hass)
    current = (integration, group)
    if current in setup_started:
        # We are already inside another async_start_setup, this like means we
        # are setting up a platform inside async_setup_entry so we should not
        # record this as a new setup
        yield
        return

    started = time.monotonic()
    current_setup_group.set(current)
    setup_started[current] = started

    try:
        yield
    finally:
        time_taken = time.monotonic() - started
        del setup_started[current]
        group_setup_times = _setup_times(hass)[integration][group]
        # We may see the phase multiple times if there are multiple
        # platforms, but we only care about the longest time.
        group_setup_times[phase] = max(group_setup_times[phase], time_taken)
        if group is None:
            _LOGGER.info(
                "Setup of domain %s took %.2f seconds", integration, time_taken
            )
        elif _LOGGER.isEnabledFor(logging.DEBUG):
            wait_time = -sum(value for value in group_setup_times.values() if value < 0)
            calculated_time = time_taken - wait_time
            _LOGGER.debug(
                "Phase %s for %s (%s) took %.2fs (elapsed=%.2fs) (wait_time=%.2fs)",
                phase,
                integration,
                group,
                calculated_time,
                time_taken,
                wait_time,
            )


@callback
def async_get_setup_timings(hass: core.HomeAssistant) -> dict[str, float]:
    """Return timing data for each integration."""
    setup_time = _setup_times(hass)
    domain_timings: dict[str, float] = {}
    top_level_timings: Mapping[SetupPhases, float]
    for domain, timings in setup_time.items():
        top_level_timings = timings.get(None, {})
        total_top_level = sum(top_level_timings.values())
        # Groups (config entries/platform instance) are setup in parallel so we
        # take the max of the group timings and add it to the top level
        group_totals = {
            group: sum(group_timings.values())
            for group, group_timings in timings.items()
            if group is not None
        }
        group_max = max(group_totals.values(), default=0)
        domain_timings[domain] = total_top_level + group_max

    return domain_timings


@callback
def async_get_domain_setup_times(
    hass: core.HomeAssistant, domain: str
) -> Mapping[str | None, dict[SetupPhases, float]]:
    """Return timing data for each integration."""
    return _setup_times(hass).get(domain, {})
