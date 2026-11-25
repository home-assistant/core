"""Diagnostics support for SmartyPlants."""

from dataclasses import asdict
from typing import Any

from pysmartyplants import Sensor

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from .const import CONF_WEBHOOK_SECRET
from .coordinator import SmartyPlantsConfigEntry

# Ids and the hardware identifier address rows in the SmartyPlants account, and
# the image URL carries them in its path.
TO_REDACT = {
    CONF_API_KEY,
    CONF_WEBHOOK_ID,
    CONF_WEBHOOK_SECRET,
    "id",
    "identifier",
    "image_url",
}


def _sensor_diagnostics(sensor: Sensor) -> dict[str, Any]:
    """Describe one sensor without naming the account it belongs to."""
    data = asdict(sensor)
    # Sensors are provisioned as "SmartyPlant Sensor-<identifier>", so the
    # default name gives away the identifier redacted below.
    data.pop("name", None)
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SmartyPlantsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diagnostics: dict[str, Any] = {
        "entry_data": dict(entry.data),
        # Registration needs both, so the secret alone would overstate it.
        "webhook_configured": bool(
            entry.data.get(CONF_WEBHOOK_ID) and entry.data.get(CONF_WEBHOOK_SECRET)
        ),
    }

    # An entry that is not set up, one waiting to retry included, has no
    # coordinator: the download then reports the entry alone instead of failing.
    if entry.state is ConfigEntryState.LOADED:
        coordinator = entry.runtime_data
        diagnostics["last_update_success"] = coordinator.last_update_success
        diagnostics["sensors"] = [
            _sensor_diagnostics(sensor) for sensor in (coordinator.data or {}).values()
        ]

    return async_redact_data(diagnostics, TO_REDACT)
