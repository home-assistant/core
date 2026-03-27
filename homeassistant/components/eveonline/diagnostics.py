"""Diagnostics support for the Eve Online integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .coordinator import EveOnlineConfigEntry

TO_REDACT_CONFIG = {
    "access_token",
    "auth_implementation",
    "refresh_token",
    "token",
}

TO_REDACT_DATA = {
    "character_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EveOnlineConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT_CONFIG),
        "coordinator_data": {
            "server_status": asdict(data.server_status),
            "character_id": "**REDACTED**",
            "character_name": data.character_name,
            "character_online": (
                asdict(data.character_online) if data.character_online else None
            ),
            "wallet_balance": (
                asdict(data.wallet_balance) if data.wallet_balance else None
            ),
            "skill_queue_length": len(data.skill_queue),
            "location": asdict(data.location) if data.location else None,
            "ship": asdict(data.ship) if data.ship else None,
            "skills": asdict(data.skills) if data.skills else None,
            "mail_labels": asdict(data.mail_labels) if data.mail_labels else None,
            "industry_jobs_count": len(data.industry_jobs),
            "market_orders_count": len(data.market_orders),
            "jump_fatigue": (asdict(data.jump_fatigue) if data.jump_fatigue else None),
        },
    }
