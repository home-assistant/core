"""Diagnostics support for Sunricher DALI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .const import CONF_SERIAL_NUMBER
from .types import DaliCenterConfigEntry

if TYPE_CHECKING:
    from PySrDaliGateway import Device, Scene
    from PySrDaliGateway.types import SceneDeviceType

TO_REDACT = {
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SERIAL_NUMBER,
    "dev_sn",
}

ALLOWED_ENTRY_KEYS: tuple[str, ...] = (
    CONF_HOST,
    CONF_PORT,
    CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SERIAL_NUMBER,
)


def _serialize_entry_data(entry: DaliCenterConfigEntry) -> dict[str, Any]:
    """Return entry data filtered by the whitelist."""
    return {key: entry.data[key] for key in ALLOWED_ENTRY_KEYS if key in entry.data}


def _serialize_device(device: Device) -> dict[str, Any]:
    """Return a whitelisted dict view of a Device."""
    return {
        "dev_id": device.dev_id,
        "unique_id": device.unique_id,
        "name": device.name,
        "dev_type": device.dev_type,
        "channel": device.channel,
        "address": device.address,
        "status": device.status,
        "dev_sn": device.dev_sn,
        "area_name": getattr(device, "area_name", None),
        "area_id": getattr(device, "area_id", None),
        "model": device.model,
    }


def _serialize_scene(scene: Scene) -> dict[str, Any]:
    """Return a whitelisted dict view of a Scene."""
    members: list[SceneDeviceType] = scene.devices
    return {
        "scene_id": scene.scene_id,
        "name": scene.name,
        "channel": scene.channel,
        "area_id": getattr(scene, "area_id", None),
        "unique_id": scene.unique_id,
        "device_unique_ids": [member["unique_id"] for member in members],
    }


def _strip_gw_sn(data: Any, gw_sn: str) -> Any:
    """Recursively replace gw_sn in string values and list items."""
    if isinstance(data, dict):
        return {key: _strip_gw_sn(value, gw_sn) for key, value in data.items()}
    if isinstance(data, list):
        return [_strip_gw_sn(item, gw_sn) for item in data]
    if isinstance(data, str):
        return data.replace(gw_sn, REDACTED)
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DaliCenterConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    payload = {
        "entry_data": _serialize_entry_data(entry),
        "devices": [_serialize_device(device) for device in data.devices],
        "scenes": [_serialize_scene(scene) for scene in data.scenes],
    }
    return _strip_gw_sn(async_redact_data(payload, TO_REDACT), data.gateway.gw_sn)
