"""Diagnostics support for the OpenThread Border Router integration."""

from typing import Any

from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    is_multiprotocol_url,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .types import OTBRConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OTBRConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    otbrdata = entry.runtime_data
    active_dataset_info: dict[str, Any] | None = None
    # Network name, PAN IDs, mesh local prefix and keys are omitted on purpose
    if active_dataset := await otbrdata.get_active_dataset():
        active_dataset_info = {
            "active_timestamp": (
                active_dataset.active_timestamp.as_json()
                if active_dataset.active_timestamp
                else None
            ),
            "channel": active_dataset.channel,
            "channel_mask": active_dataset.channel_mask,
            "security_policy": (
                active_dataset.security_policy.as_json()
                if active_dataset.security_policy
                else None
            ),
        }
    coprocessor_version: str | None
    try:
        coprocessor_version = await otbrdata.get_coprocessor_version()
    except HomeAssistantError:
        coprocessor_version = None
    return {
        "multiprotocol": is_multiprotocol_url(otbrdata.url),
        "api_version": await otbrdata.api.get_api_version(),
        "coprocessor_version": coprocessor_version,
        "active_dataset": active_dataset_info,
        "pending_dataset": await otbrdata.get_pending_dataset_tlvs() is not None,
    }
