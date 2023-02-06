"""API controller configuration for go-e Charger Cloud integration."""

import aiohttp
from goechargerv2.goecharger import GoeChargerApi

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import HomeAssistantType

from .const import API, CHARGERS_API, DOMAIN, INIT_STATE


async def fetch_status(hass: HomeAssistantType, charger_name: str) -> dict:
    """Fetch go-e Charger Cloud car status via API."""

    api: GoeChargerApi = hass.data[DOMAIN][INIT_STATE][CHARGERS_API][charger_name][API]
    fetched_status: dict = await hass.async_add_executor_job(api.request_status)

    return fetched_status


async def ping_charger(hass: HomeAssistantType, charger_name: str) -> None:
    """Make a call to the charger device. If it fails raise an error."""

    try:
        api: GoeChargerApi = hass.data[DOMAIN][INIT_STATE][CHARGERS_API][charger_name][
            API
        ]
        await hass.async_add_executor_job(api.request_status)
    except (aiohttp.ClientError, RuntimeError) as ex:
        raise ConfigEntryNotReady(ex) from ex
