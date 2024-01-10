"""Diagnostics support for Enphase Envoy."""
from __future__ import annotations

from typing import Any

from pyenphase.const import SupportedFeatures

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import EnphaseUpdateCoordinator

CONF_TITLE = "title"

TO_REDACT = {
    CONF_NAME,
    CONF_PASSWORD,
    # Config entry title and unique ID may contain sensitive data:
    CONF_TITLE,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
    CONF_TOKEN,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: EnphaseUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "envoy_firmware": coordinator.envoy.firmware,
            "supported_features": [
                feature.name
                for feature in SupportedFeatures
                if feature in coordinator.envoy.supported_features
            ],
            "phase_mode": coordinator.envoy.phase_mode,
            "phase_count": coordinator.envoy.phase_count,
            "active_phasecount": coordinator.envoy.active_phase_count,
            "ct_count": coordinator.envoy.ct_meter_count,
            "ct_consumption_meter": coordinator.envoy.consumption_meter_type,
            "data": coordinator.data,
        },
        TO_REDACT,
    )
