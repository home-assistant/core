"""Provides diagnostics for ZHA."""
from __future__ import annotations

import dataclasses
from typing import Any

import bellows
import pkg_resources
import zigpy
from zigpy.config import CONF_NWK_EXTENDED_PAN_ID
import zigpy_deconz
import zigpy_xbee
import zigpy_zigate
import zigpy_znp

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .core.const import ATTR_IEEE, DATA_ZHA, DATA_ZHA_CONFIG, DATA_ZHA_GATEWAY
from .core.device import ZHADevice
from .core.gateway import ZHAGateway
from .core.helpers import async_get_zha_device

KEYS_TO_REDACT = {
    ATTR_IEEE,
    CONF_UNIQUE_ID,
    "network_key",
    CONF_NWK_EXTENDED_PAN_ID,
    "partner_ieee",
}


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
) -> dict:
    """Return diagnostics for a config entry."""
    config: dict = hass.data[DATA_ZHA].get(DATA_ZHA_CONFIG, {})
    gateway: ZHAGateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    return async_redact_data(
        {
            "config": config,
            "config_entry": config_entry.as_dict(),
            "application_state": shallow_asdict(gateway.application_controller.state),
            "versions": {
                "bellows": bellows.__version__,
                "zigpy": zigpy.__version__,
                "zigpy_deconz": zigpy_deconz.__version__,
                "zigpy_xbee": zigpy_xbee.__version__,
                "zigpy_znp": zigpy_znp.__version__,
                "zigpy_zigate": zigpy_zigate.__version__,
                "zhaquirks": pkg_resources.get_distribution("zha-quirks").version,
            },
        },
        KEYS_TO_REDACT,
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: dr.DeviceEntry
) -> dict:
    """Return diagnostics for a device."""
    zha_device: ZHADevice = async_get_zha_device(hass, device.id)
    return async_redact_data(zha_device.zha_device_info, KEYS_TO_REDACT)
