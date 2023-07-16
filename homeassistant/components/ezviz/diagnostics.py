"""Diagnostics support for EZVIZ."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import EzvizDataUpdateCoordinator

TO_REDACT_COORDINATOR = {
    "serial",
    "last_alarm_pic",
    "wan_ip",
    "encrypted_pwd_hash",
    "last_alarm_time",
    "ssid",
    "mac_address",
    "CLOUD",
    "VTM",
    "P2P",
    "KMS",
    "VIDEO_QUALITY",
}

TO_REDACT_PYEZVIZ_DATA = {
    "deviceSerial",
    "netIp",
    "wanIp",
    "encryptPwd",
    "ssid",
    "mac",
    "userName",
    "fullSerial",
    "superDeviceSerial",
    "resourceId",
    "CLOUD",
    "VTM",
    "P2P",
    "KMS",
    "TIME_PLAN",
    "CHANNEL",
    "QOS",
    "VIDEO_QUALITY",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    ezviz_api_page_list = await hass.async_add_executor_job(
        coordinator.ezviz_client.get_device_infos
    )

    return {
        "ezviz_coordinator_data": [
            async_redact_data(coordinator.data, TO_REDACT_COORDINATOR)
        ],
        "ezviz_api_page_list": [
            async_redact_data(ezviz_api_page_list, TO_REDACT_PYEZVIZ_DATA)
        ],
    }
