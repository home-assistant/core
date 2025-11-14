"""The usage prediction integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from . import common_control
from .const import DATA_CACHE, DOMAIN
from .models import EntityUsageDataCache, EntityUsagePredictions, LocationBasedPredictions

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

CACHE_DURATION = timedelta(hours=24)


def get_predictions_for_location(
    location_predictions: LocationBasedPredictions, location_state: str
) -> EntityUsagePredictions:
    """Get predictions for a specific location with fallback logic.

    If the user's state is set to anything but 'home' and 'not_home',
    and it has no results, fall back to 'not_home'.
    If that has no results, fall back to 'home'.
    """
    # Try to get predictions for the specified location
    if location_state in location_predictions.location_predictions:
        predictions = location_predictions.location_predictions[location_state]
        # Check if predictions have any entities
        if any(
            [
                predictions.morning,
                predictions.afternoon,
                predictions.evening,
                predictions.night,
            ]
        ):
            return predictions

    # If not home or not_home, and no results, try fallback
    if location_state not in (STATE_HOME, STATE_NOT_HOME):
        # Try not_home first
        if STATE_NOT_HOME in location_predictions.location_predictions:
            predictions = location_predictions.location_predictions[STATE_NOT_HOME]
            if any(
                [
                    predictions.morning,
                    predictions.afternoon,
                    predictions.evening,
                    predictions.night,
                ]
            ):
                return predictions

        # Fall back to home
        if STATE_HOME in location_predictions.location_predictions:
            predictions = location_predictions.location_predictions[STATE_HOME]
            if any(
                [
                    predictions.morning,
                    predictions.afternoon,
                    predictions.evening,
                    predictions.night,
                ]
            ):
                return predictions

    # Return empty predictions if nothing found
    return EntityUsagePredictions()


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the usage prediction integration."""
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

    # Get the current person state for the user
    person_entity_id = common_control.get_person_entity_id_for_user(
        hass, connection.user.id
    )
    current_location = STATE_HOME  # Default to home
    if person_entity_id and (person_state := hass.states.get(person_entity_id)):
        current_location = person_state.state

    # Get predictions for the current location with fallback
    location_predictions = get_predictions_for_location(result, current_location)

    connection.send_result(
        msg["id"],
        {
            "entities": getattr(location_predictions, time_category),
        },
    )


async def get_cached_common_control(
    hass: HomeAssistant, user_id: str
) -> LocationBasedPredictions:
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
