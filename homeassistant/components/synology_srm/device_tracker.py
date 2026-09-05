"""Device tracker for Synology SRM routers."""

from datetime import datetime
from typing import Any, override

from homeassistant.components.device_tracker import DEFAULT_CONSIDER_HOME, ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import SynologySRMConfigEntry, SynologySRMDeviceScanner

ATTRIBUTE_ALIAS = {
    "band": None,
    "connection": None,
    "current_rate": None,
    "dev_type": None,
    "hostname": None,
    "ip6_addr": None,
    "ip_addr": None,
    "is_baned": "is_banned",
    "is_beamforming_on": None,
    "is_guest": None,
    "is_high_qos": None,
    "is_low_qos": None,
    "is_manual_dev_type": None,
    "is_manual_hostname": None,
    "is_online": None,
    "is_parental_controled": "is_parental_controlled",
    "is_qos": None,
    "is_wireless": None,
    "mac": None,
    "max_rate": None,
    "mesh_node_id": None,
    "rate_quality": None,
    "signalstrength": "signal_strength",
    "transferRXRate": "transfer_rx_rate",
    "transferTXRate": "transfer_tx_rate",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SynologySRMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for Synology SRM component."""
    scanner = config_entry.runtime_data
    tracked: set[str] = set()

    @callback
    def update_devices() -> None:
        """Update scanner entities."""
        add_entities(scanner, async_add_entities, tracked)

    scanner.async_on_close(
        async_dispatcher_connect(hass, scanner.signal_device_new, update_devices)
    )

    update_devices()


@callback
def add_entities(
    scanner: SynologySRMDeviceScanner,
    async_add_entities: AddConfigEntryEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new tracker entities from the router."""
    new_tracked = []

    for mac, device in scanner.devices.items():
        if mac in tracked:
            continue

        new_tracked.append(SynologySRMScannerEntity(scanner, device))
        tracked.add(mac)

    async_add_entities(new_tracked)


class SynologySRMScannerEntity(ScannerEntity):
    """A Synology SRM entity."""

    _attr_should_poll = False

    def __init__(
        self, scanner: SynologySRMDeviceScanner, device: dict[str, Any]
    ) -> None:
        """Init a Synology SRM device."""
        self._scanner = scanner
        self._device = device
        self._mac = format_mac(device["mac"])
        self._name = device.get("hostname", self._mac)
        self._connected = False
        self._last_activity: datetime | None = None

    @property
    @override
    def name(self) -> str | None:
        """Return device name."""
        return self._name

    @property
    @override
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        return self._device.get("hostname")

    @property
    @override
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self._device.get("ip_addr")

    @property
    @override
    def mac_address(self) -> str | None:
        """Return the MAC address of the device."""
        return self._mac

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._connected

    @property
    @override
    def icon(self) -> str:
        """Return device icon."""
        if self._connected:
            return "mdi:lan-connect"
        return "mdi:lan-disconnect"

    @property
    def last_activity(self) -> datetime | None:
        """Return device last activity."""
        return self._last_activity

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs: dict[str, Any] = {}

        if not self._connected:
            return {}

        for attribute, alias in ATTRIBUTE_ALIAS.items():
            if (value := self._device.get(attribute)) is None:
                continue
            attr = alias or attribute
            attrs[attr] = value
        return attrs

    @override
    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_on_demand_update()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._scanner.signal_device_update,
                self.async_on_demand_update,
            )
        )

    @callback
    def async_on_demand_update(self) -> None:
        """Update the device information."""
        utc_point_in_time = dt_util.utcnow()
        self._device = self._scanner.devices[self._mac]
        self._last_activity = self._device["last_activity"]

        self._connected = (
            self._last_activity is not None
            and (utc_point_in_time - self._last_activity).total_seconds()
            < DEFAULT_CONSIDER_HOME.total_seconds()
        )

        self.async_write_ha_state()
