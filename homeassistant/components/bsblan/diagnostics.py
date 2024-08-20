"""Diagnostics support for BSBLan."""

from __future__ import annotations

import inspect
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import json_dumps
from homeassistant.util.json import json_loads

from .const import DOMAIN
from .models import BSBLanData


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: BSBLanData = hass.data[DOMAIN][entry.entry_id]

    async def safe_serialize(obj):
        if inspect.iscoroutine(obj):
            obj = await obj
        if callable(getattr(obj, "to_dict", None)):
            result = obj.to_dict()
            if inspect.iscoroutine(result):
                result = await result
            obj = result
        return json_loads(json_dumps(obj))

    return {
        "info": await safe_serialize(data.info),
        "device": await safe_serialize(data.device),
        "coordinator_data": {
            "state": await safe_serialize(data.coordinator.data.state)
            if data.coordinator.data.state
            else {},
        },
        "static": await safe_serialize(data.static),
    }
