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
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SERVICE,
    EVENT_CALL_SERVICE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.json import JSONEncoder
from homeassistant.util import dt as dt_util

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
        self.time_fired_ts = self.time_fired.timestamp()
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


def setup_thermostat_context_test_entities(hass_: HomeAssistant) -> None:
    """Set up initial states for the thermostat context chain test entities."""
    hass_.states.async_set(
        "climate.living_room",
        "off",
        {ATTR_FRIENDLY_NAME: "Living Room Thermostat"},
    )
    hass_.states.async_set("switch.heater", STATE_OFF)


def simulate_thermostat_context_chain(
    hass_: HomeAssistant,
    user_id: str = "b400facee45711eaa9308bfd3d19e474",
) -> tuple[Context, Context]:
    """Simulate the generic_thermostat context chain.

    Fires events in the realistic order:
    1. EVENT_CALL_SERVICE for set_hvac_mode (parent context)
    2. EVENT_CALL_SERVICE for homeassistant.turn_on (child context)
    3. Climate state changes off → heat (parent context)
    4. Switch state changes off → on (child context)

    Returns the (parent_context, child_context) tuple.
    """
    parent_context = Context(
        id="01GTDGKBCH00GW0X476W5TVAAA",
        user_id=user_id,
    )
    child_context = Context(
        id="01GTDGKBCH00GW0X476W5TVDDD",
        parent_id=parent_context.id,
    )

    hass_.bus.async_fire(
        EVENT_CALL_SERVICE,
        {
            ATTR_DOMAIN: "climate",
            ATTR_SERVICE: "set_hvac_mode",
            "service_data": {ATTR_ENTITY_ID: "climate.living_room"},
        },
        context=parent_context,
    )
    hass_.bus.async_fire(
        EVENT_CALL_SERVICE,
        {
            ATTR_DOMAIN: "homeassistant",
            ATTR_SERVICE: "turn_on",
            "service_data": {ATTR_ENTITY_ID: "switch.heater"},
        },
        context=child_context,
    )
    hass_.states.async_set(
        "climate.living_room",
        "heat",
        {ATTR_FRIENDLY_NAME: "Living Room Thermostat"},
        context=parent_context,
    )
    hass_.states.async_set(
        "switch.heater",
        STATE_ON,
        {ATTR_FRIENDLY_NAME: "Heater"},
        context=child_context,
    )
    return parent_context, child_context


def assert_thermostat_context_chain_events(
    events: list[dict[str, Any]], parent_context: Context
) -> None:
    """Assert the logbook events for a thermostat context chain.

    Verifies that climate and switch state changes have correct
    state, user attribution, and service call context.
    """
    climate_entries = [e for e in events if e.get("entity_id") == "climate.living_room"]
    assert len(climate_entries) == 1
    assert climate_entries[0]["state"] == "heat"
    assert climate_entries[0]["context_user_id"] == parent_context.user_id
    assert climate_entries[0]["context_event_type"] == EVENT_CALL_SERVICE
    assert climate_entries[0]["context_domain"] == "climate"
    assert climate_entries[0]["context_service"] == "set_hvac_mode"

    heater_entries = [e for e in events if e.get("entity_id") == "switch.heater"]
    assert len(heater_entries) == 1
    assert heater_entries[0]["state"] == "on"
    assert heater_entries[0]["context_user_id"] == parent_context.user_id
    assert heater_entries[0]["context_event_type"] == EVENT_CALL_SERVICE
    assert heater_entries[0]["context_domain"] == "homeassistant"
    assert heater_entries[0]["context_service"] == "turn_on"


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
            None,
        ),
    )
