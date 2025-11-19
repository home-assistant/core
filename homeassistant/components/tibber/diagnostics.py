"""Diagnostics support for Tibber."""

from __future__ import annotations

from typing import Any

import aiohttp
import tibber

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import API_TYPE_DATA_API, API_TYPE_GRAPHQL, CONF_API_TYPE, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    api_type = config_entry.data.get(CONF_API_TYPE, API_TYPE_GRAPHQL)
    domain_data = hass.data.get(DOMAIN, {})

    if api_type == API_TYPE_GRAPHQL:
        tibber_connection: tibber.Tibber = domain_data[API_TYPE_GRAPHQL].tibber
        return {
            "api_type": API_TYPE_GRAPHQL,
            "homes": [
                {
                    "last_data_timestamp": home.last_data_timestamp,
                    "has_active_subscription": home.has_active_subscription,
                    "has_real_time_consumption": home.has_real_time_consumption,
                    "last_cons_data_timestamp": home.last_cons_data_timestamp,
                    "country": home.country,
                }
                for home in tibber_connection.get_homes(only_active=False)
            ],
        }

    runtime = domain_data.get(API_TYPE_DATA_API)
    if runtime is None:
        return {
            "api_type": API_TYPE_DATA_API,
            "devices": [],
        }

    devices: dict[str, Any] = {}
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

    return {
        "api_type": API_TYPE_DATA_API,
        "error": error,
        "devices": [
            {
                "id": device.id,
                "name": device.name,
                "brand": device.brand,
                "model": device.model,
            }
            for device in devices.values()
        ],
    }
