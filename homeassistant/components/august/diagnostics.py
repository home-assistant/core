"""Diagnostics support for august."""

from __future__ import annotations

from typing import Any

from yalexs.const import DEFAULT_BRAND

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import AugustConfigEntry
from .const import CONF_BRAND

TO_REDACT = {
    "HouseID",
    "OfflineKeys",
    "installUserID",
    "invitations",
    "key",
    "pins",
    "pubsubChannel",
    "recentImage",
    "remoteOperateSecret",
    "users",
    "zWaveDSK",
    "contentToken",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AugustConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data

    return {
        "locks": {
            lock.device_id: async_redact_data(
                data.get_device_detail(lock.device_id).raw, TO_REDACT
            )
            for lock in data.locks
        },
        "doorbells": {
            doorbell.device_id: async_redact_data(
                data.get_device_detail(doorbell.device_id).raw, TO_REDACT
            )
            for doorbell in data.doorbells
        },
        "brand": entry.data.get(CONF_BRAND, DEFAULT_BRAND),
    }
