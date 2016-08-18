"""Helper methods to help with platform discovery."""

from homeassistant import bootstrap
from homeassistant.const import (
    ATTR_DISCOVERED, ATTR_SERVICE, EVENT_PLATFORM_DISCOVERED)

EVENT_LOAD_PLATFORM = 'load_platform.{}'
ATTR_PLATFORM = 'platform'


def listen(hass, service, callback):
    """Setup listener for discovery of specific service.

    Service can be a string or a list/tuple.
    """
    if isinstance(service, str):
        service = (service,)
    else:
        service = tuple(service)

    def discovery_event_listener(event):
        """Listen for discovery events."""
        if ATTR_SERVICE in event.data and event.data[ATTR_SERVICE] in service:
            callback(event.data[ATTR_SERVICE], event.data.get(ATTR_DISCOVERED))

    hass.bus.listen(EVENT_PLATFORM_DISCOVERED, discovery_event_listener)


def discover(hass, service, discovered=None, component=None, hass_config=None):
    """Fire discovery event. Can ensure a component is loaded."""
    if component is not None:
        bootstrap.setup_component(hass, component, hass_config)

    data = {
        ATTR_SERVICE: service
    }

    if discovered is not None:
        data[ATTR_DISCOVERED] = discovered

    hass.bus.fire(EVENT_PLATFORM_DISCOVERED, data)


def listen_platform(hass, component, callback):
    """Register a platform loader listener."""
    service = EVENT_LOAD_PLATFORM.format(component)

    def discovery_platform_listener(event):
        """Listen for platform discovery events."""
        if event.data.get(ATTR_SERVICE) != service:
            return

        platform = event.data.get(ATTR_PLATFORM)

        if not platform:
            return

        callback(platform, event.data.get(ATTR_DISCOVERED))

    hass.bus.listen(EVENT_PLATFORM_DISCOVERED, discovery_platform_listener)


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
    def discover_platform():
        """Discover platform job."""
        # No need to fire event if we could not setup component
        if not bootstrap.setup_component(hass, component, hass_config):
            return

        data = {
            ATTR_SERVICE: EVENT_LOAD_PLATFORM.format(component),
            ATTR_PLATFORM: platform,
        }

        if discovered is not None:
            data[ATTR_DISCOVERED] = discovered

        hass.bus.fire(EVENT_PLATFORM_DISCOVERED, data)

    hass.add_job(discover_platform)
