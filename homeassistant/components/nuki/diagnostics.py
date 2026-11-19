"""Diagnostics support for Nuki."""

from typing import Any

from pynuki import NukiLock, NukiOpener
from pynuki.device import NukiDevice

from homeassistant.core import HomeAssistant

from .const import CONF_ENCRYPT_TOKEN
from .coordinator import NukiConfigEntry


def _device_diagnostics(device: NukiDevice) -> dict[str, Any]:
    """Return the diagnostics of a lock or opener."""
    # The name and Nuki ID are left out, as they identify the device.
    return {
        "device_type": device.device_type,
        "firmware_version": device.firmware_version,
        "mode": device.mode,
        "state": device.state,
        "state_name": device.state_name,
        "battery_critical": device.battery_critical,
    }


def _lock_diagnostics(lock: NukiLock) -> dict[str, Any]:
    """Return the diagnostics of a lock."""
    return {
        **_device_diagnostics(lock),
        "battery_charging": lock.battery_charging,
        "battery_charge": lock.battery_charge,
        "keypad_battery_critical": lock.battery_critical_keypad,
        "door_sensor_state": lock.door_sensor_state,
        "door_sensor_state_name": lock.door_sensor_state_name,
    }


def _opener_diagnostics(opener: NukiOpener) -> dict[str, Any]:
    """Return the diagnostics of an opener."""
    return {
        **_device_diagnostics(opener),
        "ring_action_state": opener.ring_action_state,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NukiConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    # The bridge info is cached during setup, so this does not reach out to
    # the bridge. It is run in the executor as pynuki fetches it again with a
    # blocking call when the cache is empty. Values that change over time,
    # like the uptime, are left out, as they would be stale.
    info: dict[str, Any] = await hass.async_add_executor_job(data.bridge.info)
    versions = info.get("versions", {})

    # The host, port, and token are left out, as well as the hardware and
    # server IDs of the bridge, as they identify the bridge. The scan results
    # are left out, as they hold the names and IDs of nearby devices.
    return {
        "config_entry": {
            CONF_ENCRYPT_TOKEN: entry.data.get(CONF_ENCRYPT_TOKEN, True),
        },
        "coordinator": {
            "last_update_success": data.coordinator.last_update_success,
        },
        "bridge": {
            "bridge_type": info.get("bridgeType"),
            "firmware_version": versions.get("firmwareVersion"),
            "wifi_firmware_version": versions.get("wifiFirmwareVersion"),
        },
        "locks": [_lock_diagnostics(lock) for lock in data.locks],
        "openers": [_opener_diagnostics(opener) for opener in data.openers],
    }
