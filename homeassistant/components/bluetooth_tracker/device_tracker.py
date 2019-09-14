"""Tracking for bluetooth devices."""
import asyncio
import logging
from typing import List, Set, Tuple, Optional

# pylint: disable=import-error
import bluetooth
from bt_proximity import BluetoothRSSI
import voluptuous as vol

from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.components.device_tracker.const import (
    CONF_SCAN_INTERVAL,
    CONF_TRACK_NEW,
    DOMAIN,
    SCAN_INTERVAL,
    SOURCE_TYPE_BLUETOOTH,
)
from homeassistant.components.device_tracker.legacy import (
    YAML_DEVICES,
    async_load_config,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType


_LOGGER = logging.getLogger(__name__)

BT_PREFIX = "BT_"

CONF_REQUEST_RSSI = "request_rssi"
CONF_DEVICE_ID = "device_id"
CONF_DISCOVER_NEW_DEVICES = "discover_new_devices"

DEFAULT_DEVICE_ID = -1
DEFAULT_DISCOVER_NEW_DEVICES = True
DEFAULT_REQUEST_RSSI = False

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_DISCOVER_NEW_DEVICES, default=DEFAULT_DISCOVER_NEW_DEVICES
        ): cv.boolean,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_REQUEST_RSSI, default=DEFAULT_REQUEST_RSSI): cv.boolean,
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.All(
            vol.Coerce(int), vol.Range(min=-1)
        ),
    }
)


def is_bluetooth_device(device) -> bool:
    """Check whether a device is a bluetooth device by its mac."""
    return device.mac and device.mac[:3].upper() == BT_PREFIX


def discover_devices(device_id: int) -> List[Tuple[str, str]]:
    """Discover Bluetooth devices."""
    result = bluetooth.discover_devices(
        duration=8,
        lookup_names=True,
        flush_cache=True,
        lookup_class=False,
        device_id=device_id,
    )
    _LOGGER.debug("Bluetooth devices discovered = %d", len(result))
    return result


async def see_device(
    hass: HomeAssistantType, async_see, mac: str, device_name: str, rssi=None
) -> None:
    """Mark a device as seen."""
    attributes = {}
    if rssi is not None:
        attributes["rssi"] = rssi

    await async_see(
        mac=f"{BT_PREFIX}{mac}",
        host_name=device_name,
        attributes=attributes,
        source_type=SOURCE_TYPE_BLUETOOTH,
    )


async def get_tracking_devices(hass: HomeAssistantType) -> Tuple[Set[str], Set[str]]:
    """
    Load all known devices.

    We just need the devices so set consider_home and home range to 0
    """
    yaml_path: str = hass.config.path(YAML_DEVICES)

    devices = await async_load_config(yaml_path, hass, 0)
    bluetooth_devices = [device for device in devices if is_bluetooth_device(device)]

    devices_to_track: Set[str] = {
        device.mac[3:] for device in bluetooth_devices if device.track
    }
    devices_to_not_track: Set[str] = {
        device.mac[3:] for device in bluetooth_devices if not device.track
    }

    return devices_to_track, devices_to_not_track


def lookup_name(mac: str) -> Optional[str]:
    """Lookup a Bluetooth device name."""
    _LOGGER.debug("Scanning %s", mac)
    return bluetooth.lookup_name(mac, timeout=5)


def get_discover_new_devices_value(config: dict) -> bool:
    """Get the configuration value of discovering new devices."""
    legacy_value = config.get(CONF_TRACK_NEW)
    if legacy_value is not None:
        _LOGGER.warning(
            "Using deprecated option '%s', switch to '%s'.",
            CONF_TRACK_NEW,
            CONF_DISCOVER_NEW_DEVICES,
        )
        return legacy_value

    return config.get(CONF_DISCOVER_NEW_DEVICES)


async def async_setup_scanner(
    hass: HomeAssistantType, config: dict, async_see, discovery_info=None
):
    """Set up the Bluetooth Scanner."""
    device_id: int = config.get(CONF_DEVICE_ID)
    interval = config.get(CONF_SCAN_INTERVAL)
    request_rssi: bool = config.get(CONF_REQUEST_RSSI)
    discover_new_devices = get_discover_new_devices_value(config)

    update_bluetooth_lock = asyncio.Lock()
    devices_to_track, devices_to_not_track = await get_tracking_devices(hass)

    if not devices_to_track and not discover_new_devices:
        _LOGGER.debug("No Bluetooth devices to track and not discovering new devices")

    if request_rssi:
        _LOGGER.debug("Detecting RSSI for devices")

    async def perform_bluetooth_update():
        """Discover Bluetooth devices and update status."""

        _LOGGER.debug("Performing Bluetooth devices discovery and update")
        tasks = []

        try:
            if discover_new_devices:
                devices = await hass.async_add_executor_job(discover_devices, device_id)
                for mac, device_name in devices:
                    if mac not in devices_to_track and mac not in devices_to_not_track:
                        devices_to_track.add(mac)

            for mac in devices_to_track:
                device_name = await hass.async_add_executor_job(lookup_name, mac)
                if device_name is None:
                    # Could not lookup device name
                    continue

                rssi = None
                if request_rssi:
                    client = BluetoothRSSI(mac)
                    rssi = await hass.async_add_executor_job(client.request_rssi)
                    client.close()

                tasks.append(see_device(hass, async_see, mac, device_name, rssi))

            if tasks:
                await asyncio.wait(tasks)

        except bluetooth.BluetoothError:
            _LOGGER.exception("Error looking up Bluetooth device")

    async def update_bluetooth(now=None):
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

    async def handle_manual_update_bluetooth(call):
        """Update bluetooth devices on demand."""

        await update_bluetooth()

    # Launch initial discovery and update
    hass.async_create_task(update_bluetooth())

    # Schedule interval for discovery and updates
    async_track_time_interval(hass, update_bluetooth, interval)

    # Allow manual triggering of discovery and update
    hass.services.async_register(
        DOMAIN, "bluetooth_tracker_update", handle_manual_update_bluetooth
    )

    return True
