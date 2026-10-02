"""Diagnostics support for Daikin Diagnostics."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import AnyDeviceEntry

if TYPE_CHECKING:
    from .coordinator import OnectaDataUpdateCoordinator

REDACT_KEYS = {"serialNumber", "macAddress"}


def get_entities(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, dict[str, Any]]:
    """Return entity diagnostics for a config entry."""
    entity_registry = er.async_get(hass)
    entities_data: dict[str, dict[str, Any]] = {}

    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        entity_id = entity_entry.entity_id
        state = hass.states.get(entity_id)

        entity_info: dict[str, Any] = {
            "entity_id": entity_id,
            "unique_id": entity_entry.unique_id,
            "platform": entity_entry.platform,
            "original_name": entity_entry.original_name,
            "disabled": entity_entry.disabled,
            "translation_key": entity_entry.translation_key,
        }

        if state:
            entity_info["state"] = state.state
            entity_info["attributes"] = async_redact_data(
                dict(state.attributes), REDACT_KEYS
            )

        entities_data[entity_id] = entity_info

    return entities_data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    daikin_api = coordinator.api
    return {
        "json_data": async_redact_data(
            [device.device.to_dict() for device in (coordinator.data or {}).values()],
            REDACT_KEYS,
        ),
        "rate_limits": daikin_api.rate_limits,
        "options": config_entry.options,
        "oauth2_token_valid": daikin_api.session.valid_token,
        "entities": get_entities(hass, config_entry),
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: AnyDeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    data: dict[str, Any] = {}
    dev_id = next(iter(device.identifiers))[1]
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    daikin_api = coordinator.api
    daikin_device = (coordinator.data or {}).get(dev_id)
    if daikin_device is not None:
        data["device_json_data"] = async_redact_data(
            daikin_device.device.to_dict(), REDACT_KEYS
        )
    data["rate_limits"] = daikin_api.rate_limits
    data["options"] = config_entry.options
    data["oauth2_token_valid"] = daikin_api.session.valid_token
    data["entities"] = get_entities(hass, config_entry)
    return data
