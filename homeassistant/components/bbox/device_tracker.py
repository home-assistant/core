"""Support for French FAI Bouygues Bbox routers."""

from __future__ import annotations

from datetime import datetime
import logging

import pybbox
import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    SCAN_INTERVAL,
    ScannerEntity,
)
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "192.168.1.254"

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Bbox device tracker platform."""
    host: str = config[CONF_HOST]

    tracked: set[str] = set()
    connected_macs: set[str] = set()
    device_names: dict[str, str] = {}
    signal = f"bbox_update_{host}"

    async def async_scan_devices(now: datetime | None = None) -> None:
        """Scan for devices and update state."""
        _LOGGER.debug("Scanning")

        result = await hass.async_add_executor_job(_get_connected_devices, host)
        if result is None:
            return

        new_connected: set[str] = set()
        for device_data in result:
            if device_data["active"] != 1:
                continue
            mac = device_data["macaddress"]
            new_connected.add(mac)
            device_names[mac] = device_data["hostname"]

        connected_macs.clear()
        connected_macs.update(new_connected)

        new_macs = [mac for mac in new_connected if mac not in tracked]
        tracked.update(new_macs)
        if new_macs:
            async_add_entities(
                [
                    BboxDeviceTracker(
                        mac, device_names[mac], connected_macs, device_names, signal
                    )
                    for mac in new_macs
                ]
            )

        async_dispatcher_send(hass, signal)
        _LOGGER.debug("Scan successful")

    await async_scan_devices()

    scan_interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    async_track_time_interval(hass, async_scan_devices, scan_interval)


def _get_connected_devices(host: str) -> list[dict] | None:
    """Get connected devices from the Bbox router."""
    try:
        box = pybbox.Bbox(ip=host)
        return box.get_all_connected_devices()
    except Exception:
        _LOGGER.exception("Failed to scan Bbox devices")
        return None


class BboxDeviceTracker(ScannerEntity):
    """Representation of a Bbox tracked device."""

    _attr_should_poll = False

    def __init__(
        self,
        mac: str,
        name: str,
        connected_macs: set[str],
        device_names: dict[str, str],
        signal: str,
    ) -> None:
        """Initialize a Bbox device tracker entity."""
        self._mac = mac
        self._attr_name = name
        self._connected_macs = connected_macs
        self._device_names = device_names
        self._signal = signal

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._mac in self._connected_macs

    @property
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
        return self._device_names.get(self._mac)

    @property
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        return self._mac

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._signal,
                self._async_update_state,
            )
        )

    @callback
    def _async_update_state(self) -> None:
        """Update the device state."""
        self.async_write_ha_state()
