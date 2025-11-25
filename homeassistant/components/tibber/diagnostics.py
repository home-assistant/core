"""Diagnostics support for Tibber."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import aiohttp
import tibber

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import TibberRuntimeData


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    runtime = cast("TibberRuntimeData | None", hass.data.get(DOMAIN))
    if runtime is None:
        return {"homes": []}
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

    if runtime.session:
        error: str | None = None
        try:
            devices = await (await runtime.async_get_client(hass)).get_all_devices()
        except ConfigEntryAuthFailed:
            devices = {}
            error = "Authentication failed"
        except TimeoutError:
            devices = {}
            error = "Timeout error"
        except aiohttp.ClientError:
            devices = {}
            error = "Client error"
        except tibber.InvalidLoginError:
            devices = {}
            error = "Invalid login"
        except tibber.RetryableHttpExceptionError as err:
            devices = {}
            error = f"Retryable HTTP error ({err.status})"
        except tibber.FatalHttpExceptionError as err:
            devices = {}
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
