"""Code to generate common control usage patterns."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import cache
import logging
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.db_schema import EventData, Events, EventTypes
from homeassistant.components.recorder.models import uuid_hex_to_bytes_or_none
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util.json import json_loads_object

_LOGGER = logging.getLogger(__name__)

# Time categories for usage patterns
TIME_CATEGORIES = ["morning", "afternoon", "evening", "night"]

RESULTS_TO_SHOW = 8


@cache
def time_category(hour: int) -> str:
    """Determine the time category for a given hour."""
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 22:
        return "evening"
    return "night"


async def async_predict_common_control(
    hass: HomeAssistant, user_id: str
) -> dict[str, list[str]]:
    """Generate a list of commonly used entities for a user.

    Args:
        hass: Home Assistant instance
        user_id: User ID to filter events by.

    Returns:
        Dictionary with time categories as keys and lists of most common entity IDs as values
    """
    # Get the recorder instance to ensure it's ready
    recorder = get_instance(hass)

    # Execute the database operation in the recorder's executor
    return await recorder.async_add_executor_job(
        _fetch_with_session, hass, _fetch_and_process_data, user_id
    )


def _fetch_and_process_data(session: Session, user_id: str) -> dict[str, list[str]]:
    """Fetch and process service call events from the database."""
    # Prepare a dictionary to track results
    results: dict[str, Counter[str]] = {
        time_cat: Counter() for time_cat in TIME_CATEGORIES
    }

    # Keep track of contexts that we processed so that we will only process
    # the first service call in a context, and not subsequent calls.
    context_processed: set[bytes] = set()
    thirty_days_ago_ts = (dt_util.utcnow() - timedelta(days=30)).timestamp()
    user_id_bytes = uuid_hex_to_bytes_or_none(user_id)
    if not user_id_bytes:
        raise ValueError("Invalid user_id format")

    # Build the main query for events with their data
    query = (
        select(
            Events.context_id_bin,
            Events.time_fired_ts,
            EventData.shared_data,
        )
        .select_from(Events)
        .outerjoin(EventData, Events.data_id == EventData.data_id)
        .outerjoin(EventTypes, Events.event_type_id == EventTypes.event_type_id)
        .where(Events.time_fired_ts >= thirty_days_ago_ts)
        .where(Events.context_user_id_bin == user_id_bytes)
        .where(EventTypes.event_type == "call_service")
        .order_by(Events.time_fired_ts)
    )

    # Execute the query
    context_id: bytes
    time_fired_ts: float
    shared_data: str | None
    local_time_zone = dt_util.get_default_time_zone()
    for context_id, time_fired_ts, shared_data in (
        session.connection().execute(query).all()
    ):
        # Skip if we have already processed an event that was part of this context
        if context_id in context_processed:
            continue

        # Parse the event data
        if not shared_data:
            continue

        try:
            event_data = json_loads_object(shared_data)
        except (ValueError, TypeError) as err:
            _LOGGER.debug("Failed to parse event data: %s", err)
            continue

        # Empty event data, skipping
        if not event_data:
            continue

        service_data = cast(dict[str, Any] | None, event_data.get("service_data"))

        # No service data found, skipping
        if not service_data:
            continue

        entity_ids: str | list[str] | None
        if (target := service_data.get("target")) and (
            target_entity_ids := target.get("entity_id")
        ):
            entity_ids = target_entity_ids
        else:
            entity_ids = service_data.get("entity_id")

        # No entity IDs found, skip this event
        if entity_ids is None:
            continue

        if not isinstance(entity_ids, list):
            entity_ids = [entity_ids]

        # Mark this context as processed
        context_processed.add(context_id)

        # Convert timestamp to datetime and determine time category
        if time_fired_ts:
            # Convert to local time for time category determination
            period = time_category(
                datetime.fromtimestamp(time_fired_ts, local_time_zone).hour
            )

            # Count entity usage
            for entity_id in entity_ids:
                results[period][entity_id] += 1

    # Convert results to lists of top entities
    return {
        period: [ent_id for (ent_id, _) in period_results.most_common(RESULTS_TO_SHOW)]
        for period, period_results in results.items()
    }


def _fetch_with_session(
    hass: HomeAssistant, fetch_func: Callable[[Session], dict[str, list[str]]], *args
) -> dict[str, list[str]]:
    """Execute a fetch function with a database session."""
    with session_scope(hass=hass, read_only=True) as session:
        return fetch_func(session, *args)
