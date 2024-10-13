"""Provides diagnostics for TotalConnect."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = [
    "username",
    "Password",
    "Usercode",
    "UserID",
    "Serial Number",
    "serial_number",
    "sensor_serial_number",
]

# Private variable access needed for diagnostics


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    client = hass.data[DOMAIN][config_entry.entry_id].client

    data: dict[str, Any] = {}
    data["client"] = {
        "auto_bypass_low_battery": client.auto_bypass_low_battery,
        "module_flags": client._module_flags,  # noqa: SLF001
        "retry_delay": client.retry_delay,
        "invalid_credentials": client._invalid_credentials,  # noqa: SLF001
    }

    data["user"] = {
        "master": client._user._master_user,  # noqa: SLF001
        "user_admin": client._user._user_admin,  # noqa: SLF001
        "config_admin": client._user._config_admin,  # noqa: SLF001
        "security_problem": client._user.security_problem(),  # noqa: SLF001
        "features": client._user._features,  # noqa: SLF001
    }

    data["locations"] = []
    for location in client.locations.values():
        new_location = {
            "location_id": location.location_id,
            "name": location.location_name,
            "module_flags": location._module_flags,  # noqa: SLF001
            "security_device_id": location.security_device_id,
            "ac_loss": location.ac_loss,
            "low_battery": location.low_battery,
            "auto_bypass_low_battery": location.auto_bypass_low_battery,
            "cover_tampered": location.cover_tampered,
            "arming_state": location.arming_state,
        }

        new_location["devices"] = []
        for device in location.devices.values():
            new_device = {
                "device_id": device.deviceid,
                "name": device.name,
                "class_id": device.class_id,
                "serial_number": device.serial_number,
                "security_panel_type_id": device.security_panel_type_id,
                "serial_text": device.serial_text,
                "flags": device.flags,
            }
            new_location["devices"].append(new_device)

        new_location["partitions"] = []
        for partition in location.partitions.values():
            new_partition = {
                "partition_id": partition.partitionid,
                "name": partition.name,
                "is_stay_armed": partition.is_stay_armed,
                "is_fire_enabled": partition.is_fire_enabled,
                "is_common_enabled": partition.is_common_enabled,
                "is_locked": partition.is_locked,
                "is_new_partition": partition.is_new_partition,
                "is_night_stay_enabled": partition.is_night_stay_enabled,
                "exit_delay_timer": partition.exit_delay_timer,
            }
            new_location["partitions"].append(new_partition)

        new_location["zones"] = []
        for zone in location.zones.values():
            new_zone = {
                "zone_id": zone.zoneid,
                "description": zone.description,
                "partition": zone.partition,
                "status": zone.status,
                "zone_type_id": zone.zone_type_id,
                "can_be_bypassed": zone.can_be_bypassed,
                "battery_level": zone.battery_level,
                "signal_strength": zone.signal_strength,
                "sensor_serial_number": zone.sensor_serial_number,
                "loop_number": zone.loop_number,
                "response_type": zone.response_type,
                "alarm_report_state": zone.alarm_report_state,
                "supervision_type": zone.supervision_type,
                "chime_state": zone.chime_state,
                "device_type": zone.device_type,
            }
            new_location["zones"].append(new_zone)

        data["locations"].append(new_location)

    return async_redact_data(data, TO_REDACT)
