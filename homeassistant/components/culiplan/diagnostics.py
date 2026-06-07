"""Diagnostics support for the Culiplan integration.

Returns integration health data for troubleshooting while redacting
sensitive values (OAuth tokens, refresh tokens, account identifiers).
"""

from datetime import UTC, datetime
import time
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import CuliplanConfigEntry

_REDACT = {"access_token", "refresh_token", "token", "id", "email"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: CuliplanConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for ``entry`` — tokens and IDs are redacted."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator

    token: dict[str, Any] = entry.data.get("token", {}) or {}
    issued_at = token.get("issued_at")
    token_age_seconds = (
        int(time.time() - issued_at) if isinstance(issued_at, (int, float)) else None
    )

    return {
        "entry": async_redact_data(
            {"data": dict(entry.data), "options": dict(entry.options)}, _REDACT
        ),
        "token_age_seconds": token_age_seconds,
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": (
                repr(coordinator.last_exception)
                if coordinator.last_exception is not None
                else None
            ),
            "push_connected": coordinator.push_connected,
        },
        "captured_at": datetime.now(UTC).isoformat(),
    }
