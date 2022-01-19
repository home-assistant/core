"""Diagnostics support for Nest."""

from __future__ import annotations

from typing import Any

from google_nest_sdm.device import Device
from google_nest_sdm.device_traits import InfoTrait
from google_nest_sdm.exceptions import ApiException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_SUBSCRIBER, DOMAIN

REDACT_DEVICE_TRAITS = {InfoTrait.NAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    if DATA_SUBSCRIBER not in hass.data[DOMAIN]:
        return {"error": "No subscriber configured"}

    subscriber = hass.data[DOMAIN][DATA_SUBSCRIBER]
    try:
        device_manager = await subscriber.async_get_device_manager()
    except ApiException as err:
        return {"error": str(err)}

    return {
        "devices": [
            get_device_data(device) for device in device_manager.devices.values()
        ]
    }


def get_device_data(device: Device) -> dict[str, Any]:
    """Return diagnostic information about a device."""
    # Return a simplified view of the API object, but skipping any id fields or
    # traits that include unique identifiers or personally identifiable information.
    # See https://developers.google.com/nest/device-access/traits for API details
    return {
        "type": device.type,
        "traits": {
            trait: data
            for trait, data in device.raw_data.get("traits", {}).items()
            if trait not in REDACT_DEVICE_TRAITS
        },
    }
