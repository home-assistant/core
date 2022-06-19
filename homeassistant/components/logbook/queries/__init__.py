"""Queries for logbook."""
from __future__ import annotations

from datetime import datetime as dt
import json

from sqlalchemy.sql.selectable import Select

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
) -> Select:
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

    # entities and devices: logbook sends everything for the timeframe for the entities and devices
    if entity_ids and device_ids:
        json_quoted_entity_ids = [json.dumps(entity_id) for entity_id in entity_ids]
        json_quoted_device_ids = [json.dumps(device_id) for device_id in device_ids]
        return entities_devices_stmt(
            start_day,
            end_day,
            event_types,
            entity_ids,
            json_quoted_entity_ids,
            json_quoted_device_ids,
        )

    # entities: logbook sends everything for the timeframe for the entities
    if entity_ids:
        json_quoted_entity_ids = [json.dumps(entity_id) for entity_id in entity_ids]
        return entities_stmt(
            start_day,
            end_day,
            event_types,
            entity_ids,
            json_quoted_entity_ids,
        )

    # devices: logbook sends everything for the timeframe for the devices
    assert device_ids is not None
    json_quoted_device_ids = [json.dumps(device_id) for device_id in device_ids]
    return devices_stmt(
        start_day,
        end_day,
        event_types,
        json_quoted_device_ids,
    )
