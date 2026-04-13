"""Diagnostics support for Sunricher DALI."""

from __future__ import annotations

from typing import Any

from PySrDaliGateway import Device, Scene

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .types import DaliCenterConfigEntry

TO_REDACT = {
    "host",
    "username",
    "password",
    "serial_number",
    "dev_sn",
}


def _serialize_device(device: Device) -> dict[str, Any]:
    """Serialize a Device using an explicit field whitelist.

    The whitelist is enforced by EXPECTED_DEVICE_KEYS in test_diagnostics.py.
    Any change here must be mirrored there.
    """
    return {
        "dev_id": device.dev_id,
        "unique_id": device.unique_id,
        "name": device.name,
        "dev_type": device.dev_type,
        "channel": device.channel,
        "address": device.address,
        "status": device.status,
        "dev_sn": device.dev_sn,
        "area_name": device.area_name,
        "area_id": device.area_id,
        "model": device.model,
    }


def _serialize_scene(scene: Scene) -> dict[str, Any]:
    """Serialize a Scene using an explicit field whitelist.

    Only the unique_id of each member device is exported, intentionally
    skipping gw_sn_obj and property fields from SceneDeviceType to avoid
    leaking gw_sn aliases or runtime light state.
    """
    return {
        "scene_id": scene.scene_id,
        "name": scene.name,
        "channel": scene.channel,
        "area_id": scene.area_id,
        "unique_id": scene.unique_id,
        "device_unique_ids": [d["unique_id"] for d in scene.devices],
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DaliCenterConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    return async_redact_data(
        {
            "entry_data": dict(entry.data),
            "devices": [_serialize_device(d) for d in data.devices],
            "scenes": [_serialize_scene(s) for s in data.scenes],
        },
        TO_REDACT,
    )
