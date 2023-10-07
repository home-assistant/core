"""Diagnostic module for Olarm."""
import asyncio
from collections.abc import Mapping
import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_ALARM_CODE, CONF_OLARM_DEVICES, DOMAIN, VERSION


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Mapping[str, Any]:
    """Return the device diagnostic file."""
    return await async_get_device_diagnostics(
        hass, entry, DeviceEntry(name="All Devices")
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device1: DeviceEntry
) -> Mapping[str, Any]:
    """Return the device diagnostic file."""
    devices = hass.data[DOMAIN]["devices"]
    try:
        errors = [
            log_entry.to_dict()
            for key, log_entry in hass.data["system_log"].records.items()
            if DOMAIN in key
        ]

        # Removing device_id from url
        ind1: int = 0
        ind2: int = 0
        for error in errors:
            for er in error["message"]:
                if "devices/" in er:
                    error["message"][ind2] = (
                        error["message"][ind2].split("devices/")[0]
                        + "devices/the_device_id')"
                    )

                ind2 = ind2 + 1

            ind1 = ind1 + 1

    except (KeyError, IndexError) as e:
        errors.append(f"{type(e).__name__}: {e}")

    index: int = 0
    config: dict = {str: str}

    for device in devices:
        # Removing unneeded detail
        device.pop("deviceTimestamp")
        device.pop("deviceSerial")
        device.pop("deviceTriggers")
        device["deviceState"].pop("timestamp")
        device["deviceState"].pop("cmdRecv")
        device["deviceState"].pop("type")
        device["deviceState"].pop("areasDetail")
        device["deviceState"].pop("areasStamp")
        device["deviceState"].pop("zones")
        device["deviceState"].pop("zonesStamp")
        device["deviceProfile"].pop("zonesLabels")
        device["deviceProfile"].pop("zonesTypes")
        device["deviceProfile"].pop("pgmLabels")
        device["deviceProfile"].pop("ukeysLabels")
        device["deviceProfile"].pop("ukeysControl")
        # Electric fence config.
        if device["deviceProfile"]["fenceLabels"] is not None:
            device["deviceProfile"].pop("fenceLabels")
            device["deviceProfile"].pop("fenceZonesLabels")
            device["deviceProfile"].pop("fenceGatesLabels")

        # Updating the devices
        devices[index] = device

        index += index

        if device1.name != "All Devices":
            dev_id = device1.identifiers.pop()[1]
            if device["deviceId"] != dev_id:
                continue

        # Checking if the Olarm API allows the device to be used.
        data = await hass.data[DOMAIN][device["deviceId"]].api.check_credentials()

        config[device["deviceName"]] = {}
        config[device["deviceName"]]["auth_success"] = data["auth_success"]
        config[device["deviceName"]]["error"] = data["error"]
        config[device["deviceName"]]["code_required"] = (
            entry.data[CONF_ALARM_CODE] is not None
        )

        # Removing the device Id
        device["deviceId"] = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        devices[index] = device

        await asyncio.sleep(2)

    config["scan_interval"] = entry.data[CONF_SCAN_INTERVAL]

    uuid = (
        str(round(datetime.datetime.now().timestamp()))
        + str(len(entry.data[CONF_OLARM_DEVICES]))
        + str(entry.entry_id)
        + VERSION
    )
    return {
        "version": VERSION,
        "config": config,
        "errors": errors,
        "enabled_devices": entry.data[CONF_OLARM_DEVICES],
        "amount_of_enabled_devices": len(entry.data[CONF_OLARM_DEVICES]),
        "all_devices": devices,
        "amount_of_total_devices": len(devices),
        "uuid": uuid,
        "entry_id": str(entry.entry_id),
    }
