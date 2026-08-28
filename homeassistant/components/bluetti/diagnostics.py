"""Diagnostics support for the BLUETTI integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import BluettiConfigEntry

TO_REDACT = {"token", "access_token", "refresh_token", "products"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BluettiConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data

    # device_id is the device's real BLUETTI serial number, tied to
    # ownership/warranty - it shouldn't be exposed in a diagnostics dump any
    # more than a token would be. Alias it to a stable per-dump "device_N"
    # instead of blanking it outright, so multiple devices in one dump can
    # still be told apart and cross-referenced against "coordinators" below.
    # Built from every serial-bearing source, not just the live runtime
    # devices: a device enabled in entry.options can be absent from
    # runtime_data (e.g. its product data went stale between an account
    # rebind and the next reload), and the entry_options aliasing below
    # would otherwise fall through to the raw, unaliased serial for it.
    all_device_ids = {
        device.device_id for device in runtime_data.bluetti_devices.devices
    }
    all_device_ids.update(entry.options.get("devices", []))
    all_device_ids.update(entry.options.get("modbus", {}))
    aliases = {
        device_id: f"device_{i + 1}"
        for i, device_id in enumerate(sorted(all_device_ids))
    }

    devices = [
        {
            "device_id": aliases[device.device_id],
            "model": device.model,
            "online": device.online,
            "states": [
                {
                    "fn_code": state.fn_code,
                    "fn_type": state.fn_type,
                    "fn_value": state.fn_value,
                    # Shows whether a SENSOR-type state was actually turned
                    # into an entity, or silently skipped because its
                    # sensorType isn't recognized (see sensor.SENSOR_MAP) -
                    # otherwise that's only visible in the logs.
                    "sensor_info": state.sensor_info or None,
                }
                for state in device.states
            ],
        }
        for device in runtime_data.bluetti_devices.devices
    ]

    coordinators = {
        aliases.get(device_id, device_id): {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
        }
        for device_id, coordinator in runtime_data.coordinators.items()
    }

    entry_options = dict(entry.options)
    if "devices" in entry_options:
        # Same real serial numbers as above (the enabled-devices list), so
        # alias them the same way rather than leaving them in the clear here.
        entry_options["devices"] = [
            aliases.get(sn, sn) for sn in entry_options["devices"]
        ]
    if "modbus" in entry_options:
        # Keyed by the same real serial numbers - alias the keys too, or a
        # device with local Modbus configured would leak its serial here
        # even though "devices" above was redacted. The host is sensitive
        # local-network information (the device's LAN IP or hostname) in
        # its own right, independently of which device it belongs to.
        entry_options["modbus"] = {
            aliases.get(sn, sn): async_redact_data(config, {"host"})
            for sn, config in entry_options["modbus"].items()
        }

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": entry_options,
        "devices": devices,
        "coordinators": coordinators,
    }
