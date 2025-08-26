"""The usage prediction integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from . import common_control
from .const import DOMAIN

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

# Storage configuration
STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}.common_control"
CACHE_DURATION = timedelta(hours=24)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the usage prediction integration."""
    websocket_api.async_register_command(hass, ws_common_control)

    # Initialize domain data storage
    hass.data[DOMAIN] = {}

    return True


@websocket_api.websocket_command(
    {
        "type": f"{DOMAIN}/common_control",
        "user_id": cv.string,
    }
)
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
            "entities": result[time_category],
        },
    )


async def get_cached_common_control(
    hass: HomeAssistant, user_id: str
) -> dict[str, list[str]]:
    """Get cached common control predictions or fetch new ones.

    Returns cached data if it's less than 24 hours old,
    otherwise fetches new data and caches it.
    """
    # Create a unique storage key for this user
    storage_key = f"{STORAGE_KEY_PREFIX}.{user_id}"

    # Get or create store for this user
    if storage_key not in hass.data[DOMAIN]:
        hass.data[DOMAIN][storage_key] = Store[dict[str, Any]](
            hass, STORAGE_VERSION, storage_key, private=True
        )

    store: Store[dict[str, Any]] = hass.data[DOMAIN][storage_key]

    # Load cached data
    cached_data = await store.async_load()

    # Check if cache is valid (less than 24 hours old)
    now = dt_util.utcnow()
    if cached_data is not None:
        cached_time = dt_util.parse_datetime(cached_data.get("timestamp", ""))
        if cached_time and (now - cached_time) < CACHE_DURATION:
            # Cache is still valid, return the cached predictions
            return cached_data["predictions"]

    # Cache is expired or doesn't exist, fetch new data
    predictions = await common_control.async_predict_common_control(hass, user_id)

    # Store the new data with timestamp
    cache_data = {
        "timestamp": now.isoformat(),
        "predictions": predictions,
    }

    # Save to cache
    await store.async_save(cache_data)

    return predictions
