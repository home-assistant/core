"""Helper methods to help with platform discovery.

There are two different types of discoveries that can be fired/listened for.
 - listen/discover is for services. These are targeted at a component.
 - listen_platform/discover_platform is for platforms. These are used by
   components to allow discovery of their platforms.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, TypedDict

from homeassistant import core, setup
from homeassistant.const import Platform
from homeassistant.loader import bind_hass

from ..util.signal_type import SignalTypeFormat
from .dispatcher import async_dispatcher_connect, async_dispatcher_send_internal
from .typing import ConfigType, DiscoveryInfoType

SIGNAL_PLATFORM_DISCOVERED: SignalTypeFormat[DiscoveryDict] = SignalTypeFormat(
    "discovery.platform_discovered_{}"
)
EVENT_LOAD_PLATFORM = "load_platform.{}"
ATTR_PLATFORM = "platform"
ATTR_DISCOVERED = "discovered"


class DiscoveryDict(TypedDict):
    """Discovery data."""

    service: str
    platform: str | None
    discovered: DiscoveryInfoType | None


@core.callback
@bind_hass
def async_listen(
    hass: core.HomeAssistant,
    service: str,
    callback: Callable[
        [str, DiscoveryInfoType | None], Coroutine[Any, Any, None] | None
    ],
) -> None:
    """Set up listener for discovery of specific service.

    Service can be a string or a list/tuple.
    """
    job = core.HassJob(callback, f"discovery listener {service}")

    @core.callback
    def _async_discovery_event_listener(discovered: DiscoveryDict) -> None:
        """Listen for discovery events."""
        hass.async_run_hass_job(job, discovered["service"], discovered["discovered"])

    async_dispatcher_connect(
        hass,
        SIGNAL_PLATFORM_DISCOVERED.format(service),
        _async_discovery_event_listener,
    )


@bind_hass
def discover(
    hass: core.HomeAssistant,
    service: str,
    discovered: DiscoveryInfoType,
    component: str,
    hass_config: ConfigType,
) -> None:
    """Fire discovery event. Can ensure a component is loaded."""
    hass.create_task(
        async_discover(hass, service, discovered, component, hass_config),
        f"discover {service} {component} {discovered}",
    )


@bind_hass
async def async_discover(
    hass: core.HomeAssistant,
    service: str,
    discovered: DiscoveryInfoType | None,
    component: str | None,
    hass_config: ConfigType,
) -> None:
    """Fire discovery event. Can ensure a component is loaded."""
    if component is not None and component not in hass.config.components:
        await setup.async_setup_component(hass, component, hass_config)

    data: DiscoveryDict = {
        "service": service,
        "platform": None,
        "discovered": discovered,
    }

    async_dispatcher_send_internal(
        hass, SIGNAL_PLATFORM_DISCOVERED.format(service), data
    )


@bind_hass
def async_listen_platform(
    hass: core.HomeAssistant,
    component: str,
    callback: Callable[[str, dict[str, Any] | None], Any],
) -> Callable[[], None]:
    """Register a platform loader listener.

    This method must be run in the event loop.
    """
    service = EVENT_LOAD_PLATFORM.format(component)
    job = core.HassJob(callback, f"platform loaded {component}")

    @core.callback
    def _async_discovery_platform_listener(discovered: DiscoveryDict) -> None:
        """Listen for platform discovery events."""
        if not (platform := discovered["platform"]):
            return
        hass.async_run_hass_job(job, platform, discovered.get("discovered"))

    return async_dispatcher_connect(
        hass,
        SIGNAL_PLATFORM_DISCOVERED.format(service),
        _async_discovery_platform_listener,
    )


@bind_hass
def load_platform(
    hass: core.HomeAssistant,
    component: Platform | str,
    platform: str,
    discovered: DiscoveryInfoType | None,
    hass_config: ConfigType,
) -> None:
    """Load a component and platform dynamically."""
    hass.create_task(
        async_load_platform(hass, component, platform, discovered, hass_config),
        f"discovery load_platform {component} {platform}",
    )


@bind_hass
async def async_load_platform(
    hass: core.HomeAssistant,
    component: Platform | str,
    platform: str,
    discovered: DiscoveryInfoType | None,
    hass_config: ConfigType,
) -> None:
    """Load a component and platform dynamically.

    Use `async_listen_platform` to register a callback for these events.

    Warning: This method can load a base component if its not loaded which
    can take a long time since base components currently have to import
    every platform integration listed under it to do config validation.
    To avoid waiting for this, use
    `hass.async_create_task(async_load_platform(..))` instead.
    """
    assert hass_config is not None, "You need to pass in the real hass config"

    setup_success = True

    if component not in hass.config.components:
        setup_success = await setup.async_setup_component(hass, component, hass_config)

    # No need to send signal if we could not set up component
    if not setup_success:
        return

    service = EVENT_LOAD_PLATFORM.format(component)

    data: DiscoveryDict = {
        "service": service,
        "platform": platform,
        "discovered": discovered,
    }

    async_dispatcher_send_internal(
        hass, SIGNAL_PLATFORM_DISCOVERED.format(service), data
    )
