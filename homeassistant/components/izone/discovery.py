"""Internal discovery service for  iZone AC."""

import asyncio
from collections.abc import Callable
import logging

import pizone

from homeassistant import config_entries
from homeassistant.const import CONF_EXCLUDE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .config_flow import async_note_integration_discovery
from .const import (
    DATA_CONFIG,
    DATA_DISCOVERY_SERVICE,
    DISCOVERY_IDLE_SECONDS,
    DISPATCH_CONTROLLER_DISCONNECTED,
    DISPATCH_CONTROLLER_DISCOVERED,
    DISPATCH_CONTROLLER_RECONNECTED,
    DISPATCH_CONTROLLER_UPDATE,
    DISPATCH_ZONE_UPDATE,
    IZONE,
)

_LOGGER = logging.getLogger(__name__)


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
    def controller_discovered(self, ctrl: pizone.Controller) -> None:
        """Handle new controller discovery."""
        self.async_schedule_idle_stop()
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_DISCOVERED, ctrl)

    def controller_disconnected(self, ctrl: pizone.Controller, ex: Exception) -> None:
        """On disconnect from controller."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_DISCONNECTED, ctrl, ex)

    def controller_reconnected(self, ctrl: pizone.Controller) -> None:
        """On reconnect to controller."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_RECONNECTED, ctrl)

    def controller_update(self, ctrl: pizone.Controller) -> None:
        """System update message is received from the controller."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_UPDATE, ctrl)

    def zone_update(self, ctrl: pizone.Controller, zone: pizone.Zone) -> None:
        """Zone update message is received from the controller."""
        async_dispatcher_send(self.hass, DISPATCH_ZONE_UPDATE, ctrl, zone)


async def async_start_discovery_service(hass: HomeAssistant):
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
    """Return True when UID is excluded by YAML or ignored by config entries."""
    conf = hass.data.get(DATA_CONFIG)
    if conf and uid in conf.get(CONF_EXCLUDE, []):
        return True

    if not (entries := hass.config_entries.async_entries(IZONE)):
        return True

    return any(entry.unique_id == uid for entry in entries)


@callback
def _async_has_actionable_entries(hass: HomeAssistant) -> bool:
    """Return True when there is at least one enabled, non-ignored iZone entry."""
    return bool(hass.config_entries.async_entries(IZONE))


@callback
def _async_has_actionable_flows(hass: HomeAssistant) -> bool:
    """Return True when there is an in-progress iZone flow that can create/update state."""
    return any(
        flow["context"].get("source") != config_entries.SOURCE_IGNORE
        for flow in hass.config_entries.flow.async_progress_by_handler(
            IZONE, include_uninitialized=True
        )
    )


async def async_maybe_stop_discovery_service(hass: HomeAssistant) -> None:
    """Stop discovery after idle delay when no actionable controllers remain."""
    if not (disco := hass.data.get(DATA_DISCOVERY_SERVICE)):
        return

    if _async_has_actionable_flows(hass) or _async_has_actionable_entries(hass):
        disco.async_schedule_idle_stop()
        return

    controllers = list(disco.pi_disco.controllers.values())
    if not controllers:
        await async_stop_discovery_service(hass)
        return

    if all(_async_is_ignored_or_excluded_uid(hass, c.device_uid) for c in controllers):
        await async_stop_discovery_service(hass)
        return

    disco.async_schedule_idle_stop()


async def async_stop_discovery_service(hass: HomeAssistant):
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
