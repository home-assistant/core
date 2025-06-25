"""Provides diagnostics for Fully Kiosk Browser."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import FullyKioskConfigEntry

DEVICE_INFO_TO_REDACT = {
    "serial",
    "Mac",
    "ip6",
    "hostname6",
    "ip4",
    "hostname4",
    "deviceID",
    "startUrl",
    "currentPage",
    "SSID",
    "BSSID",
}
SETTINGS_TO_REDACT = {
    "startURL",
    "mqttBrokerPassword",
    "mqttBrokerUsername",
    "remoteAdminPassword",
    "wifiKey",
    "authPassword",
    "authUsername",
    "mqttBrokerUrl",
    "kioskPin",
    "wifiSSID",
    "screensaverWallpaperURL",
    "barcodeScanTargetUrl",
    "launcherBgUrl",
    "clientCaUrl",
    "urlWhitelist",
    "alarmSoundFileUrl",
    "errorURL",
    "actionBarIconUrl",
    "kioskWifiPin",
    "knoxApnConfig",
    "injectJsCode",
    "mdmApnConfig",
    "mdmProxyConfig",
    "wifiEnterpriseIdentity",
    "sebExamKey",
    "sebConfigKey",
    "kioskPinEnc",
    "remoteAdminPasswordEnc",
}


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: FullyKioskConfigEntry, device: dr.DeviceEntry
) -> dict[str, Any]:
    """Return device diagnostics."""
    coordinator = entry.runtime_data
    data = coordinator.data
    data["settings"] = async_redact_data(data["settings"], SETTINGS_TO_REDACT)
    return async_redact_data(data, DEVICE_INFO_TO_REDACT)
