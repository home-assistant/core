"""Tests for the logbook component."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.components import logbook
from homeassistant.components.logbook import processor
from homeassistant.components.logbook.models import EventAsRow, LogbookConfig
from homeassistant.components.recorder.models import (
    process_timestamp_to_utc_isoformat,
    ulid_to_bytes_or_none,
    uuid_hex_to_bytes_or_none,
)
from homeassistant.core import Context
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.json import JSONEncoder
import homeassistant.util.dt as dt_util

IDX_TO_NAME = dict(enumerate(EventAsRow._fields))


class MockRow:
    """Minimal row mock."""

    def __init__(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        context: Context | None = None,
    ) -> None:
        """Init the fake row."""
        self.event_type = event_type
        self.event_data = json.dumps(data, cls=JSONEncoder)
        self.data = data
        self.time_fired = dt_util.utcnow()
        self.time_fired_ts = dt_util.utc_to_timestamp(self.time_fired)
        self.context_parent_id_bin = (
            ulid_to_bytes_or_none(context.parent_id) if context else None
        )
        self.context_user_id_bin = (
            uuid_hex_to_bytes_or_none(context.user_id) if context else None
        )
        self.context_id_bin = ulid_to_bytes_or_none(context.id) if context else None
        self.state = None
        self.entity_id = None
        self.row_id = None
        self.shared_attrs = None
        self.attributes = None
        self.context_only = False

    def __getitem__(self, idx: int) -> Any:
        """Get item."""
        return getattr(self, IDX_TO_NAME[idx])

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
    entity_name_cache = processor.EntityNameCache(hass_)
    ent_reg = er.async_get(hass_)
    event_cache = processor.EventCache({})
    context_lookup = {}
    logbook_config = hass_.data.get(logbook.DOMAIN, LogbookConfig({}, None, None))
    external_events = logbook_config.external_events
    logbook_run = processor.LogbookRun(
        context_lookup,
        external_events,
        event_cache,
        entity_name_cache,
        include_entity_name=True,
        timestamp=False,
    )
    context_augmenter = processor.ContextAugmenter(logbook_run)
    return list(
        processor._humanify(
            hass_,
            rows,
            ent_reg,
            logbook_run,
            context_augmenter,
        ),
    )
