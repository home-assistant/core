"""Diagnostics support for ViCare."""

import json
from typing import Any

from PyViCare.PyViCareServiceViaGateway import filter_features_for_device
from PyViCare.PyViCareUtils import PyViCareDeviceCommunicationError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .types import ViCareConfigEntry

TO_REDACT = {
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ViCareConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    def dump_devices() -> list[dict[str, Any]]:
        """Dump devices, tolerating per-device communication failures."""
        devices: list[dict[str, Any]] = []
        for device in entry.runtime_data.client.all_devices:
            try:
                dump = json.loads(device.dump_secure())
                # In viaGateway mode dump_secure() returns the whole gateway's
                # features, so scope them to the device the entry describes.
                dump["data"] = filter_features_for_device(
                    dump["data"], device.device_id
                )
                devices.append(dump)
            except PyViCareDeviceCommunicationError as err:
                # One offline gateway must not abort the whole diagnostics dump.
                devices.append(
                    {
                        "device": {
                            "id": device.device_id,
                            "modelId": device.device_model,
                            "type": device.device_type,
                            "status": device.status,
                            "roles": device.roles,
                        },
                        "error": f"{type(err).__name__}: {err}",
                    }
                )
        return devices

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": await hass.async_add_executor_job(dump_devices),
    }
