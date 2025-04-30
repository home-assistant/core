"""Provides diagnostics for ZHA."""

from __future__ import annotations

import dataclasses
from importlib.metadata import version
from typing import Any

from zha.application.const import ATTR_IEEE
from zha.application.gateway import Gateway
from zigpy.config import CONF_NWK_EXTENDED_PAN_ID
from zigpy.types import Channels

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_ALARM_MASTER_CODE
from .helpers import (
    ZHADeviceProxy,
    async_get_zha_device_proxy,
    get_zha_data,
    get_zha_gateway,
)

KEYS_TO_REDACT = {
    ATTR_IEEE,
    CONF_UNIQUE_ID,
    CONF_ALARM_MASTER_CODE,
    "network_key",
    CONF_NWK_EXTENDED_PAN_ID,
    "partner_ieee",
}

ATTRIBUTES = "attributes"
CLUSTER_DETAILS = "cluster_details"
UNSUPPORTED_ATTRIBUTES = "unsupported_attributes"

BELLOWS_VERSION = version("bellows")
ZIGPY_VERSION = version("zigpy")
ZIGPY_DECONZ_VERSION = version("zigpy-deconz")
ZIGPY_XBEE_VERSION = version("zigpy-xbee")
ZIGPY_ZNP_VERSION = version("zigpy-znp")
ZIGPY_ZIGATE_VERSION = version("zigpy-zigate")
ZHA_QUIRKS_VERSION = version("zha-quirks")
ZHA_VERSION = version("zha")


def shallow_asdict(obj: Any) -> dict:
    """Return a shallow copy of a dataclass as a dict."""
    if hasattr(obj, "__dataclass_fields__"):
        result = {}

        for field in dataclasses.fields(obj):
            result[field.name] = shallow_asdict(getattr(obj, field.name))

        return result
    if hasattr(obj, "as_dict"):
        return obj.as_dict()
    return obj


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    zha_data = get_zha_data(hass)
    gateway: Gateway = get_zha_gateway(hass)
    app = gateway.application_controller

    energy_scan = await app.energy_scan(
        channels=Channels.ALL_CHANNELS, duration_exp=4, count=1
    )

    return async_redact_data(
        {
            "config": zha_data.yaml_config,
            "config_entry": config_entry.as_dict(),
            "application_state": shallow_asdict(app.state),
            "energy_scan": {
                channel: 100 * energy / 255 for channel, energy in energy_scan.items()
            },
            "versions": {
                "bellows": BELLOWS_VERSION,
                "zigpy": ZIGPY_VERSION,
                "zigpy_deconz": ZIGPY_DECONZ_VERSION,
                "zigpy_xbee": ZIGPY_XBEE_VERSION,
                "zigpy_znp": ZIGPY_ZNP_VERSION,
                "zigpy_zigate": ZIGPY_ZIGATE_VERSION,
                "zhaquirks": ZHA_QUIRKS_VERSION,
                "zha": ZHA_VERSION,
            },
            "devices": [
                {
                    "manufacturer": device.manufacturer,
                    "model": device.model,
                    "logical_type": device.device_type,
                }
                for device in gateway.devices.values()
            ],
        },
        KEYS_TO_REDACT,
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: dr.DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    zha_device_proxy: ZHADeviceProxy = async_get_zha_device_proxy(hass, device.id)
    diagnostics_json: dict[str, Any] = zha_device_proxy.device.get_diagnostics_json()
    return async_redact_data(diagnostics_json, KEYS_TO_REDACT)
