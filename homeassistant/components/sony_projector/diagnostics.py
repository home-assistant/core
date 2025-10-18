"""Diagnostics support for Sony Projector."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pysdcp_extended

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import SonyProjectorConfigEntry
from .const import CONF_MODEL, CONF_SERIAL

TO_REDACT = {CONF_HOST, CONF_SERIAL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SonyProjectorConfigEntry
) -> Mapping[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = entry.runtime_data.coordinator
    data = coordinator.data

    diag: dict[str, object] = {
        "host": entry.data.get(CONF_HOST),
        "model": data.model if data else entry.data.get(CONF_MODEL),
        "serial": data.serial if data else entry.data.get(CONF_SERIAL),
        "features": {
            "aspect_ratio": bool(data and data.aspect_ratio_options),
            "picture_mode": bool(data and data.picture_mode_options),
            "picture_mute": data.picture_mute is not None if data else False,
        },
        "lamp_hours": data.lamp_hours if data else None,
        "library_version": getattr(pysdcp_extended, "__version__", "unknown"),
        "last_error": coordinator.last_error,
    }

    return async_redact_data(diag, TO_REDACT)
