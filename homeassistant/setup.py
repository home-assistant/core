"""All methods needed to bootstrap a Home Assistant instance."""
import asyncio
import logging
import logging.handlers
import os
from timeit import default_timer as timer

from types import ModuleType
from typing import Optional, Dict

import homeassistant.config as conf_util
from homeassistant.config import async_notify_setup_error
import homeassistant.core as core
import homeassistant.loader as loader
import homeassistant.util.package as pkg_util
from homeassistant.util.async import run_coroutine_threadsafe
from homeassistant.const import (
    EVENT_COMPONENT_LOADED, PLATFORM_FORMAT, CONSTRAINT_FILE)

_LOGGER = logging.getLogger(__name__)

ATTR_COMPONENT = 'component'

DATA_SETUP = 'setup_tasks'
DATA_PIP_LOCK = 'pip_lock'

SLOW_SETUP_WARNING = 10


def setup_component(hass: core.HomeAssistant, domain: str,
                    config: Optional[Dict]=None) -> bool:
    """Set up a component and all its dependencies."""
    return run_coroutine_threadsafe(
        async_setup_component(hass, domain, config), loop=hass.loop).result()


@asyncio.coroutine
def async_setup_component(hass: core.HomeAssistant, domain: str,
                          config: Optional[Dict]=None) -> bool:
    """Set up a component and all its dependencies.

    This method is a coroutine.
    """
    if domain in hass.config.components:
        return True

    setup_tasks = hass.data.get(DATA_SETUP)

    if setup_tasks is not None and domain in setup_tasks:
        return (yield from setup_tasks[domain])

    if config is None:
        config = {}

    if setup_tasks is None:
        setup_tasks = hass.data[DATA_SETUP] = {}

    task = setup_tasks[domain] = hass.async_add_job(
        _async_setup_component(hass, domain, config))

    return (yield from task)


@asyncio.coroutine
def _async_process_requirements(hass: core.HomeAssistant, name: str,
                                requirements) -> bool:
    """Install the requirements for a component.

    This method is a coroutine.
    """
    if hass.config.skip_pip:
        return True

    pip_lock = hass.data.get(DATA_PIP_LOCK)
    if pip_lock is None:
        pip_lock = hass.data[DATA_PIP_LOCK] = asyncio.Lock(loop=hass.loop)

    def pip_install(mod):
        """Install packages."""
        return pkg_util.install_package(
            mod, target=hass.config.path('deps'),
            constraints=os.path.join(
                os.path.dirname(__file__), CONSTRAINT_FILE))

    with (yield from pip_lock):
        for req in requirements:
            ret = yield from hass.async_add_job(pip_install, req)
            if not ret:
                _LOGGER.error("Not initializing %s because could not install "
                              "dependency %s", name, req)
                async_notify_setup_error(hass, name)
                return False

    return True


@asyncio.coroutine
def _async_process_dependencies(hass, config, name, dependencies):
    """Ensure all dependencies are set up."""
    blacklisted = [dep for dep in dependencies
                   if dep in loader.DEPENDENCY_BLACKLIST]

    if blacklisted:
        _LOGGER.error("Unable to setup dependencies of %s: "
                      "found blacklisted dependencies: %s",
                      name, ', '.join(blacklisted))
        return False

    tasks = [async_setup_component(hass, dep, config) for dep
             in dependencies]

    if not tasks:
        return True

    results = yield from asyncio.gather(*tasks, loop=hass.loop)

    failed = [dependencies[idx] for idx, res
              in enumerate(results) if not res]

    if failed:
        _LOGGER.error("Unable to setup dependencies of %s. "
                      "Setup failed for dependencies: %s",
                      name, ', '.join(failed))

        return False
    return True


@asyncio.coroutine
def _async_setup_component(hass: core.HomeAssistant,
                           domain: str, config) -> bool:
    """Set up a component for Home Assistant.

    This method is a coroutine.
    """
    def log_error(msg, link=True):
        """Log helper."""
        _LOGGER.error("Setup failed for %s: %s", domain, msg)
        async_notify_setup_error(hass, domain, link)

    component = loader.get_component(domain)

    if not component:
        log_error("Component not found.", False)
        return False

    # Validate no circular dependencies
    components = loader.load_order_component(domain)

    # OrderedSet is empty if component or dependencies could not be resolved
    if not components:
        log_error("Unable to resolve component or dependencies.")
        return False

    processed_config = \
        conf_util.async_process_component_config(hass, config, domain)

    if processed_config is None:
        log_error("Invalid config.")
        return False

    if not hass.config.skip_pip and hasattr(component, 'REQUIREMENTS'):
        req_success = yield from _async_process_requirements(
            hass, domain, component.REQUIREMENTS)
        if not req_success:
            log_error("Could not install all requirements.")
            return False

    if hasattr(component, 'DEPENDENCIES'):
        dep_success = yield from _async_process_dependencies(
            hass, config, domain, component.DEPENDENCIES)

        if not dep_success:
            log_error("Could not setup all dependencies.")
            return False

    async_comp = hasattr(component, 'async_setup')

    start = timer()
    _LOGGER.info("Setting up %s", domain)
    warn_task = hass.loop.call_later(
        SLOW_SETUP_WARNING, _LOGGER.warning,
        "Setup of %s is taking over %s seconds.", domain, SLOW_SETUP_WARNING)

    try:
        if async_comp:
            result = yield from component.async_setup(hass, processed_config)
        else:
            result = yield from hass.async_add_job(
                component.setup, hass, processed_config)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Error during setup of component %s", domain)
        async_notify_setup_error(hass, domain, True)
        return False
    finally:
        end = timer()
        warn_task.cancel()
    _LOGGER.info("Setup of domain %s took %.1f seconds.", domain, end - start)

    if result is False:
        log_error("Component failed to initialize.")
        return False
    elif result is not True:
        log_error("Component did not return boolean if setup was successful. "
                  "Disabling component.")
        loader.set_component(domain, None)
        return False

    hass.config.components.add(component.DOMAIN)

    # Cleanup
    if domain in hass.data[DATA_SETUP]:
        hass.data[DATA_SETUP].pop(domain)

    hass.bus.async_fire(
        EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: component.DOMAIN}
    )

    return True


@asyncio.coroutine
def async_prepare_setup_platform(hass: core.HomeAssistant, config, domain: str,
                                 platform_name: str) \
                                 -> Optional[ModuleType]:
    """Load a platform and makes sure dependencies are setup.

    This method is a coroutine.
    """
    platform_path = PLATFORM_FORMAT.format(domain, platform_name)

    def log_error(msg):
        """Log helper."""
        _LOGGER.error("Unable to prepare setup for platform %s: %s",
                      platform_path, msg)
        async_notify_setup_error(hass, platform_path)

    platform = loader.get_platform(domain, platform_name)

    # Not found
    if platform is None:
        log_error("Platform not found.")
        return None

    # Already loaded
    elif platform_path in hass.config.components:
        return platform

    # Load dependencies
    if hasattr(platform, 'DEPENDENCIES'):
        dep_success = yield from _async_process_dependencies(
            hass, config, platform_path, platform.DEPENDENCIES)

        if not dep_success:
            log_error("Could not setup all dependencies.")
            return None

    if not hass.config.skip_pip and hasattr(platform, 'REQUIREMENTS'):
        req_success = yield from _async_process_requirements(
            hass, platform_path, platform.REQUIREMENTS)

        if not req_success:
            log_error("Could not install all requirements.")
            return None

    return platform
