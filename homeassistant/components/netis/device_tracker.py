"""device_tracker platform for Netis Router.

Tracks the presence of devices connected to the router (both wired and
wireless). Uses the ``ScannerEntity`` base class so HA natively integrates
with the "Person" device tracker system.

Data source: ``devices_app.get_host_info`` returns a list of all known hosts
(even offline ones). Each host has ``online``, ``mac``, ``ip``, ``alias``,
connection type (wired/2.4G/5G/guest), and per-device traffic counters.

New devices are auto-discovered: a coordinator listener checks every poll
for MAC addresses we haven't seen before and creates tracker entities for
them dynamically.
"""

from __future__ import annotations

import logging

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NetisCoordinator
from .entity import NetisEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Netis device trackers."""
    coordinator: NetisCoordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        if coordinator.data is None:
            return
        new_entities = []
        for device in coordinator.data.devices:
            if device.mac in known:
                continue
            known.add(device.mac)
            new_entities.append(NetisTrackerEntity(coordinator, device.mac))
        if new_entities:
            async_add_entities(new_entities)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class NetisTrackerEntity(NetisEntity, ScannerEntity):
    """A single tracked device."""

    _attr_should_poll = False

    def __init__(self, coordinator: NetisCoordinator, mac: str) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{mac}"

    @property
    def _device(self):
        if not self.coordinator.data:
            return None
        for device in self.coordinator.data.devices:
            if device.mac == self._mac:
                return device
        return None

    @property
    def is_connected(self) -> bool:
        dev = self._device
        return bool(dev and dev.online)

    @property
    def source_type(self) -> SourceType:
        return SourceType.ROUTER

    @property
    def mac_address(self) -> str | None:
        return self._mac

    @property
    def hostname(self) -> str | None:
        dev = self._device
        return dev.name if dev else None

    @property
    def ip_address(self) -> str | None:
        dev = self._device
        if dev and dev.ip and dev.ip != "::":
            return dev.ip
        return None

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        dev = self._device
        if not dev:
            return None
        connection = (
            "wired" if dev.wired
            else "5g" if dev.wifi_5g
            else "2.4g" if dev.wifi_24g
            else "wireless"
        )
        return {
            "connection": connection,
            "guest": dev.guest,
            "up_speed_bps": dev.up_speed,
            "down_speed_bps": dev.down_speed,
            "up_bytes": dev.up_bytes,
            "down_bytes": dev.down_bytes,
            "connected_seconds": dev.connected_seconds,
        }
