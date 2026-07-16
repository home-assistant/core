"""The usage prediction integration."""

import asyncio
from datetime import timedelta
from typing import Any

from aiohttp import web

from homeassistant.components import websocket_api
from homeassistant.components.http import KEY_HASS, KEY_HASS_USER, HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from . import common_control
from .const import DATA_CACHE, DOMAIN
from .models import EntityUsageDataCache, EntityUsagePredictions

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

CACHE_DURATION = timedelta(hours=24)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the usage prediction integration."""
    hass.http.register_view(CommonControlView)
    websocket_api.async_register_command(hass, ws_common_control)
    hass.data[DATA_CACHE] = {}
    return True


@websocket_api.websocket_command({"type": f"{DOMAIN}/common_control"})
@websocket_api.async_response
async def ws_common_control(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle usage prediction common control WebSocket API."""
    result = await get_cached_common_control(hass, connection.user.id)
    time_category = common_control.time_category(dt_util.now().hour)
    connection.send_result(
        msg["id"],
        {
            "entities": getattr(result, time_category),
        },
    )


class CommonControlView(HomeAssistantView):
    """View to get common control usage predictions for the current user."""

    url = f"/api/{DOMAIN}/common_control"
    name = f"api:{DOMAIN}:common_control"

    async def get(self, request: web.Request) -> web.Response:
        """Return common control usage predictions for the current user."""
        hass = request.app[KEY_HASS]
        result = await get_cached_common_control(hass, request[KEY_HASS_USER].id)
        time_category = common_control.time_category(dt_util.now().hour)
        return self.json({"entities": getattr(result, time_category)})


async def get_cached_common_control(
    hass: HomeAssistant, user_id: str
) -> EntityUsagePredictions:
    """Get cached common control predictions or fetch new ones.

    Returns cached data if it's less than 24 hours old,
    otherwise fetches new data and caches it.
    """
    # Create a unique storage key for this user
    storage_key = user_id

    cached_data = hass.data[DATA_CACHE].get(storage_key)

    if isinstance(cached_data, asyncio.Task):
        # If there's an ongoing task to fetch data, await its result
        return await cached_data

    # Check if cache is valid (less than 24 hours old)
    if cached_data is not None:
        if (dt_util.utcnow() - cached_data.timestamp) < CACHE_DURATION:
            # Cache is still valid, return the cached predictions
            return cached_data.predictions

    # Create task fetching data
    task = hass.async_create_task(
        common_control.async_predict_common_control(hass, user_id)
    )
    hass.data[DATA_CACHE][storage_key] = task

    try:
        predictions = await task
    except Exception:
        # If the task fails, remove it from cache to allow retries
        hass.data[DATA_CACHE].pop(storage_key)
        raise

    hass.data[DATA_CACHE][storage_key] = EntityUsageDataCache(
        predictions=predictions,
    )

    return predictions
