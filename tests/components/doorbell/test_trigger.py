"""Test doorbell trigger."""

from typing import Any

import pytest

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.components.common import (
    BasicTriggerStateDescription,
    arm_trigger,
    assert_trigger_gated_by_labs_flag,
    assert_trigger_options_supported,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_events(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple event entities associated with different targets."""
    return await target_entities(hass, "event")


@pytest.mark.parametrize("trigger_key", ["doorbell.rang"])
async def test_doorbell_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the doorbell triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(
        hass,
        caplog,
        trigger_key,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("doorbell.rang", None, False, False),
    ],
)
async def test_doorbell_trigger_options_validation(
    hass: HomeAssistant,
    trigger_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that doorbell triggers support the expected options."""
    await assert_trigger_options_supported(
        hass,
        trigger_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("event"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        # Doorbell rang with ring event_type
        (
            "doorbell.rang",
            [
                {
                    "included_state": {
                        "state": STATE_UNAVAILABLE,
                        "attributes": {ATTR_DEVICE_CLASS: "doorbell"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {
                            ATTR_DEVICE_CLASS: "doorbell",
                            ATTR_EVENT_TYPE: "ring",
                        },
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {
                            ATTR_DEVICE_CLASS: "doorbell",
                            ATTR_EVENT_TYPE: "ring",
                        },
                    },
                    "count": 1,
                },
            ],
        ),
        # From unknown - first valid state after unknown is triggered
        (
            "doorbell.rang",
            [
                {
                    "included_state": {
                        "state": STATE_UNKNOWN,
                        "attributes": {ATTR_DEVICE_CLASS: "doorbell"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {
                            ATTR_DEVICE_CLASS: "doorbell",
                            ATTR_EVENT_TYPE: "ring",
                        },
                    },
                    "count": 1,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {
                            ATTR_DEVICE_CLASS: "doorbell",
                            ATTR_EVENT_TYPE: "ring",
                        },
                    },
                    "count": 1,
                },
                {
                    "included_state": {
                        "state": STATE_UNKNOWN,
                        "attributes": {ATTR_DEVICE_CLASS: "doorbell"},
                    },
                    "count": 0,
                },
            ],
        ),
        # Same ring event fires again (different timestamps)
        (
            "doorbell.rang",
            [
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {
                            ATTR_DEVICE_CLASS: "doorbell",
                            ATTR_EVENT_TYPE: "ring",
                        },
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {
                            ATTR_DEVICE_CLASS: "doorbell",
                            ATTR_EVENT_TYPE: "ring",
                        },
                    },
                    "count": 1,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:02.000+00:00",
                        "attributes": {
                            ATTR_DEVICE_CLASS: "doorbell",
                            ATTR_EVENT_TYPE: "ring",
                        },
                    },
                    "count": 1,
                },
            ],
        ),
        # To unavailable - should not trigger, and first state after unavailable is skipped
        (
            "doorbell.rang",
            [
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {
                            ATTR_DEVICE_CLASS: "doorbell",
                            ATTR_EVENT_TYPE: "ring",
                        },
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": STATE_UNAVAILABLE,
                        "attributes": {ATTR_DEVICE_CLASS: "doorbell"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {
                            ATTR_DEVICE_CLASS: "doorbell",
                            ATTR_EVENT_TYPE: "ring",
                        },
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:02.000+00:00",
                        "attributes": {
                            ATTR_DEVICE_CLASS: "doorbell",
                            ATTR_EVENT_TYPE: "ring",
                        },
                    },
                    "count": 1,
                },
            ],
        ),
        # Non-ring event_type should not trigger
        (
            "doorbell.rang",
            [
                {
                    "included_state": {
                        "state": STATE_UNAVAILABLE,
                        "attributes": {ATTR_DEVICE_CLASS: "doorbell"},
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {
                            ATTR_DEVICE_CLASS: "doorbell",
                            ATTR_EVENT_TYPE: "other_event",
                        },
                    },
                    "count": 0,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:01.000+00:00",
                        "attributes": {
                            ATTR_DEVICE_CLASS: "doorbell",
                            ATTR_EVENT_TYPE: "ring",
                        },
                    },
                    "count": 1,
                },
                {
                    "included_state": {
                        "state": "2026-01-01T00:00:00.000+00:00",
                        "attributes": {
                            ATTR_DEVICE_CLASS: "doorbell",
                            ATTR_EVENT_TYPE: "other_event",
                        },
                    },
                    "count": 0,
                },
            ],
        ),
    ],
)
async def test_doorbell_rang_trigger(
    hass: HomeAssistant,
    target_events: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[BasicTriggerStateDescription],
) -> None:
    """Test that the doorbell rang trigger fires when a doorbell ring event is received."""
    calls: list[str] = []
    other_entity_ids = set(target_events["included_entities"]) - {entity_id}

    # Set all events to the initial state
    for eid in target_events["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, None, trigger_target_config, calls)

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
