"""Diagnostics support for Daikin Diagnostics."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import AnyDeviceEntry

from .const import DOMAIN
from .device import DaikinOnectaDevice

if TYPE_CHECKING:
    from .coordinator import OnectaDataUpdateCoordinator

REDACT_KEYS = {"serialNumber", "macAddress", "ssid", "wifiConnectionSSID", "sgtin"}
REDACTED_SENSOR_TRANSLATION_KEYS = {"ssid", "wificonnectionssid", "sgtin"}


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
            entity_info["state"] = (
                REDACTED
                if entity_entry.translation_key in REDACTED_SENSOR_TRANSLATION_KEYS
                else state.state
            )
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


def _find_daikin_device(
    device: AnyDeviceEntry, devices: dict[str, DaikinOnectaDevice]
) -> DaikinOnectaDevice | None:
    """Return the Onecta gateway that owns a Home Assistant device."""
    identifiers = {
        identifier for domain, identifier in device.identifiers if domain == DOMAIN
    }
    for gateway_id, daikin_device in devices.items():
        if gateway_id in identifiers:
            return daikin_device
        if any(
            gateway_id + management_point.embedded_id in identifiers
            for management_point in daikin_device.device.management_points
        ):
            return daikin_device
    return None


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: AnyDeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    data: dict[str, Any] = {}
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    daikin_api = coordinator.api
    daikin_device = _find_daikin_device(device, coordinator.data or {})
    if daikin_device is not None:
        data["device_json_data"] = async_redact_data(
            daikin_device.device.to_dict(), REDACT_KEYS
        )
    data["rate_limits"] = daikin_api.rate_limits
    data["options"] = config_entry.options
    data["oauth2_token_valid"] = daikin_api.session.valid_token
    data["entities"] = get_entities(hass, config_entry)
    return data
