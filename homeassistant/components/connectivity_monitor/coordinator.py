"""Coordinator support for the Connectivity Monitor integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from importlib import import_module
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_BLUETOOTH_ADDRESS,
    CONF_ESPHOME_DEVICE_ID,
    CONF_HOST,
    CONF_INACTIVE_TIMEOUT,
    CONF_MATTER_NODE_ID,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_ZHA_IEEE,
    DEFAULT_INACTIVE_TIMEOUT,
    DOMAIN,
    PROTOCOL_AD_DC,
    PROTOCOL_BLUETOOTH,
    PROTOCOL_ESPHOME,
    PROTOCOL_ICMP,
    PROTOCOL_MATTER,
    PROTOCOL_TCP,
    PROTOCOL_UDP,
    PROTOCOL_ZHA,
)
from .network import NetworkProbe

_LOGGER = logging.getLogger(__name__)


def _sensor_platform():
    """Import the sensor platform lazily to avoid a circular import."""
    return import_module(".sensor", __package__)


@dataclass(slots=True)
class ConnectivityMonitorRuntimeData:
    """Runtime data for a Connectivity Monitor config entry."""

    coordinator: ConnectivityMonitorCoordinator
    alert_handler: Any


type ConnectivityMonitorConfigEntry = ConfigEntry[ConnectivityMonitorRuntimeData]


def _target_key(target: dict) -> str:
    """Build a stable key for a configured target."""
    protocol = target[CONF_PROTOCOL]
    if protocol in (PROTOCOL_TCP, PROTOCOL_UDP, PROTOCOL_AD_DC):
        return f"{protocol}:{target[CONF_HOST]}:{target.get(CONF_PORT, 'none')}"
    if protocol == PROTOCOL_ICMP:
        return f"{protocol}:{target[CONF_HOST]}"
    if protocol == PROTOCOL_ZHA:
        return f"{protocol}:{target[CONF_ZHA_IEEE]}"
    if protocol == PROTOCOL_MATTER:
        return f"{protocol}:{target[CONF_MATTER_NODE_ID]}"
    if protocol == PROTOCOL_ESPHOME:
        return f"{protocol}:{target[CONF_ESPHOME_DEVICE_ID]}"
    if protocol == PROTOCOL_BLUETOOTH:
        return f"{protocol}:{target[CONF_BLUETOOTH_ADDRESS]}"
    return f"{protocol}:{target.get(CONF_HOST, 'unknown')}"


class ConnectivityMonitorCoordinator(DataUpdateCoordinator):
    """Central coordinator that polls all configured targets for one entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        targets: list[dict],
        update_interval: int,
        dns_server: str,
        config_entry: ConnectivityMonitorConfigEntry,
    ) -> None:
        """Initialize the shared coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{config_entry.entry_id}",
            update_interval=timedelta(seconds=update_interval),
        )
        self.targets = targets
        self._network_probe = NetworkProbe(hass, dns_server)

    def get_target_data(self, target: dict) -> dict[str, Any]:
        """Return the last known payload for a specific target."""
        return (self.data or {}).get(_target_key(target), {})

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data for all configured targets in a single polling cycle."""
        network_hosts = {
            target[CONF_HOST]
            for target in self.targets
            if target.get(CONF_PROTOCOL)
            not in (
                PROTOCOL_ZHA,
                PROTOCOL_MATTER,
                PROTOCOL_ESPHOME,
                PROTOCOL_BLUETOOTH,
            )
        }
        await asyncio.gather(
            *(self._network_probe.async_prepare_host(host) for host in network_hosts)
        )

        results = await asyncio.gather(
            *(self._async_update_target(target) for target in self.targets),
            return_exceptions=True,
        )

        data: dict[str, dict[str, Any]] = {}
        for target, result in zip(self.targets, results, strict=False):
            key = _target_key(target)
            if isinstance(result, Exception):
                _LOGGER.error("Update failed for target %s: %s", key, result)
                data[key] = self._default_result_for(target)
                continue
            data[key] = (
                result if isinstance(result, dict) else self._default_result_for(target)
            )

        return data

    def _default_result_for(self, target: dict) -> dict[str, Any]:
        """Return a protocol-specific empty payload."""
        if target[CONF_PROTOCOL] in (
            PROTOCOL_ZHA,
            PROTOCOL_MATTER,
            PROTOCOL_ESPHOME,
            PROTOCOL_BLUETOOTH,
        ):
            return {"active": False, "device_found": False}
        return {
            "connected": False,
            "latency": None,
            "resolved_ip": None,
            "mac_address": None,
        }

    async def _async_update_target(self, target: dict) -> dict[str, Any]:
        """Dispatch a target update to the protocol-specific probe."""
        protocol = target[CONF_PROTOCOL]
        if protocol in (PROTOCOL_TCP, PROTOCOL_UDP, PROTOCOL_ICMP, PROTOCOL_AD_DC):
            return await self._network_probe.async_update_target(target)
        if protocol == PROTOCOL_ZHA:
            return await self._async_update_zha_target(target)
        if protocol == PROTOCOL_MATTER:
            return await self._async_update_matter_target(target)
        if protocol == PROTOCOL_ESPHOME:
            return await self._async_update_esphome_target(target)
        if protocol == PROTOCOL_BLUETOOTH:
            return await self._async_update_bluetooth_target(target)

        _LOGGER.warning("Unsupported protocol '%s' for target %s", protocol, target)
        return self._default_result_for(target)

    async def _async_update_zha_target(self, target: dict) -> dict[str, Any]:
        """Fetch last_seen and activity state for a ZHA device."""
        sensor_platform = _sensor_platform()

        ieee = target[CONF_ZHA_IEEE]
        timeout_minutes = target.get(CONF_INACTIVE_TIMEOUT, DEFAULT_INACTIVE_TIMEOUT)
        last_seen = await sensor_platform.async_get_zha_device_last_seen(
            self.hass, ieee
        )

        active = False
        minutes_ago = None
        if last_seen is not None:
            elapsed = datetime.now().timestamp() - last_seen
            minutes_ago = round(elapsed / 60, 1)
            active = elapsed < (timeout_minutes * 60)

        return {
            "active": active,
            "last_seen": last_seen,
            "minutes_ago": minutes_ago,
        }

    async def _async_update_matter_target(self, target: dict) -> dict[str, Any]:
        """Fetch activity state for a Matter device."""
        sensor_platform = _sensor_platform()

        active = await sensor_platform.async_get_matter_device_active(
            self.hass, target[CONF_MATTER_NODE_ID]
        )
        return {
            "active": bool(active),
            "device_found": active is not None,
        }

    async def _async_update_esphome_target(self, target: dict) -> dict[str, Any]:
        """Fetch activity state for an ESPHome device."""
        sensor_platform = _sensor_platform()

        active = await sensor_platform.async_get_esphome_device_active(
            self.hass, target[CONF_ESPHOME_DEVICE_ID]
        )
        return {
            "active": bool(active),
            "device_found": active is not None,
        }

    async def _async_update_bluetooth_target(self, target: dict) -> dict[str, Any]:
        """Fetch activity details for a Bluetooth device."""
        sensor_platform = _sensor_platform()

        return await sensor_platform.async_get_bluetooth_device_details(
            self.hass, target[CONF_BLUETOOTH_ADDRESS]
        )
