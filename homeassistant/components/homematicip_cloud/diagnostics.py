"""Diagnostics support for HomematicIP Cloud."""

from __future__ import annotations

import json
from typing import Any

from homematicip.base.helpers import handle_config

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .hap import HomematicIPConfigEntry

TO_REDACT_CONFIG = {"city", "latitude", "longitude", "refreshToken"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: HomematicIPConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hap = config_entry.runtime_data
    json_state = await hap.home.download_configuration_async()
    anonymized = handle_config(json_state, anonymize=True)
    config = json.loads(anonymized)

    return async_redact_data(config, TO_REDACT_CONFIG)
