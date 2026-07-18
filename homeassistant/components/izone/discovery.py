"""Shared pizone discovery lifecycle for iZone.

Lazy: ``create_discovery`` runs only when HomeKit discovery or user-initiated
setup needs it (then reused for config-entry ``create_controller``). Not started
from bare domain ``async_setup``.

The library 1.4 path does not run a scan loop; this module owns a slow shared
``discovery.scan()`` timer so new bridges still surface (parity with the old
~5 minute discovery broadcast).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging

import pizone

from homeassistant import config_entries
from homeassistant.const import CONF_EXCLUDE, CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import aiohttp_client, discovery_flow
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    DATA_CONFIG,
    DATA_DISCOVERY_SERVICE,
    DISCOVERY_IDLE_SECONDS,
    DISCOVERY_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DiscoveryRuntime:
    """HA-owned lifecycle around the process-wide pizone discovery service."""

    service: pizone.DiscoveryService
    unsub_scan: Callable[[], None]
    unsub_stop: Callable[[], None]
    cancel_idle_stop: Callable[[], None] | None = None


def yaml_excluded_uids(hass: HomeAssistant) -> set[str]:
    """Return controller UIDs listed in deprecated YAML ``exclude``."""
    conf: ConfigType | None = hass.data.get(DATA_CONFIG)
    if not conf:
        return set()
    return set(conf.get(CONF_EXCLUDE, ()))


@callback
def async_note_integration_discovery(
    hass: HomeAssistant, endpoint: pizone.ControllerEndpoint
) -> None:
    """Start a config flow when discovery reports an unclaimed endpoint."""
    if endpoint.uid in yaml_excluded_uids(hass):
        return
    if _async_blocks_runtime_integration_discovery(hass):
        return
    discovery_flow.async_create_flow(
        hass,
        DOMAIN,
        context={
            "source": config_entries.SOURCE_INTEGRATION_DISCOVERY,
            "unique_id": endpoint.uid,
        },
        data={CONF_HOST: endpoint.host},
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


@callback
def _async_has_actionable_flows(hass: HomeAssistant) -> bool:
    """Return True when an in-progress iZone flow can create/update state."""
    return any(
        flow["context"].get("source") != config_entries.SOURCE_IGNORE
        for flow in hass.config_entries.flow.async_progress_by_handler(
            DOMAIN, include_uninitialized=True
        )
    )


@callback
def async_schedule_idle_stop(hass: HomeAssistant) -> None:
    """Schedule a delayed shutdown check for the shared discovery service."""
    runtime = hass.data.get(DATA_DISCOVERY_SERVICE)
    if runtime is None:
        return

    if runtime.cancel_idle_stop is not None:
        runtime.cancel_idle_stop()

    def _fire_idle_stop() -> None:
        runtime.cancel_idle_stop = None
        hass.async_create_task(async_maybe_stop_discovery(hass))

    runtime.cancel_idle_stop = hass.loop.call_later(
        DISCOVERY_IDLE_SECONDS, _fire_idle_stop
    ).cancel


async def async_ensure_discovery(hass: HomeAssistant) -> pizone.DiscoveryService:
    """Create and start the shared discovery service if needed.

    Call from HomeKit / user-initiated setup (and later from entry setup for
    ``create_controller``). Do not call from bare domain ``async_setup``.

    Raises:
        OSError: Discovery UDP socket could not be bound.
        RuntimeError: A process-global discovery service already exists outside
            this Home Assistant instance's tracking.
    """
    if runtime := hass.data.get(DATA_DISCOVERY_SERVICE):
        return runtime.service

    _LOGGER.debug("Starting iZone discovery service")

    @callback
    def _on_endpoint_discovered(endpoint: pizone.ControllerEndpoint) -> None:
        async_note_integration_discovery(hass, endpoint)
        async_schedule_idle_stop(hass)

    session = aiohttp_client.async_get_clientsession(hass)
    service = await pizone.create_discovery(
        on_endpoint_discovered=_on_endpoint_discovered,
        session=session,
    )

    async def _async_scan(_now: datetime | None = None) -> None:
        try:
            await service.scan()
        except ConnectionError:
            _LOGGER.debug("iZone discovery scan skipped; transport not ready")

    unsub_scan = async_track_time_interval(
        hass, _async_scan, DISCOVERY_SCAN_INTERVAL, cancel_on_shutdown=True
    )

    async def _async_stop_on_shutdown(_event: Event) -> None:
        # listen_once removes itself before this runs; avoid a second unsub.
        if runtime := hass.data.get(DATA_DISCOVERY_SERVICE):
            runtime.unsub_stop = lambda: None
        await async_stop_discovery(hass)

    unsub_stop = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, _async_stop_on_shutdown
    )

    hass.data[DATA_DISCOVERY_SERVICE] = DiscoveryRuntime(
        service=service,
        unsub_scan=unsub_scan,
        unsub_stop=unsub_stop,
    )

    # Initial broadcast — 1.4 create_discovery binds :7005 but does not scan.
    await _async_scan()
    async_schedule_idle_stop(hass)
    return service


async def async_maybe_stop_discovery(hass: HomeAssistant) -> None:
    """Stop discovery when nothing actionable remains."""
    if DATA_DISCOVERY_SERVICE not in hass.data:
        return

    if hass.config_entries.async_loaded_entries(DOMAIN) or _async_has_actionable_flows(
        hass
    ):
        async_schedule_idle_stop(hass)
        return

    await async_stop_discovery(hass)


async def async_stop_discovery(hass: HomeAssistant) -> None:
    """Stop the shared discovery service and clear HA tracking."""
    runtime = hass.data.pop(DATA_DISCOVERY_SERVICE, None)
    if runtime is None:
        return

    if runtime.cancel_idle_stop is not None:
        runtime.cancel_idle_stop()
        runtime.cancel_idle_stop = None

    runtime.unsub_scan()
    runtime.unsub_stop()
    await runtime.service.close()
    _LOGGER.debug("Stopped iZone discovery service")
