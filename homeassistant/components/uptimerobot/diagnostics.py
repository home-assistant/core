"""Diagnostics support for UptimeRobot."""

from __future__ import annotations

from typing import Any

from pyuptimerobot import UptimeRobotException

from homeassistant.core import HomeAssistant

from .coordinator import UptimeRobotConfigEntry


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
                "up_monitors": details.up_monitors,
                "down_monitors": details.down_monitors,
                "paused_monitors": details.paused_monitors,
            }

    return {
        "account": account,
        "monitors": [
            {
                "id": monitor.id,
                "type": str(monitor.type),
                "interval": monitor.interval,
                "status": monitor.status,
            }
            for monitor in coordinator.data
        ],
    }
