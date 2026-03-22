"""Support for Swisscom routers (Internet-Box)."""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime
import logging

import requests
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

DEFAULT_IP = "192.168.1.1"

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_HOST, default=DEFAULT_IP): cv.string}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Swisscom device tracker platform."""
    host: str = config[CONF_HOST]

    # Test the router is accessible
    data = await hass.async_add_executor_job(_get_swisscom_data, host)
    if data is None:
        return

    tracked: set[str] = set()
    connected_macs: set[str] = set()
    device_names: dict[str, str] = {}
    signal = f"swisscom_update_{host}"

    async def async_scan_devices(now: datetime | None = None) -> None:
        """Scan for devices and update state."""
        _LOGGER.debug("Loading data from Swisscom Internet Box")
        data = await hass.async_add_executor_job(_get_swisscom_data, host)
        if not data:
            return

        active_clients = [
            client for client in data.values() if client["status"]
        ]

        new_connected = {client["mac"] for client in active_clients}
        for client in active_clients:
            device_names[client["mac"]] = client["host"]

        connected_macs.clear()
        connected_macs.update(new_connected)

        new_macs = [mac for mac in new_connected if mac not in tracked]
        tracked.update(new_macs)
        if new_macs:
            async_add_entities(
                [
                    SwisscomDeviceTracker(
                        mac, device_names[mac], connected_macs, device_names, signal
                    )
                    for mac in new_macs
                ]
            )

        async_dispatcher_send(hass, signal)

    await async_scan_devices()

    scan_interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    async_track_time_interval(hass, async_scan_devices, scan_interval)


def _get_swisscom_data(host: str) -> dict | None:
    """Retrieve data from Swisscom and return parsed result."""
    url = f"http://{host}/ws"
    headers = {"Content-Type": "application/x-sah-ws-4-call+json"}
    data = (
        '{"service":"Devices", "method":"get",'
        '"parameters":{"expression":"lan and not self"}}'
    )

    devices: dict = {}

    try:
        request = requests.post(url, headers=headers, data=data, timeout=10)
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.ConnectTimeout,
    ):
        _LOGGER.debug("No response from Swisscom Internet Box")
        return devices

    if "status" not in request.json():
        _LOGGER.debug("No status in response from Swisscom Internet Box")
        return devices

    for device in request.json()["status"]:
        with suppress(KeyError, requests.exceptions.RequestException):
            devices[device["Key"]] = {
                "ip": device["IPAddress"],
                "mac": device["PhysAddress"],
                "host": device["Name"],
                "status": device["Active"],
            }
    return devices


class SwisscomDeviceTracker(ScannerEntity):
    """Representation of a Swisscom tracked device."""

    _attr_should_poll = False

    def __init__(
        self,
        mac: str,
        name: str,
        connected_macs: set[str],
        device_names: dict[str, str],
        signal: str,
    ) -> None:
        """Initialize a Swisscom device tracker entity."""
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
