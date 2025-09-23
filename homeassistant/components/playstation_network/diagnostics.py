"""Diagnostics support for PlayStation Network."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from psnawp_api.models.trophies import PlatformType

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import PlaystationNetworkConfigEntry

TO_REDACT = {
    "account_id",
    "firstName",
    "lastName",
    "middleName",
    "onlineId",
    "url",
    "username",
    "onlineId",
    "accountId",
    "members",
    "body",
    "shareable_profile_link",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PlaystationNetworkConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.user_data
    groups = entry.runtime_data.groups
    return {
        "data": async_redact_data(
            _serialize_platform_types(asdict(coordinator.data)), TO_REDACT
        ),
        "groups": async_redact_data(groups.data, TO_REDACT),
    }


def _serialize_platform_types(data: Any) -> Any:
    """Recursively convert PlatformType enums to strings in dicts and sets."""
    if isinstance(data, dict):
        return {
            (
                platform.value if isinstance(platform, PlatformType) else platform
            ): _serialize_platform_types(record)
            for platform, record in data.items()
        }
    if isinstance(data, set):
        return sorted(
            [
                record.value if isinstance(record, PlatformType) else record
                for record in data
            ]
        )
    if isinstance(data, PlatformType):
        return data.value
    return data
