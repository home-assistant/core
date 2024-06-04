"""Diagnostics support for Synology DSM."""

from __future__ import annotations

from typing import Any

from homeassistant.components.camera import diagnostics as camera_diagnostics
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_TOKEN, DOMAIN
from .models import SynologyDSMData

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, CONF_DEVICE_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: SynologyDSMData = hass.data[DOMAIN][entry.unique_id]
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
