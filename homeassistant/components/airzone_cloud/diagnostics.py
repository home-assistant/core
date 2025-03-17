"""Support for the Airzone Cloud diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aioairzone_cloud.const import (
    API_CITY,
    API_GROUP_ID,
    API_GROUPS,
    API_LOCATION_ID,
    API_OLD_ID,
    API_PIN,
    API_STAT_AP_MAC,
    API_STAT_SSID,
    API_USER_ID,
    AZD_WIFI_MAC,
    RAW_DEVICES_STATUS,
    RAW_INSTALLATIONS,
    RAW_WEBSERVERS,
)

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import AirzoneCloudConfigEntry

TO_REDACT_API = [
    API_CITY,
    API_LOCATION_ID,
    API_OLD_ID,
    API_PIN,
    API_STAT_AP_MAC,
    API_STAT_SSID,
    API_USER_ID,
]

TO_REDACT_CONFIG = [
    CONF_PASSWORD,
    CONF_USERNAME,
]

TO_REDACT_COORD = [
    AZD_WIFI_MAC,
]


def gather_ids(api_data: dict[str, Any]) -> dict[str, Any]:
    """Return dict with IDs."""
    ids: dict[str, Any] = {}

    dev_idx = 1
    for dev_id in api_data[RAW_DEVICES_STATUS]:
        if dev_id not in ids:
            ids[dev_id] = f"device{dev_idx}"
            dev_idx += 1

    group_idx = 1
    inst_idx = 1
    for inst_id, inst_data in api_data[RAW_INSTALLATIONS].items():
        if inst_id not in ids:
            ids[inst_id] = f"installation{inst_idx}"
            inst_idx += 1
        for group in inst_data[API_GROUPS]:
            group_id = group[API_GROUP_ID]
            if group_id not in ids:
                ids[group_id] = f"group{group_idx}"
                group_idx += 1

    ws_idx = 1
    for ws_id in api_data[RAW_WEBSERVERS]:
        if ws_id not in ids:
            ids[ws_id] = f"webserver{ws_idx}"
            ws_idx += 1

    return ids


def redact_keys(data: Any, ids: dict[str, Any]) -> Any:
    """Redact sensitive keys in a dict."""
    if not isinstance(data, (Mapping, list)):
        return data

    if isinstance(data, list):
        return [redact_keys(val, ids) for val in data]

    redacted = {**data}

    keys = list(redacted)
    for key in keys:
        if key in ids:
            redacted[ids[key]] = redacted.pop(key)
        elif isinstance(redacted[key], Mapping):
            redacted[key] = redact_keys(redacted[key], ids)
        elif isinstance(redacted[key], list):
            redacted[key] = [redact_keys(item, ids) for item in redacted[key]]

    return redacted


def redact_values(data: Any, ids: dict[str, Any]) -> Any:
    """Redact sensitive values in a dict."""
    if not isinstance(data, (Mapping, list)):
        if data in ids:
            return ids[data]
        return data

    if isinstance(data, list):
        return [redact_values(val, ids) for val in data]

    redacted = {**data}

    for key, value in redacted.items():
        if value is None:
            continue
        if isinstance(value, Mapping):
            redacted[key] = redact_values(value, ids)
        elif isinstance(value, list):
            redacted[key] = [redact_values(item, ids) for item in value]
        elif value in ids:
            redacted[key] = ids[value]

    return redacted


def redact_all(
    data: dict[str, Any], ids: dict[str, Any], to_redact: list[str]
) -> dict[str, Any]:
    """Redact sensitive data."""
    _data = redact_keys(data, ids)
    _data = redact_values(_data, ids)
    return async_redact_data(_data, to_redact)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: AirzoneCloudConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data
    raw_data = coordinator.airzone.raw_data()
    ids = gather_ids(raw_data)

    return {
        "api_data": redact_all(raw_data, ids, TO_REDACT_API),
        "config_entry": redact_all(config_entry.as_dict(), ids, TO_REDACT_CONFIG),
        "coord_data": redact_all(coordinator.data, ids, TO_REDACT_COORD),
    }
