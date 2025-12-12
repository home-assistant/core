"""Diagnostics support for Tibber."""

from __future__ import annotations

from typing import Any

import aiohttp
import tibber

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import TibberConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: TibberConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    runtime = config_entry.runtime_data
    result: dict[str, Any] = {
        "homes": [
            {
                "last_data_timestamp": home.last_data_timestamp,
                "has_active_subscription": home.has_active_subscription,
                "has_real_time_consumption": home.has_real_time_consumption,
                "last_cons_data_timestamp": home.last_cons_data_timestamp,
                "country": home.country,
            }
            for home in runtime.tibber_connection.get_homes(only_active=False)
        ]
    }

    devices: dict[str, Any] = {}
    error: str | None = None
    try:
        coordinator = runtime.data_api_coordinator
        if coordinator is not None:
            devices = coordinator.data
    except ConfigEntryAuthFailed:
        error = "Authentication failed"
    except TimeoutError:
        error = "Timeout error"
    except aiohttp.ClientError:
        error = "Client error"
    except tibber.InvalidLoginError:
        error = "Invalid login"
    except tibber.RetryableHttpExceptionError as err:
        error = f"Retryable HTTP error ({err.status})"
    except tibber.FatalHttpExceptionError as err:
        error = f"Fatal HTTP error ({err.status})"

    result["error"] = error
    result["devices"] = [
        {
            "id": device.id,
            "name": device.name,
            "brand": device.brand,
            "model": device.model,
        }
        for device in devices.values()
    ]

    return result
