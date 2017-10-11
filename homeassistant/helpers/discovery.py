"""Helper methods to help with platform discovery.

There are two different types of discoveries that can be fired/listened for.
 - listen/discover is for services. These are targeted at a component.
 - listen_platform/discover_platform is for platforms. These are used by
   components to allow discovery of their platforms.
"""
import asyncio

from homeassistant import setup, core
from homeassistant.loader import bind_hass
from homeassistant.const import (
    ATTR_DISCOVERED, ATTR_SERVICE, EVENT_PLATFORM_DISCOVERED)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import DEPENDENCY_BLACKLIST
from homeassistant.util.async import run_callback_threadsafe

EVENT_LOAD_PLATFORM = 'load_platform.{}'
ATTR_PLATFORM = 'platform'


@bind_hass
def listen(hass, service, callback):
    """Set up listener for discovery of specific service.

    Service can be a string or a list/tuple.
    """
    run_callback_threadsafe(
        hass.loop, async_listen, hass, service, callback).result()


@core.callback
@bind_hass
def async_listen(hass, service, callback):
    """Set up listener for discovery of specific service.

    Service can be a string or a list/tuple.
    """
    if isinstance(service, str):
        service = (service,)
    else:
        service = tuple(service)

    @core.callback
    def discovery_event_listener(event):
        """Listen for discovery events."""
        if ATTR_SERVICE in event.data and event.data[ATTR_SERVICE] in service:
            hass.async_add_job(callback, event.data[ATTR_SERVICE],
                               event.data.get(ATTR_DISCOVERED))

    hass.bus.async_listen(EVENT_PLATFORM_DISCOVERED, discovery_event_listener)


@bind_hass
def discover(hass, service, discovered=None, component=None, hass_config=None):
    """Fire discovery event. Can ensure a component is loaded."""
    hass.add_job(
        async_discover(hass, service, discovered, component, hass_config))


@asyncio.coroutine
@bind_hass
def async_discover(hass, service, discovered=None, component=None,
                   hass_config=None):
    """Fire discovery event. Can ensure a component is loaded."""
    if component in DEPENDENCY_BLACKLIST:
        raise HomeAssistantError(
            'Cannot discover the {} component.'.format(component))

    if component is not None and component not in hass.config.components:
        yield from setup.async_setup_component(
            hass, component, hass_config)

    data = {
        ATTR_SERVICE: service
    }

    if discovered is not None:
        data[ATTR_DISCOVERED] = discovered

    hass.bus.async_fire(EVENT_PLATFORM_DISCOVERED, data)


@bind_hass
def listen_platform(hass, component, callback):
    """Register a platform loader listener."""
    run_callback_threadsafe(
        hass.loop, async_listen_platform, hass, component, callback
    ).result()


@bind_hass
def async_listen_platform(hass, component, callback):
    """Register a platform loader listener.

    This method must be run in the event loop.
    """
    service = EVENT_LOAD_PLATFORM.format(component)

    @core.callback
    def discovery_platform_listener(event):
        """Listen for platform discovery events."""
        if event.data.get(ATTR_SERVICE) != service:
            return

        platform = event.data.get(ATTR_PLATFORM)

        if not platform:
            return

        hass.async_run_job(
            callback, platform, event.data.get(ATTR_DISCOVERED)
        )

    hass.bus.async_listen(
        EVENT_PLATFORM_DISCOVERED, discovery_platform_listener)


@bind_hass
def load_platform(hass, component, platform, discovered=None,
                  hass_config=None):
    """Load a component and platform dynamically.

    Target components will be loaded and an EVENT_PLATFORM_DISCOVERED will be
    fired to load the platform. The event will contain:
        { ATTR_SERVICE = LOAD_PLATFORM + '.' + <<component>>
          ATTR_PLATFORM = <<platform>>
          ATTR_DISCOVERED = <<discovery info>> }

    Use `listen_platform` to register a callback for these events.
    """
    hass.add_job(
        async_load_platform(hass, component, platform, discovered,
                            hass_config))


@asyncio.coroutine
@bind_hass
def async_load_platform(hass, component, platform, discovered=None,
                        hass_config=None):
    """Load a component and platform dynamically.

    Target components will be loaded and an EVENT_PLATFORM_DISCOVERED will be
    fired to load the platform. The event will contain:
        { ATTR_SERVICE = LOAD_PLATFORM + '.' + <<component>>
          ATTR_PLATFORM = <<platform>>
          ATTR_DISCOVERED = <<discovery info>> }

    Use `listen_platform` to register a callback for these events.

    Warning: Do not yield from this inside a setup method to avoid a dead lock.
    Use `hass.loop.async_add_job(async_load_platform(..))` instead.

    This method is a coroutine.
    """
    if component in DEPENDENCY_BLACKLIST:
        raise HomeAssistantError(
            'Cannot discover the {} component.'.format(component))

    setup_success = True

    if component not in hass.config.components:
        setup_success = yield from setup.async_setup_component(
            hass, component, hass_config)

    # No need to fire event if we could not setup component
    if not setup_success:
        return

    data = {
        ATTR_SERVICE: EVENT_LOAD_PLATFORM.format(component),
        ATTR_PLATFORM: platform,
    }

    if discovered is not None:
        data[ATTR_DISCOVERED] = discovered

    hass.bus.async_fire(EVENT_PLATFORM_DISCOVERED, data)
