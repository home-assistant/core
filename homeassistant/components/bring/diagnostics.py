"""Diagnostics support for Bring."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from bring_api.types import BringList, BringUserSettingsResponse

from homeassistant.core import HomeAssistant

from . import BringConfigEntry
from .coordinator import BringData


@dataclass
class BringDiagnostics:
    """Diagnostics data."""

    user_settings: BringUserSettingsResponse
    lists: list[BringList]
    list_items: list[BringData]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: BringConfigEntry
) -> Mapping[str, Any]:
    """Return diagnostics for a config entry."""

    return asdict(
        BringDiagnostics(
            user_settings=config_entry.runtime_data.user_settings,
            lists=config_entry.runtime_data.lists,
            list_items=config_entry.runtime_data.data,
        )
    )
