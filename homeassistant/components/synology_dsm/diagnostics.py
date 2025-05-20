"""Diagnostics support for Synology DSM."""

from __future__ import annotations

from typing import Any

from homeassistant.components.camera import diagnostics as camera_diagnostics
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_TOKEN
from .coordinator import SynologyDSMConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, CONF_DEVICE_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SynologyDSMConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    syno_api = data.api
    dsm_info = syno_api.dsm.information

    diag_data: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": {
            "model": dsm_info.model,
            "version": dsm_info.version_string,
            "ram": dsm_info.ram,
            "uptime": dsm_info.uptime,
            "temperature": dsm_info.temperature,
        },
        "external_usb": {"devices": {}, "partitions": {}},
        "network": {"interfaces": {}},
        "storage": {"disks": {}, "volumes": {}},
        "surveillance_station": {"cameras": {}, "camera_diagnostics": {}},
        "upgrade": {},
        "utilisation": {},
        "is_system_loaded": True,
        "api_details": {
            "fetching_entities": syno_api._fetching_entities,  # noqa: SLF001
        },
    }

    if syno_api.external_usb is not None:
        for device in syno_api.external_usb.get_devices.values():
            if device is not None:
                diag_data["external_usb"]["devices"][device.device_id] = {
                    "name": device.device_name,
                    "manufacturer": device.device_manufacturer,
                    "model": device.device_product_name,
                    "type": device.device_type,
                    "status": device.device_status,
                    "size_total": device.device_size_total(False),
                }
                for partition in device.device_partitions.values():
                    if partition is not None:
                        diag_data["external_usb"]["partitions"][partition.name_id] = {
                            "name": partition.partition_title,
                            "filesystem": partition.filesystem,
                            "share_name": partition.share_name,
                            "size_used": partition.partition_size_used(False),
                            "size_total": partition.partition_size_total(False),
                        }

    if syno_api.network is not None:
        for intf in syno_api.network.interfaces:
            diag_data["network"]["interfaces"][intf["id"]] = {
                "type": intf["type"],
                "ip": intf["ip"],
            }

    if syno_api.storage is not None:
        for disk in syno_api.storage.disks:
            diag_data["storage"]["disks"][disk["id"]] = {
                "name": disk["name"],
                "vendor": disk["vendor"],
                "model": disk["model"],
                "device": disk["device"],
                "temp": disk["temp"],
                "size_total": disk["size_total"],
            }

        for volume in syno_api.storage.volumes:
            diag_data["storage"]["volumes"][volume["id"]] = {
                "name": volume["fs_type"],
                "size": volume["size"],
            }

    if syno_api.surveillance_station is not None:
        for camera in syno_api.surveillance_station.get_all_cameras():
            diag_data["surveillance_station"]["cameras"][camera.id] = {
                "name": camera.name,
                "is_enabled": camera.is_enabled,
                "is_motion_detection_enabled": camera.is_motion_detection_enabled,
                "model": camera.model,
                "resolution": camera.resolution,
            }
        if camera_data := await camera_diagnostics.async_get_config_entry_diagnostics(
            hass, entry
        ):
            diag_data["surveillance_station"]["camera_diagnostics"] = camera_data

    if syno_api.upgrade is not None:
        diag_data["upgrade"] = {
            "update_available": syno_api.upgrade.update_available,
            "available_version": syno_api.upgrade.available_version,
            "reboot_needed": syno_api.upgrade.reboot_needed,
            "service_restarts": syno_api.upgrade.service_restarts,
        }

    if syno_api.utilisation is not None:
        diag_data["utilisation"] = {
            "cpu": syno_api.utilisation.cpu,
            "memory": syno_api.utilisation.memory,
            "network": syno_api.utilisation.network,
        }

    return diag_data
