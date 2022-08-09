"""Tracking for bluetooth devices."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from datetime import datetime, timedelta
import logging
from typing import Final

import bluetooth  # pylint: disable=import-error
from bt_proximity import BluetoothRSSI
import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
)
from homeassistant.components.device_tracker.const import (
    CONF_SCAN_INTERVAL,
    CONF_TRACK_NEW,
    DEFAULT_TRACK_NEW,
    SCAN_INTERVAL,
    SourceType,
)
from homeassistant.components.device_tracker.legacy import (
    YAML_DEVICES,
    AsyncSeeCallback,
    Device,
    async_load_config,
)
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    BT_PREFIX,
    CONF_REQUEST_RSSI,
    DEFAULT_DEVICE_ID,
    DOMAIN,
    SERVICE_UPDATE,
)

_LOGGER: Final = logging.getLogger(__name__)

PLATFORM_SCHEMA: Final = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_TRACK_NEW): cv.boolean,
        vol.Optional(CONF_REQUEST_RSSI): cv.boolean,
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.All(
            vol.Coerce(int), vol.Range(min=-1)
        ),
    }
)


def is_bluetooth_device(device: Device) -> bool:
    """Check whether a device is a bluetooth device by its mac."""
    return device.mac is not None and device.mac[:3].upper() == BT_PREFIX


def discover_devices(device_id: int) -> list[tuple[str, str]]:
    """Discover Bluetooth devices."""
    try:
        result = bluetooth.discover_devices(
            duration=8,
            lookup_names=True,
            flush_cache=True,
            lookup_class=False,
            device_id=device_id,
        )
    except OSError as ex:
        # OSError is generally thrown if a bluetooth device isn't found
        _LOGGER.error("Couldn't discover bluetooth devices: %s", ex)
        return []
    _LOGGER.debug("Bluetooth devices discovered = %d", len(result))
    return result  # type: ignore[no-any-return]


async def see_device(
    hass: HomeAssistant,
    async_see: AsyncSeeCallback,
    mac: str,
    device_name: str,
    rssi: tuple[int] | None = None,
) -> None:
    """Mark a device as seen."""
    attributes = {}
    if rssi is not None:
        attributes["rssi"] = rssi

    await async_see(
        mac=f"{BT_PREFIX}{mac}",
        host_name=device_name,
        attributes=attributes,
        source_type=SourceType.BLUETOOTH,
    )


async def get_tracking_devices(hass: HomeAssistant) -> tuple[set[str], set[str]]:
    """
    Load all known devices.

    We just need the devices so set consider_home and home range to 0
    """
    yaml_path: str = hass.config.path(YAML_DEVICES)

    devices = await async_load_config(yaml_path, hass, timedelta(0))
    bluetooth_devices = [device for device in devices if is_bluetooth_device(device)]

    devices_to_track: set[str] = {
        device.mac[3:]
        for device in bluetooth_devices
        if device.track and device.mac is not None
    }
    devices_to_not_track: set[str] = {
        device.mac[3:]
        for device in bluetooth_devices
        if not device.track and device.mac is not None
    }

    return devices_to_track, devices_to_not_track


def lookup_name(mac: str) -> str | None:
    """Lookup a Bluetooth device name."""
    _LOGGER.debug("Scanning %s", mac)
    return bluetooth.lookup_name(mac, timeout=5)  # type: ignore[no-any-return]


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the Bluetooth Scanner."""
    device_id: int = config[CONF_DEVICE_ID]
    interval: timedelta = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    request_rssi: bool = config.get(CONF_REQUEST_RSSI, False)
    update_bluetooth_lock = asyncio.Lock()

    # If track new devices is true discover new devices on startup.
    track_new: bool = config.get(CONF_TRACK_NEW, DEFAULT_TRACK_NEW)
    _LOGGER.debug("Tracking new devices is set to %s", track_new)

    devices_to_track, devices_to_not_track = await get_tracking_devices(hass)

    if not devices_to_track and not track_new:
        _LOGGER.debug("No Bluetooth devices to track and not tracking new devices")

    if request_rssi:
        _LOGGER.debug("Detecting RSSI for devices")

    async def perform_bluetooth_update() -> None:
        """Discover Bluetooth devices and update status."""
        _LOGGER.debug("Performing Bluetooth devices discovery and update")
        tasks: list[Awaitable[None]] = []

        try:
            if track_new:
                devices = await hass.async_add_executor_job(discover_devices, device_id)
                for mac, _device_name in devices:
                    if mac not in devices_to_track and mac not in devices_to_not_track:
                        devices_to_track.add(mac)

            for mac in devices_to_track:
                friendly_name = await hass.async_add_executor_job(lookup_name, mac)
                if friendly_name is None:
                    # Could not lookup device name
                    continue

                rssi = None
                if request_rssi:
                    client = BluetoothRSSI(mac)
                    rssi = await hass.async_add_executor_job(client.request_rssi)
                    client.close()

                tasks.append(see_device(hass, async_see, mac, friendly_name, rssi))

            if tasks:
                await asyncio.wait(tasks)

        except bluetooth.BluetoothError:
            _LOGGER.exception("Error looking up Bluetooth device")

    async def update_bluetooth(now: datetime | None = None) -> None:
        """Lookup Bluetooth devices and update status."""
        # If an update is in progress, we don't do anything
        if update_bluetooth_lock.locked():
            _LOGGER.debug(
                "Previous execution of update_bluetooth is taking longer than the scheduled update of interval %s",
                interval,
            )
            return

        async with update_bluetooth_lock:
            await perform_bluetooth_update()

    async def handle_manual_update_bluetooth(call: ServiceCall) -> None:
        """Update bluetooth devices on demand."""
        await update_bluetooth()

    hass.async_create_task(update_bluetooth())
    async_track_time_interval(hass, update_bluetooth, interval)

    hass.services.async_register(DOMAIN, SERVICE_UPDATE, handle_manual_update_bluetooth)

    return True
