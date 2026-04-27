"""Diagnostics support for Opower."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_LOGIN_DATA, CONF_TOTP_SECRET
from .coordinator import OpowerConfigEntry

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_LOGIN_DATA,
    CONF_TOTP_SECRET,
    # Title contains the username/email
    "title",
    "utility_account_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OpowerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "data": [
                {
                    "account": {
                        "utility_account_id": account.utility_account_id,
                        "meter_type": account.meter_type.name,
                        "read_resolution": (
                            account.read_resolution.name
                            if account.read_resolution
                            else None
                        ),
                    },
                    "forecast": (
                        {
                            "usage_to_date": forecast.usage_to_date,
                            "cost_to_date": forecast.cost_to_date,
                            "forecasted_usage": forecast.forecasted_usage,
                            "forecasted_cost": forecast.forecasted_cost,
                            "typical_usage": forecast.typical_usage,
                            "typical_cost": forecast.typical_cost,
                            "unit_of_measure": forecast.unit_of_measure.name,
                            "start_date": forecast.start_date.isoformat(),
                            "end_date": forecast.end_date.isoformat(),
                            "current_date": forecast.current_date.isoformat(),
                        }
                        if (forecast := data.forecast)
                        else None
                    ),
                    "last_changed": (
                        data.last_changed.isoformat() if data.last_changed else None
                    ),
                    "last_updated": (
                        data.last_updated.isoformat() if data.last_updated else None
                    ),
                }
                for data in coordinator.data.values()
                for account in (data.account,)
            ],
        },
        TO_REDACT,
    )
