"""Internal discovery service for iZone AC."""

import asyncio
from collections.abc import Callable
import logging
from typing import override

import pizone

from homeassistant import config_entries
from homeassistant.const import CONF_EXCLUDE, CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import aiohttp_client, discovery_flow
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    DATA_CONFIG,
    DATA_DISCOVERY_SERVICE,
    DISCOVERY_IDLE_SECONDS,
    DISPATCH_CONTROLLER_DISCONNECTED,
    DISPATCH_CONTROLLER_DISCOVERED,
    DISPATCH_CONTROLLER_RECONNECTED,
    DISPATCH_CONTROLLER_UPDATE,
    DISPATCH_ZONE_UPDATE,
    DOMAIN,
    TIMEOUT_DISCOVERY,
)

_LOGGER = logging.getLogger(__name__)


async def async_discover_controllers(
    hass: HomeAssistant,
    *,
    refresh: bool = False,
    wait_for_uid: str | None = None,
) -> dict[str, pizone.Controller]:
    """Return currently known controllers, optionally waiting for a UID during rescan.

    If ``refresh`` is true, waits for fresh discovery data using the pizone library's
    built-in coalescing and cool-down logic. When ``wait_for_uid`` is provided, returns
    as soon as that specific controller appears (or after the timeout).

    If discovery is not yet running, it is started first.

    Raises:
        OSError: Discovery service failed to start or controller fetch failed.
    """
    disco = await async_start_discovery_service(hass)
    assert disco.pi_disco is not None

    if not refresh:
        return await disco.pi_disco.fetch_controllers()

    if wait_for_uid is not None:
        await disco.pi_disco.fetch_controller(wait_for_uid, timeout=TIMEOUT_DISCOVERY)
        return await disco.pi_disco.fetch_controllers()

    return await disco.pi_disco.fetch_controllers(timeout=TIMEOUT_DISCOVERY)


def yaml_excluded_uids(hass: HomeAssistant) -> set[str]:
    """Return controller UIDs listed in deprecated YAML ``exclude``."""
    conf: ConfigType | None = hass.data.get(DATA_CONFIG)
    if not conf:
        return set()
    return set(conf.get(CONF_EXCLUDE, ()))


@callback
def async_note_integration_discovery(
    hass: HomeAssistant, ctrl: pizone.Controller
) -> None:
    """Start a config flow when the shared discovery service reports a controller."""
    if ctrl.device_uid in yaml_excluded_uids(hass):
        return
    if _async_blocks_runtime_integration_discovery(hass):
        return
    discovery_flow.async_create_flow(
        hass,
        DOMAIN,
        context={
            "source": config_entries.SOURCE_INTEGRATION_DISCOVERY,
            "unique_id": ctrl.device_uid,
        },
        data={CONF_HOST: ctrl.device_ip},
    )


@callback
def _async_blocks_runtime_integration_discovery(hass: HomeAssistant) -> bool:
    """Return True when an interactive setup flow should own the UI."""
    for flw in hass.config_entries.flow.async_progress_by_handler(
        DOMAIN, include_uninitialized=True
    ):
        src = flw["context"].get("source")
        if src == config_entries.SOURCE_USER:
            return True
    return False


class DiscoveryService(pizone.Listener):
    """Discovery data and interfacing with pizone library."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise discovery service."""
        super().__init__()
        self.hass = hass
        self.pi_disco: pizone.DiscoveryService | None = None
        self.remove_stop_listener: Callable[[], None] | None = None
        self.remove_config_flow_listener: Callable[[], None] | None = None
        self._idle_stop_handle: asyncio.TimerHandle | None = None

    @callback
    def async_schedule_idle_stop(self) -> None:
        """Schedule a delayed shutdown check for discovery service."""
        if self._idle_stop_handle is not None:
            self._idle_stop_handle.cancel()

        self._idle_stop_handle = self.hass.loop.call_later(
            DISCOVERY_IDLE_SECONDS,
            lambda: self.hass.async_create_task(
                async_maybe_stop_discovery_service(self.hass)
            ),
        )

    @callback
    def async_cancel_idle_stop(self) -> None:
        """Cancel any pending idle-stop timer."""
        if self._idle_stop_handle is not None:
            self._idle_stop_handle.cancel()
            self._idle_stop_handle = None

    # Listener interface
    @override
    def controller_discovered(self, ctrl: pizone.Controller) -> None:
        """Handle new controller discovery."""
        self.async_schedule_idle_stop()
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_DISCOVERED, ctrl)

    @override
    def controller_disconnected(self, ctrl: pizone.Controller, ex: Exception) -> None:
        """On disconnect from controller."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_DISCONNECTED, ctrl, ex)

    @override
    def controller_reconnected(self, ctrl: pizone.Controller) -> None:
        """On reconnect to controller."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_RECONNECTED, ctrl)

    @override
    def controller_update(self, ctrl: pizone.Controller) -> None:
        """System update message is received from the controller."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_UPDATE, ctrl)

    @override
    def zone_update(self, ctrl: pizone.Controller, zone: pizone.Zone) -> None:
        """Zone update message is received from the controller."""
        async_dispatcher_send(self.hass, DISPATCH_ZONE_UPDATE, ctrl, zone)


async def async_start_discovery_service(hass: HomeAssistant) -> DiscoveryService:
    """Set up the pizone internal discovery."""
    if disco := hass.data.get(DATA_DISCOVERY_SERVICE):
        # Already started
        return disco
    _LOGGER.debug("Starting iZone Discovery Service")

    # discovery local services
    disco = DiscoveryService(hass)

    # Start the pizone discovery service, disco is the listener
    session = aiohttp_client.async_get_clientsession(hass)
    disco.pi_disco = pizone.discovery(disco, session=session)

    @callback
    def _async_on_controller_discovered(ctrl: pizone.Controller) -> None:
        async_note_integration_discovery(hass, ctrl)

    disco.remove_config_flow_listener = async_dispatcher_connect(
        hass, DISPATCH_CONTROLLER_DISCOVERED, _async_on_controller_discovered
    )

    await disco.pi_disco.start_discovery()
    # Stored after start_discovery() so concurrent callers never receive a
    # partially-initialised DiscoveryService (no active UDP transport or scan loop).
    hass.data[DATA_DISCOVERY_SERVICE] = disco

    async def async_stop_discovery_on_shutdown(event: Event) -> None:
        """Stop discovery on Home Assistant shutdown."""
        # async_listen_once removes its own listener before running this callback.
        # Clear our handle so async_stop_discovery_service does not try to remove it
        # a second time, which logs an "unknown job listener" error.
        disco.remove_stop_listener = None
        await async_stop_discovery_service(hass)

    disco.remove_stop_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, async_stop_discovery_on_shutdown
    )
    disco.async_schedule_idle_stop()

    return disco


@callback
def _async_is_ignored_or_excluded_uid(hass: HomeAssistant, uid: str) -> bool:
    """Return True when UID is excluded by YAML or ignored/disabled by config entries."""
    if uid in yaml_excluded_uids(hass):
        return True

    return any(
        entry.unique_id == uid
        and (
            entry.source == config_entries.SOURCE_IGNORE
            or entry.disabled_by is not None
        )
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


@callback
def _async_has_actionable_entries(hass: HomeAssistant) -> bool:
    """Return True when there is at least one enabled, non-ignored iZone entry."""
    return any(
        hass.config_entries.async_entries(
            DOMAIN, include_ignore=False, include_disabled=False
        )
    )


@callback
def _async_has_actionable_flows(hass: HomeAssistant) -> bool:
    """Return True when there is an in-progress iZone flow that can create/update state."""
    return any(
        flow["context"].get("source") != config_entries.SOURCE_IGNORE
        for flow in hass.config_entries.flow.async_progress_by_handler(
            DOMAIN, include_uninitialized=True
        )
    )


async def async_maybe_stop_discovery_service(hass: HomeAssistant) -> None:
    """Stop discovery after idle delay when no actionable controllers remain."""
    if not (disco := hass.data.get(DATA_DISCOVERY_SERVICE)):
        return

    if _async_has_actionable_flows(hass) or _async_has_actionable_entries(hass):
        disco.async_schedule_idle_stop()
        return

    controllers_map = await disco.pi_disco.fetch_controllers()
    if not controllers_map:
        await async_stop_discovery_service(hass)
        return

    if all(
        _async_is_ignored_or_excluded_uid(hass, c.device_uid)
        for c in controllers_map.values()
    ):
        await async_stop_discovery_service(hass)
        return

    disco.async_schedule_idle_stop()


async def async_stop_discovery_service(hass: HomeAssistant) -> None:
    """Stop the discovery service."""
    if not (disco := hass.data.get(DATA_DISCOVERY_SERVICE)):
        return

    if disco.remove_stop_listener is not None:
        disco.remove_stop_listener()
        disco.remove_stop_listener = None

    if disco.remove_config_flow_listener is not None:
        disco.remove_config_flow_listener()
        disco.remove_config_flow_listener = None

    disco.async_cancel_idle_stop()

    await disco.pi_disco.close()
    del hass.data[DATA_DISCOVERY_SERVICE]

    _LOGGER.debug("Stopped iZone Discovery Service")
