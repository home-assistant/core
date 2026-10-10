"""Diagnostics support for Nobø Ecohub."""

from typing import Any

from pynobo import ComponentInfo, nobo

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_IP_ADDRESS, CONF_MAC
from homeassistant.core import HomeAssistant

from . import NoboHubConfigEntry
from .const import ATTR_SERIAL, CONF_SERIAL

TO_REDACT_ENTRY = {CONF_IP_ADDRESS, CONF_MAC, CONF_SERIAL}
TO_REDACT_HUB = {ATTR_SERIAL}

_MODEL_FIELDS = (
    "model_id",
    "name",
    "type",
    "has_temp_sensor",
    "requires_control_panel",
    "supports_comfort",
    "supports_eco",
)


def _component_to_dict(component: ComponentInfo) -> dict[str, Any]:
    model = component["model"]
    formatted: dict[str, Any] = dict(component)
    formatted["model"] = {field: getattr(model, field, None) for field in _MODEL_FIELDS}
    if model.type == nobo.Model.UNKNOWN:
        # Unknown models carry the serial number in the name.
        formatted["model"]["name"] = REDACTED
    return formatted


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NoboHubConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub = entry.runtime_data
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT_ENTRY),
        "hub_info": async_redact_data(hub.hub_info, TO_REDACT_HUB),
        "zones": hub.zones,
        "components": async_redact_data(
            [_component_to_dict(c) for c in hub.components.values()],
            TO_REDACT_HUB,
        ),
        "week_profiles": hub.week_profiles,
        "overrides": hub.overrides,
    }
