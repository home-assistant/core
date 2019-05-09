"""All methods needed to bootstrap a Home Assistant instance."""
import asyncio
import logging.handlers
from timeit import default_timer as timer

from types import ModuleType
from typing import Awaitable, Callable, Optional, Dict, List

from homeassistant import requirements, core, loader, config as conf_util
from homeassistant.config import async_notify_setup_error
from homeassistant.const import EVENT_COMPONENT_LOADED, PLATFORM_FORMAT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.async_ import run_coroutine_threadsafe


_LOGGER = logging.getLogger(__name__)

ATTR_COMPONENT = 'component'

DATA_SETUP = 'setup_tasks'
DATA_DEPS_REQS = 'deps_reqs_processed'

SLOW_SETUP_WARNING = 10


def setup_component(hass: core.HomeAssistant, domain: str,
                    config: Dict) -> bool:
    """Set up a component and all its dependencies."""
    return run_coroutine_threadsafe(  # type: ignore
        async_setup_component(hass, domain, config), loop=hass.loop).result()


async def async_setup_component(hass: core.HomeAssistant, domain: str,
                                config: Dict) -> bool:
    """Set up a component and all its dependencies.

    This method is a coroutine.
    """
    if domain in hass.config.components:
        return True

    setup_tasks = hass.data.setdefault(DATA_SETUP, {})

    if domain in setup_tasks:
        return await setup_tasks[domain]  # type: ignore

    task = setup_tasks[domain] = hass.async_create_task(
        _async_setup_component(hass, domain, config))

    return await task  # type: ignore


async def _async_process_dependencies(
        hass: core.HomeAssistant, config: Dict, name: str,
        dependencies: List[str]) -> bool:
    """Ensure all dependencies are set up."""
    blacklisted = [dep for dep in dependencies
                   if dep in loader.DEPENDENCY_BLACKLIST]

    if blacklisted and name != 'default_config':
        _LOGGER.error("Unable to set up dependencies of %s: "
                      "found blacklisted dependencies: %s",
                      name, ', '.join(blacklisted))
        return False

    tasks = [async_setup_component(hass, dep, config) for dep
             in dependencies]

    if not tasks:
        return True

    results = await asyncio.gather(*tasks, loop=hass.loop)

    failed = [dependencies[idx] for idx, res
              in enumerate(results) if not res]

    if failed:
        _LOGGER.error("Unable to set up dependencies of %s. "
                      "Setup failed for dependencies: %s",
                      name, ', '.join(failed))

        return False
    return True


async def _async_setup_component(hass: core.HomeAssistant,
                                 domain: str, config: Dict) -> bool:
    """Set up a component for Home Assistant.

    This method is a coroutine.
    """
    def log_error(msg: str, link: bool = True) -> None:
        """Log helper."""
        _LOGGER.error("Setup failed for %s: %s", domain, msg)
        async_notify_setup_error(hass, domain, link)

    try:
        integration = await loader.async_get_integration(hass, domain)
    except loader.IntegrationNotFound:
        log_error("Integration not found.", False)
        return False

    # Validate all dependencies exist and there are no circular dependencies
    try:
        await loader.async_component_dependencies(hass, domain)
    except loader.IntegrationNotFound as err:
        _LOGGER.error(
            "Not setting up %s because we are unable to resolve "
            "(sub)dependency %s", domain, err.domain)
        return False
    except loader.CircularDependency as err:
        _LOGGER.error(
            "Not setting up %s because it contains a circular dependency: "
            "%s -> %s", domain, err.from_domain, err.to_domain)
        return False

    # Process requirements as soon as possible, so we can import the component
    # without requiring imports to be in functions.
    try:
        await async_process_deps_reqs(hass, config, integration)
    except HomeAssistantError as err:
        log_error(str(err))
        return False

    processed_config = await conf_util.async_process_component_config(
        hass, config, integration)

    if processed_config is None:
        log_error("Invalid config.")
        return False

    start = timer()
    _LOGGER.info("Setting up %s", domain)

    try:
        component = integration.get_component()
    except ImportError:
        log_error("Unable to import component", False)
        return False

    if hasattr(component, 'PLATFORM_SCHEMA'):
        # Entity components have their own warning
        warn_task = None
    else:
        warn_task = hass.loop.call_later(
            SLOW_SETUP_WARNING, _LOGGER.warning,
            "Setup of %s is taking over %s seconds.",
            domain, SLOW_SETUP_WARNING)

    try:
        if hasattr(component, 'async_setup'):
            result = await component.async_setup(  # type: ignore
                hass, processed_config)
        elif hasattr(component, 'setup'):
            result = await hass.async_add_executor_job(
                component.setup, hass, processed_config)  # type: ignore
        else:
            log_error("No setup function defined.")
            return False
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Error during setup of component %s", domain)
        async_notify_setup_error(hass, domain, True)
        return False
    finally:
        end = timer()
        if warn_task:
            warn_task.cancel()
    _LOGGER.info("Setup of domain %s took %.1f seconds.", domain, end - start)

    if result is False:
        log_error("Component failed to initialize.")
        return False
    if result is not True:
        log_error("Component {!r} did not return boolean if setup was "
                  "successful. Disabling component.".format(domain))
        return False

    if hass.config_entries:
        for entry in hass.config_entries.async_entries(domain):
            await entry.async_setup(hass, integration=integration)

    hass.config.components.add(domain)

    # Cleanup
    if domain in hass.data[DATA_SETUP]:
        hass.data[DATA_SETUP].pop(domain)

    hass.bus.async_fire(
        EVENT_COMPONENT_LOADED,
        {ATTR_COMPONENT: domain}
    )

    return True


async def async_prepare_setup_platform(hass: core.HomeAssistant,
                                       hass_config: Dict,
                                       domain: str, platform_name: str) \
                                 -> Optional[ModuleType]:
    """Load a platform and makes sure dependencies are setup.

    This method is a coroutine.
    """
    platform_path = PLATFORM_FORMAT.format(domain=domain,
                                           platform=platform_name)

    def log_error(msg: str) -> None:
        """Log helper."""
        _LOGGER.error("Unable to prepare setup for platform %s: %s",
                      platform_name, msg)
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
    except ImportError:
        log_error("Platform not found.")
        return None

    # Already loaded
    if platform_path in hass.config.components:
        return platform

    # Platforms cannot exist on their own, they are part of their integration.
    # If the integration is not set up yet, and can be set up, set it up.
    if integration.domain not in hass.config.components:
        try:
            component = integration.get_component()
        except ImportError:
            log_error("Unable to import the component")
            return None

        if (hasattr(component, 'setup')
                or hasattr(component, 'async_setup')):
            if not await async_setup_component(
                    hass, integration.domain, hass_config
            ):
                log_error("Unable to set up component.")
                return None

    return platform


async def async_process_deps_reqs(
        hass: core.HomeAssistant, config: Dict,
        integration: loader.Integration) -> None:
    """Process all dependencies and requirements for a module.

    Module is a Python module of either a component or platform.
    """
    processed = hass.data.get(DATA_DEPS_REQS)

    if processed is None:
        processed = hass.data[DATA_DEPS_REQS] = set()
    elif integration.domain in processed:
        return

    if integration.dependencies and not await _async_process_dependencies(
            hass,
            config,
            integration.domain,
            integration.dependencies
    ):
        raise HomeAssistantError("Could not set up all dependencies.")

    if (not hass.config.skip_pip and integration.requirements and
            not await requirements.async_process_requirements(
                hass, integration.domain, integration.requirements)):
        raise HomeAssistantError("Could not install all requirements.")

    processed.add(integration.domain)


@core.callback
def async_when_setup(
        hass: core.HomeAssistant, component: str,
        when_setup_cb: Callable[
            [core.HomeAssistant, str], Awaitable[None]]) -> None:
    """Call a method when a component is setup."""
    async def when_setup() -> None:
        """Call the callback."""
        try:
            await when_setup_cb(hass, component)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error handling when_setup callback for %s',
                              component)

    # Running it in a new task so that it always runs after
    if component in hass.config.components:
        hass.async_create_task(when_setup())
        return

    unsub = None

    async def loaded_event(event: core.Event) -> None:
        """Call the callback."""
        if event.data[ATTR_COMPONENT] != component:
            return

        unsub()  # type: ignore
        await when_setup()

    unsub = hass.bus.async_listen(EVENT_COMPONENT_LOADED, loaded_event)
