"""Diagnostics support for UptimeRobot."""

from __future__ import annotations

from typing import Any

from pyuptimerobot import UptimeRobotException

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import UptimeRobotConfigEntry

TO_REDACT = {"email"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: UptimeRobotConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    account: dict[str, Any] | str | None = None
    try:
        response = await coordinator.api.async_get_account_details()
    except UptimeRobotException as err:
        account = str(err)
    else:
        if (details := response.data) is not None:
            account = {
                "monitorsCount": details.monitorsCount,
                "email": details.email,
            }

    return {
        "account": async_redact_data(account, TO_REDACT),
        "monitors": [
            {
                "id": monitor.id,
                "type": monitor.type,
                "interval": monitor.interval,
                "status": monitor.status,
            }
            for monitor in coordinator.data
        ],
    }
