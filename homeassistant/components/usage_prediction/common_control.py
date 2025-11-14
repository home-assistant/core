"""Code to generate common control usage patterns."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from functools import cache
import logging
from typing import Any, Literal, cast

from sqlalchemy import select
from sqlalchemy.engine.row import Row
from sqlalchemy.orm import Session

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.db_schema import (
    EventData,
    Events,
    EventTypes,
    StateAttributes,
    States,
)
from homeassistant.components.recorder.models import uuid_hex_to_bytes_or_none
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import ATTR_USER_ID, STATE_HOME, STATE_NOT_HOME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.json import json_loads_object

from .models import EntityUsagePredictions, LocationBasedPredictions

_LOGGER = logging.getLogger(__name__)

# Time categories for usage patterns
TIME_CATEGORIES = ["morning", "afternoon", "evening", "night"]

RESULTS_TO_INCLUDE = 8

# List of domains for which we want to track usage
ALLOWED_DOMAINS = {
    # Entity platforms
    Platform.AIR_QUALITY,
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.FAN,
    Platform.HUMIDIFIER,
    Platform.LAWN_MOWER,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SCENE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.VACUUM,
    Platform.VALVE,
    Platform.WATER_HEATER,
    # Helpers with own domain
    "counter",
    "group",
    "input_boolean",
    "input_button",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "schedule",
    "timer",
}


@cache
def time_category(hour: int) -> Literal["morning", "afternoon", "evening", "night"]:
    """Determine the time category for a given hour."""
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 22:
        return "evening"
    return "night"


def get_person_entity_id_for_user(hass: HomeAssistant, user_id: str) -> str | None:
    """Get the person entity ID for a given user ID."""
    for state in hass.states.async_all("person"):
        if state.attributes.get(ATTR_USER_ID) == user_id:
            return state.entity_id
    return None


async def async_predict_common_control(
    hass: HomeAssistant, user_id: str
) -> LocationBasedPredictions:
    """Generate a list of commonly used entities for a user.

    Args:
        hass: Home Assistant instance
        user_id: User ID to filter events by.
    """
    # Get the recorder instance to ensure it's ready
    recorder = get_instance(hass)
    ent_reg = er.async_get(hass)

    # Get the person entity ID for this user
    person_entity_id = get_person_entity_id_for_user(hass, user_id)

    # Execute the database operation in the recorder's executor
    data = await recorder.async_add_executor_job(
        _fetch_with_session,
        hass,
        _fetch_and_process_data,
        ent_reg,
        user_id,
        person_entity_id,
    )
    # Prepare a dictionary to track results by location and time
    results: dict[str, dict[str, Counter[str]]] = {}

    allowed_entities = set(hass.states.async_entity_ids(ALLOWED_DOMAINS))
    hidden_entities: set[str] = set()

    # Keep track of contexts that we processed so that we will only process
    # the first service call in a context, and not subsequent calls.
    context_processed: set[bytes] = set()
    # Execute the query
    context_id: bytes
    time_fired_ts: float
    shared_data: str | None
    person_state: str | None
    local_time_zone = dt_util.get_default_time_zone()
    for context_id, time_fired_ts, shared_data, person_state in data:
        # Skip if we have already processed an event that was part of this context
        if context_id in context_processed:
            continue

        # Mark this context as processed
        context_processed.add(context_id)

        # Parse the event data
        if not time_fired_ts or not shared_data:
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

        # Determine location state (default to "home" if no person state)
        location = person_state if person_state else STATE_HOME

        # Initialize location results if needed
        if location not in results:
            results[location] = {time_cat: Counter() for time_cat in TIME_CATEGORIES}

        # Convert to local time for time category determination
        period = time_category(
            datetime.fromtimestamp(time_fired_ts, local_time_zone).hour
        )
        period_results = results[location][period]

        # Count entity usage
        for entity_id in entity_ids:
            if entity_id not in allowed_entities or entity_id in hidden_entities:
                continue

            if (
                entity_id not in period_results
                and (entry := ent_reg.async_get(entity_id))
                and entry.hidden
            ):
                hidden_entities.add(entity_id)
                continue

            period_results[entity_id] += 1

    # Build location-based predictions
    location_predictions = {}
    for location, time_results in results.items():
        location_predictions[location] = EntityUsagePredictions(
            morning=[
                ent_id
                for (ent_id, _) in time_results["morning"].most_common(
                    RESULTS_TO_INCLUDE
                )
            ],
            afternoon=[
                ent_id
                for (ent_id, _) in time_results["afternoon"].most_common(
                    RESULTS_TO_INCLUDE
                )
            ],
            evening=[
                ent_id
                for (ent_id, _) in time_results["evening"].most_common(
                    RESULTS_TO_INCLUDE
                )
            ],
            night=[
                ent_id
                for (ent_id, _) in time_results["night"].most_common(RESULTS_TO_INCLUDE)
            ],
        )

    return LocationBasedPredictions(location_predictions=location_predictions)


def _fetch_and_process_data(
    session: Session, ent_reg: er.EntityRegistry, user_id: str, person_entity_id: str | None
) -> Sequence[Row[tuple[bytes | None, float | None, str | None, str | None]]]:
    """Fetch and process service call events from the database with person states."""
    thirty_days_ago_ts = (dt_util.utcnow() - timedelta(days=30)).timestamp()
    user_id_bytes = uuid_hex_to_bytes_or_none(user_id)
    if not user_id_bytes:
        raise ValueError("Invalid user_id format")

    # If no person entity ID, return events without person states
    if not person_entity_id:
        query = (
            select(
                Events.context_id_bin,
                Events.time_fired_ts,
                EventData.shared_data,
                None,  # No person state
            )
            .select_from(Events)
            .outerjoin(EventData, Events.data_id == EventData.data_id)
            .outerjoin(EventTypes, Events.event_type_id == EventTypes.event_type_id)
            .where(Events.time_fired_ts >= thirty_days_ago_ts)
            .where(Events.context_user_id_bin == user_id_bytes)
            .where(EventTypes.event_type == "call_service")
            .order_by(Events.time_fired_ts)
        )
        return session.connection().execute(query).all()

    # Get the entity registry entry for the person
    person_entry = ent_reg.async_get(person_entity_id)
    if not person_entry or not person_entry.id:
        # No valid person entry, return without person states
        query = (
            select(
                Events.context_id_bin,
                Events.time_fired_ts,
                EventData.shared_data,
                None,
            )
            .select_from(Events)
            .outerjoin(EventData, Events.data_id == EventData.data_id)
            .outerjoin(EventTypes, Events.event_type_id == EventTypes.event_type_id)
            .where(Events.time_fired_ts >= thirty_days_ago_ts)
            .where(Events.context_user_id_bin == user_id_bytes)
            .where(EventTypes.event_type == "call_service")
            .order_by(Events.time_fired_ts)
        )
        return session.connection().execute(query).all()

    # Create a subquery to get the most recent person state before each event
    PersonStates = States.__table__.alias("person_states")
    subquery = (
        select(PersonStates.c.state)
        .where(PersonStates.c.metadata_id == person_entry.id)
        .where(PersonStates.c.last_updated_ts <= Events.time_fired_ts)
        .order_by(PersonStates.c.last_updated_ts.desc())
        .limit(1)
        .scalar_subquery()
    )

    # Build the main query for events with their data and person states
    query = (
        select(
            Events.context_id_bin,
            Events.time_fired_ts,
            EventData.shared_data,
            subquery.label("person_state"),
        )
        .select_from(Events)
        .outerjoin(EventData, Events.data_id == EventData.data_id)
        .outerjoin(EventTypes, Events.event_type_id == EventTypes.event_type_id)
        .where(Events.time_fired_ts >= thirty_days_ago_ts)
        .where(Events.context_user_id_bin == user_id_bytes)
        .where(EventTypes.event_type == "call_service")
        .order_by(Events.time_fired_ts)
    )
    return session.connection().execute(query).all()


def _fetch_with_session(
    hass: HomeAssistant,
    fetch_func: Callable[
        [Session], Sequence[Row[tuple[bytes | None, float | None, str | None, str | None]]]
    ],
    *args: object,
) -> Sequence[Row[tuple[bytes | None, float | None, str | None, str | None]]]:
    """Execute a fetch function with a database session."""
    with session_scope(hass=hass, read_only=True) as session:
        return fetch_func(session, *args)
