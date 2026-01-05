"""Define the HEOS integration diagnostics module."""

from collections.abc import Mapping, Sequence
import dataclasses
from typing import Any

from pyheos import HeosError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import ATTR_PASSWORD, ATTR_USERNAME, DOMAIN
from .coordinator import HeosConfigEntry

TO_REDACT = [
    ATTR_PASSWORD,
    ATTR_USERNAME,
    "signed_in_username",
    "serial",
    "serial_number",
]


def _as_dict(
    data: Any, redact: bool = False
) -> Mapping[str, Any] | Sequence[Any] | Any:
    """Convert dataclasses to dicts within various data structures."""
    if dataclasses.is_dataclass(data):
        data_dict = dataclasses.asdict(data)  # type: ignore[arg-type]
        return data_dict if not redact else async_redact_data(data_dict, TO_REDACT)
    if not isinstance(data, (Mapping, Sequence)):
        return data
    if isinstance(data, Sequence):
        return [_as_dict(val) for val in data]
    return {k: _as_dict(v) for k, v in data.items()}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: HeosConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data
    diagnostics = {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "heos": {
            "connection_state": coordinator.heos.connection_state,
            "current_credentials": _as_dict(
                coordinator.heos.current_credentials, redact=True
            ),
        },
        "groups": _as_dict(coordinator.heos.groups),
        "source_list": coordinator.async_get_source_list(),
        "inputs": _as_dict(coordinator.inputs),
        "favorites": _as_dict(coordinator.favorites),
    }
    # Try getting system information
    try:
        system_info = await coordinator.heos.get_system_info()
    except HeosError as err:
        diagnostics["system"] = {"error": str(err)}
    else:
        diagnostics["system"] = _as_dict(system_info, redact=True)
    return diagnostics


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: HeosConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    entity_registry = er.async_get(hass)
    entities = entity_registry.entities.get_entries_for_device_id(device.id, True)
    player_id = next(
        int(value) for domain, value in device.identifiers if domain == DOMAIN
    )
    player = config_entry.runtime_data.heos.players.get(player_id)
    return {
        "device": async_redact_data(device.dict_repr, TO_REDACT),
        "entities": [
            {
                "entity": entity.as_partial_dict,
                "state": state.as_dict()
                if (state := hass.states.get(entity.entity_id))
                else None,
            }
            for entity in entities
        ],
        "player": _as_dict(player, redact=True),
    }
