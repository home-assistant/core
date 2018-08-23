"""All methods needed to bootstrap a Home Assistant instance."""
import asyncio
import logging.handlers
from timeit import default_timer as timer

from types import ModuleType
from typing import Optional, Dict, List

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
                    config: Optional[Dict] = None) -> bool:
    """Set up a component and all its dependencies."""
    return run_coroutine_threadsafe(  # type: ignore
        async_setup_component(hass, domain, config), loop=hass.loop).result()


async def async_setup_component(hass: core.HomeAssistant, domain: str,
                                config: Optional[Dict] = None) -> bool:
    """Set up a component and all its dependencies.

    This method is a coroutine.
    """
    if domain in hass.config.components:
        return True

    setup_tasks = hass.data.get(DATA_SETUP)

    if setup_tasks is not None and domain in setup_tasks:
        return await setup_tasks[domain]  # type: ignore

    if config is None:
        config = {}

    if setup_tasks is None:
        setup_tasks = hass.data[DATA_SETUP] = {}

    task = setup_tasks[domain] = hass.async_create_task(
        _async_setup_component(hass, domain, config))

    return await task  # type: ignore


async def _async_process_dependencies(
        hass: core.HomeAssistant, config: Dict, name: str,
        dependencies: List[str]) -> bool:
    """Ensure all dependencies are set up."""
    blacklisted = [dep for dep in dependencies
                   if dep in loader.DEPENDENCY_BLACKLIST]

    if blacklisted:
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

    component = loader.get_component(hass, domain)

    if not component:
        log_error("Component not found.", False)
        return False

    # Validate no circular dependencies
    components = loader.load_order_component(hass, domain)

    # OrderedSet is empty if component or dependencies could not be resolved
    if not components:
        log_error("Unable to resolve component or dependencies.")
        return False

    processed_config = \
        conf_util.async_process_component_config(hass, config, domain)

    if processed_config is None:
        log_error("Invalid config.")
        return False

    try:
        await async_process_deps_reqs(hass, config, domain, component)
    except HomeAssistantError as err:
        log_error(str(err))
        return False

    start = timer()
    _LOGGER.info("Setting up %s", domain)

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
        else:
            result = await hass.async_add_executor_job(
                component.setup, hass, processed_config)  # type: ignore
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
        log_error("Component did not return boolean if setup was successful. "
                  "Disabling component.")
        loader.set_component(hass, domain, None)
        return False

    if hass.config_entries:
        for entry in hass.config_entries.async_entries(domain):
            await entry.async_setup(hass, component=component)

    hass.config.components.add(component.DOMAIN)  # type: ignore

    # Cleanup
    if domain in hass.data[DATA_SETUP]:
        hass.data[DATA_SETUP].pop(domain)

    hass.bus.async_fire(
        EVENT_COMPONENT_LOADED,
        {ATTR_COMPONENT: component.DOMAIN}  # type: ignore
    )

    return True


async def async_prepare_setup_platform(hass: core.HomeAssistant, config: Dict,
                                       domain: str, platform_name: str) \
                                 -> Optional[ModuleType]:
    """Load a platform and makes sure dependencies are setup.

    This method is a coroutine.
    """
    platform_path = PLATFORM_FORMAT.format(domain, platform_name)

    def log_error(msg: str) -> None:
        """Log helper."""
        _LOGGER.error("Unable to prepare setup for platform %s: %s",
                      platform_path, msg)
        async_notify_setup_error(hass, platform_path)

    platform = loader.get_platform(hass, domain, platform_name)

    # Not found
    if platform is None:
        log_error("Platform not found.")
        return None

    # Already loaded
    if platform_path in hass.config.components:
        return platform

    try:
        await async_process_deps_reqs(
            hass, config, platform_path, platform)
    except HomeAssistantError as err:
        log_error(str(err))
        return None

    return platform


async def async_process_deps_reqs(
        hass: core.HomeAssistant, config: Dict, name: str,
        module: ModuleType) -> None:
    """Process all dependencies and requirements for a module.

    Module is a Python module of either a component or platform.
    """
    processed = hass.data.get(DATA_DEPS_REQS)

    if processed is None:
        processed = hass.data[DATA_DEPS_REQS] = set()
    elif name in processed:
        return

    if hasattr(module, 'DEPENDENCIES'):
        dep_success = await _async_process_dependencies(
            hass, config, name, module.DEPENDENCIES)  # type: ignore

        if not dep_success:
            raise HomeAssistantError("Could not set up all dependencies.")

    if not hass.config.skip_pip and hasattr(module, 'REQUIREMENTS'):
        req_success = await requirements.async_process_requirements(
            hass, name, module.REQUIREMENTS)  # type: ignore

        if not req_success:
            raise HomeAssistantError("Could not install all requirements.")

    processed.add(name)
