"""Diagnostics support for SmartyPlants."""

from dataclasses import asdict
from typing import Any

from pysmartyplants import Sensor

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from .const import CONF_WEBHOOK_SECRET
from .coordinator import SmartyPlantsConfigEntry

# The key and secret authenticate the account and the webhook id is the public
# part of a callback URL, so none of them belong in a shared file. Ids and the
# hardware identifier point at rows in the SmartyPlants account, and the image
# URL carries them in its path.
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
    coordinator = entry.runtime_data

    return async_redact_data(
        {
            "entry_data": dict(entry.data),
            "webhook_configured": CONF_WEBHOOK_SECRET in entry.data,
            "last_update_success": coordinator.last_update_success,
            "sensors": [
                _sensor_diagnostics(sensor)
                for sensor in (coordinator.data or {}).values()
            ],
        },
        TO_REDACT,
    )
