"""Test event trigger."""

from typing import Any

from freezegun import freeze_time
import pytest

from homeassistant.components.event import DOMAIN, EventEntity
from homeassistant.components.event.const import ATTR_EVENT_TYPE
from homeassistant.components.event.trigger import TRIGGERS
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockEntity, setup_test_component_platform
from tests.components.common import (
    TargetSupport,
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_options_supported,
    assert_triggers_target_support,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


class _MockEventEntity(MockEntity, EventEntity):
    """Mock event entity that exposes its event types."""

    @property
    def event_types(self) -> list[str]:
        """Return the supported event types."""
        return self._handle("event_types")


async def _setup_event_entity(hass: HomeAssistant) -> EventEntity:
    """Set up a single event entity and return the instance."""
    entity = _MockEventEntity(
        name="Torrent", unique_id="torrent", event_types=["downloaded"]
    )
    setup_test_component_platform(hass, DOMAIN, [entity])
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"platform": "test"}})
    await hass.async_block_till_done()
    return entity


@pytest.fixture
async def target_events(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple event entities associated with different targets."""
    return await target_entities(hass, "event")


_TRIGGER_TARGET_SUPPORT: dict[str, TargetSupport] = {
    "received": TargetSupport.STANDARD,
}


@pytest.mark.parametrize(
    ("trigger_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("event.received", {"event_type": ["test_event"]}, False, False),
    ],
)
async def test_event_trigger_options_validation(
    hass: HomeAssistant,
    trigger_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that event triggers support the expected options."""
    await assert_trigger_options_supported(
        hass,
        trigger_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


def test_trigger_target_support() -> None:
    """Certify the trigger registry matches its declared target support."""
    assert_triggers_target_support(TRIGGERS, _TRIGGER_TARGET_SUPPORT)


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("event"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        # Event received with matching event_type
        (
            "event.received",
            {"event_type": ["button_press"]},
            [
                {"included_state": {"state": None, "attributes": {}}, "count": 0},
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
            ],
        ),
        # Event received with non-matching event_type then matching
        (
            "event.received",
            {"event_type": ["button_press"]},
            [
                {"included_state": {"state": None, "attributes": {}}, "count": 0},
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "other_event"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
            ],
        ),
        # Multiple event types configured
        (
            "event.received",
            {"event_type": ["button_press", "button_long_press"]},
            [
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_long_press"},
                    },
                    "count": 1,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:02.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "other_event"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:03.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
            ],
        ),
        # From unavailable - first valid state after unavailable is not triggered
        (
            "event.received",
            {"event_type": ["button_press"]},
            [
                {
                    "included_state": {
                        "state": STATE_UNAVAILABLE,
                        "attributes": {},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
            ],
        ),
        # From unknown - first valid state after unknown is triggered
        (
            "event.received",
            {"event_type": ["button_press"]},
            [
                {
                    "included_state": {
                        "state": STATE_UNKNOWN,
                        "attributes": {},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
                {
                    "included_state": {
                        "state": STATE_UNKNOWN,
                        "attributes": {},
                    },
                    "count": 0,
                },
            ],
        ),
        # Same event type fires again (different timestamps)
        (
            "event.received",
            {"event_type": ["button_press"]},
            [
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:02.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
            ],
        ),
        # To unavailable - should not trigger, and first state
        # after unavailable is skipped
        (
            "event.received",
            {"event_type": ["button_press"]},
            [
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": STATE_UNAVAILABLE,
                        "attributes": {},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:02.000+00:00",
                        "attributes": {ATTR_EVENT_TYPE: "button_press"},
                    },
                    "count": 1,
                },
            ],
        ),
    ],
)
async def test_event_state_trigger(
    hass: HomeAssistant,
    target_events: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict,
    states: list[TriggerStateDescription],
) -> None:
    """Test event trigger fires on matching event entity event."""
    calls: list[str] = []
    other_entity_ids = set(target_events["included_entities"]) - {entity_id}

    # Set all events to the initial state
    for eid in target_events["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, trigger_options, trigger_target_config, calls)

    for state in states[1:]:
        included_state = state["included_state"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(calls) == state["count"]
        for call in calls:
            assert call == entity_id
        calls.clear()

        # Check if changing other events also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(calls) == (entities_in_target - 1) * state["count"]
        calls.clear()


async def test_multiple_events_in_one_millisecond_each_fire(
    hass: HomeAssistant,
) -> None:
    """Test each event fires the trigger even when they share a wall-clock time.

    Reproduces the scenario where an integration emits several events
    synchronously in a single update (e.g. multiple downloads completing in one
    poll). All events share the same millisecond timestamp, but each must still
    fire event.received once.
    """
    entity = await _setup_event_entity(hass)
    calls: list[str] = []
    await arm_trigger(
        hass,
        "event.received",
        {"event_type": ["downloaded"]},
        {"entity_id": entity.entity_id},
        calls,
    )

    with freeze_time("2026-01-01T00:00:00+00:00"):
        for torrent_id in (1, 2, 3):
            entity._trigger_event("downloaded", {"id": torrent_id})
            entity.async_write_ha_state()
        await hass.async_block_till_done()

    assert len(calls) == 3


async def test_attribute_only_change_does_not_fire(hass: HomeAssistant) -> None:
    """Test a cosmetic state re-write (e.g. rename) does not fire the trigger.

    A rename re-writes the state in place with the same timestamp but a new
    friendly_name; this must not be mistaken for a new event.
    """
    entity = await _setup_event_entity(hass)
    with freeze_time("2026-01-01T00:00:00+00:00"):
        entity._trigger_event("downloaded", {"id": 1})
        entity.async_write_ha_state()
        await hass.async_block_till_done()

    calls: list[str] = []
    await arm_trigger(
        hass,
        "event.received",
        {"event_type": ["downloaded"]},
        {"entity_id": entity.entity_id},
        calls,
    )

    current = hass.states.get(entity.entity_id)
    hass.states.async_set(
        entity.entity_id,
        current.state,
        {**current.attributes, ATTR_FRIENDLY_NAME: "Renamed"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 0
