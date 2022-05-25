"""Queries for logbook."""
from __future__ import annotations

from datetime import datetime as dt

from sqlalchemy.sql.lambdas import StatementLambdaElement

from homeassistant.components.recorder.filters import Filters

from .all import all_stmt
from .devices import devices_stmt
from .entities import entities_stmt
from .entities_and_devices import entities_devices_stmt


def statement_for_request(
    start_day: dt,
    end_day: dt,
    event_types: tuple[str, ...],
    entity_ids: list[str] | None = None,
    device_ids: list[str] | None = None,
    filters: Filters | None = None,
    context_id: str | None = None,
) -> StatementLambdaElement:
    """Generate the logbook statement for a logbook request."""

    # No entities: logbook sends everything for the timeframe
    # limited by the context_id and the yaml configured filter
    if not entity_ids and not device_ids:
        states_entity_filter = filters.states_entity_filter() if filters else None
        events_entity_filter = filters.events_entity_filter() if filters else None
        return all_stmt(
            start_day,
            end_day,
            event_types,
            states_entity_filter,
            events_entity_filter,
            context_id,
        )

    # sqlalchemy caches object quoting, the
    # json quotable ones must be a different
    # object from the non-json ones to prevent
    # sqlalchemy from quoting them incorrectly

    # entities and devices: logbook sends everything for the timeframe for the entities and devices
    if entity_ids and device_ids:
        json_quotable_entity_ids = list(entity_ids)
        json_quotable_device_ids = list(device_ids)
        return entities_devices_stmt(
            start_day,
            end_day,
            event_types,
            entity_ids,
            json_quotable_entity_ids,
            json_quotable_device_ids,
        )

    # entities: logbook sends everything for the timeframe for the entities
    if entity_ids:
        json_quotable_entity_ids = list(entity_ids)
        return entities_stmt(
            start_day,
            end_day,
            event_types,
            entity_ids,
            json_quotable_entity_ids,
        )

    # devices: logbook sends everything for the timeframe for the devices
    assert device_ids is not None
    json_quotable_device_ids = list(device_ids)
    return devices_stmt(
        start_day,
        end_day,
        event_types,
        json_quotable_device_ids,
    )
