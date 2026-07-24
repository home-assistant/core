"""Home Assistant discovery support for Global Caché iTach IP2IR."""

import logging
import time
from typing import TypedDict

from pyitach import (
    DEFAULT_PORT,
    ItachDiscoveryBeacon,
    ItachDiscoveryListener,
    async_discover_once as _async_discover_once,
    normalize_host as _normalize_host,
    normalize_uuid as _normalize_uuid,
)

from homeassistant.config_entries import SOURCE_DISCOVERY, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

FLOW_THROTTLE_SECONDS = 60.0
HOST_UPDATE_CONFIRMATIONS = 2


class _PendingHostUpdate(TypedDict):
    """Pending host update confirmation state."""

    host: str
    count: int


class ItachDiscoveryResult(TypedDict):
    """Discovered iTach device."""

    host: str
    uuid: str
    model: str


def _entry_title_for_host(host: str) -> str:
    """Return the default config entry title for a host."""
    return f"iTach IP2IR ({host})"


async def async_discover_once(timeout: float = 5.0) -> ItachDiscoveryResult | None:
    """Listen briefly for a single iTach beacon."""
    beacon = await _async_discover_once(timeout=timeout)
    if beacon is None:
        return None

    if beacon.model.lower() != "itachip2ir":
        return None

    return {
        "host": beacon.host,
        "uuid": beacon.uuid,
        "model": beacon.model,
    }


async def async_wait_for_device_id(
    host: str,
    timeout: float = 5.0,
    discovery: ItachDiscovery | None = None,
) -> str | None:
    """Wait for a beacon matching a specific host."""
    expected_host = _normalize_host(host)
    if expected_host is None:
        return None

    if discovery is not None:
        known_uuid = discovery.get_known_device_id(expected_host)
        if known_uuid is not None:
            return known_uuid

    result = await async_discover_once(timeout=timeout)

    if result is None:
        return None

    if _normalize_host(result["host"]) == expected_host:
        return result["uuid"]

    return None


class ItachDiscovery:
    """Coordinate Global Caché iTach UDP discovery with Home Assistant."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize discovery."""
        self._hass = hass
        self._listener: ItachDiscoveryListener | None = None
        self._known_devices: dict[str, str] = {}
        self._recent_flows: dict[str, float] = {}
        self._pending_host_updates: dict[str, _PendingHostUpdate] = {}

    async def async_start(self) -> None:
        """Start the UDP discovery listener."""
        if self._listener is not None:
            _LOGGER.debug("iTach discovery listener already running")
            return

        _LOGGER.debug("Starting iTach discovery listener")

        listener = ItachDiscoveryListener(self._async_handle_beacon)
        if not await listener.async_start():
            return

        self._listener = listener

    async def async_stop(self) -> None:
        """Stop the UDP discovery listener."""
        if self._listener is not None:
            await self._listener.async_stop()
            self._listener = None

        self._known_devices.clear()
        self._recent_flows.clear()
        self._pending_host_updates.clear()

    def get_known_device_id(self, host: str) -> str | None:
        """Return a known canonical UUID for a host if already seen."""
        normalized_host = _normalize_host(host)
        if normalized_host is None:
            return None

        return self._known_devices.get(normalized_host)

    async def _async_handle_beacon(self, beacon: ItachDiscoveryBeacon) -> None:
        """Handle a parsed iTach discovery beacon."""
        beacon_host = _normalize_host(beacon.host)
        unique_id = _normalize_uuid(beacon.uuid)
        model = beacon.model

        _LOGGER.debug(
            "Discovery parsed beacon host=%s model=%s uuid=%s",
            beacon_host,
            model,
            unique_id,
        )

        if beacon_host is None or unique_id is None or model is None:
            _LOGGER.debug(
                "Ignoring iTach beacon with missing host/model/uuid: host=%s model=%s uuid=%s",
                beacon_host,
                model,
                unique_id,
            )
            return

        if model.lower() != "itachip2ir":
            _LOGGER.debug(
                "Ignoring non-IP2IR Global Caché beacon host=%s model=%s uuid=%s",
                beacon_host,
                model,
                unique_id,
            )
            return

        self._known_devices[beacon_host] = unique_id

        configured_entry = self._configured_entry(unique_id)
        if configured_entry is not None:
            self._update_configured_host(configured_entry, beacon_host)
            return

        if self._is_flow_throttled(unique_id):
            _LOGGER.debug(
                "Discovered iTach flow throttled unique_id=%s host=%s",
                unique_id,
                beacon_host,
            )
            return

        self._mark_flow_started(unique_id)

        _LOGGER.info("Discovered iTach IP2IR at %s; starting config flow", beacon_host)

        try:
            result = await self._hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_DISCOVERY},
                data={
                    CONF_HOST: beacon_host,
                    CONF_PORT: DEFAULT_PORT,
                    "unique_id": unique_id,
                    "model": model,
                },
            )
        except Exception:
            _LOGGER.exception(
                "Failed starting discovery config flow for iTach host=%s unique_id=%s",
                beacon_host,
                unique_id,
            )
            return

        _LOGGER.debug(
            "Discovery config flow result for iTach host=%s unique_id=%s: %s",
            beacon_host,
            unique_id,
            result,
        )

    def _configured_entry(self, unique_id: str) -> ConfigEntry | None:
        """Return configured entry matching canonical unique ID."""
        normalized_unique_id = _normalize_uuid(unique_id)

        if normalized_unique_id is None:
            return None

        for entry in self._hass.config_entries.async_entries(DOMAIN):
            if _normalize_uuid(entry.unique_id) == normalized_unique_id:
                return entry

        return None

    def _is_already_configured(self, unique_id: str) -> bool:
        """Return whether a canonical unique ID is already configured."""
        return self._configured_entry(unique_id) is not None

    def _update_configured_host(self, entry: ConfigEntry, host: str) -> None:
        """Update stored host from discovery for an existing entry."""
        if entry.options.get(CONF_HOST):
            return

        discovered_host = _normalize_host(host)
        current_host = _normalize_host(str(entry.data.get(CONF_HOST, "")))

        if discovered_host is None or current_host == discovered_host:
            return

        if not self._host_update_confirmed(entry.entry_id, discovered_host):
            _LOGGER.debug(
                "Pending discovered host update for iTach %s from %s to %s",
                entry.unique_id,
                current_host,
                discovered_host,
            )
            return

        old_title = _entry_title_for_host(current_host) if current_host else entry.title
        new_title = (
            _entry_title_for_host(discovered_host)
            if entry.title in {old_title, "iTach IP2IR"}
            else entry.title
        )

        self._hass.config_entries.async_update_entry(
            entry,
            title=new_title,
            data={
                **entry.data,
                CONF_HOST: discovered_host,
                CONF_PORT: entry.data.get(CONF_PORT, DEFAULT_PORT),
            },
        )
        self._pending_host_updates.pop(entry.entry_id, None)

        _LOGGER.info(
            "Updated discovered host for iTach %s from %s to %s",
            entry.unique_id,
            current_host,
            discovered_host,
        )

        self._schedule_entry_reload(entry)

    def _host_update_confirmed(self, entry_id: str, discovered_host: str) -> bool:
        """Return whether a discovered host change has been seen enough times."""
        pending = self._pending_host_updates.get(entry_id)

        if pending is None or pending["host"] != discovered_host:
            self._pending_host_updates[entry_id] = {
                "host": discovered_host,
                "count": 1,
            }
            return HOST_UPDATE_CONFIRMATIONS <= 1

        pending["count"] += 1
        return pending["count"] >= HOST_UPDATE_CONFIRMATIONS

    def _schedule_entry_reload(self, entry: ConfigEntry) -> None:
        """Schedule a reload for an updated entry."""
        self._hass.config_entries.async_schedule_reload(entry.entry_id)

    def _is_flow_throttled(self, unique_id: str) -> bool:
        """Return true if a discovery flow was recently started."""
        self._prune_recent_flows()

        last_started = self._recent_flows.get(unique_id)
        if last_started is None:
            return False

        return (time.monotonic() - last_started) < FLOW_THROTTLE_SECONDS

    def _mark_flow_started(self, unique_id: str) -> None:
        """Record that a discovery flow was started."""
        self._prune_recent_flows()
        self._recent_flows[unique_id] = time.monotonic()

    def _prune_recent_flows(self) -> None:
        """Remove expired discovery flow throttle entries."""
        now = time.monotonic()

        expired = [
            unique_id
            for unique_id, started_at in self._recent_flows.items()
            if (now - started_at) >= FLOW_THROTTLE_SECONDS
        ]

        for unique_id in expired:
            self._recent_flows.pop(unique_id, None)
