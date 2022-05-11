"""Tests for the logbook component."""
from __future__ import annotations

import json
from typing import Any

from homeassistant.components import logbook
from homeassistant.components.recorder.models import process_timestamp_to_utc_isoformat
from homeassistant.core import Context
from homeassistant.helpers.json import JSONEncoder
import homeassistant.util.dt as dt_util


class MockRow:
    """Minimal row mock."""

    def __init__(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        context: Context | None = None,
    ):
        """Init the fake row."""
        self.event_type = event_type
        self.shared_data = json.dumps(data, cls=JSONEncoder)
        self.data = data
        self.time_fired = dt_util.utcnow()
        self.context_parent_id = context.parent_id if context else None
        self.context_user_id = context.user_id if context else None
        self.context_id = context.id if context else None
        self.state = None
        self.entity_id = None

    @property
    def time_fired_minute(self):
        """Minute the event was fired."""
        return self.time_fired.minute

    @property
    def time_fired_isoformat(self):
        """Time event was fired in utc isoformat."""
        return process_timestamp_to_utc_isoformat(self.time_fired)


def mock_humanify(hass_, rows):
    """Wrap humanify with mocked logbook objects."""
    event_data_cache = {}
    context_lookup = {}
    entity_name_cache = logbook.EntityNameCache(hass_)
    event_cache = logbook.EventCache(event_data_cache)
    context_augmenter = logbook.ContextAugmenter(
        context_lookup, entity_name_cache, {}, event_cache
    )
    return list(
        logbook._humanify(
            hass_, rows, entity_name_cache, event_cache, context_augmenter
        ),
    )
