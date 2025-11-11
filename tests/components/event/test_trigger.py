"""Test event trigger."""

from homeassistant.components import automation
from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.const import CONF_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util


async def test_event_detected_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the event detected trigger fires when an event is detected."""
    entity_id = "event.test_event"
    await async_setup_component(hass, "event", {})

    # Set initial state
    hass.states.async_set(
        entity_id,
        dt_util.utcnow().isoformat(timespec="milliseconds"),
        {ATTR_EVENT_TYPE: "button_press"},
    )
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "event.detected",
                    "target": {CONF_ENTITY_ID: entity_id},
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                    },
                },
            }
        },
    )

    # Trigger event
    hass.states.async_set(
        entity_id,
        dt_util.utcnow().isoformat(timespec="milliseconds"),
        {ATTR_EVENT_TYPE: "button_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Trigger same event type again - should still trigger
    hass.states.async_set(
        entity_id,
        dt_util.utcnow().isoformat(timespec="milliseconds"),
        {ATTR_EVENT_TYPE: "button_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id


async def test_event_detected_trigger_with_event_type_filter(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the event detected trigger with event_type filter."""
    entity_id = "event.test_event"
    await async_setup_component(hass, "event", {})

    # Set initial state
    hass.states.async_set(
        entity_id,
        dt_util.utcnow().isoformat(timespec="milliseconds"),
        {ATTR_EVENT_TYPE: "button_press"},
    )
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "event.detected",
                    "target": {
                        CONF_ENTITY_ID: entity_id,
                    },
                    "options": {
                        "event_type": ["button_press", "button_hold"],
                    },
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                    },
                },
            }
        },
    )

    # Trigger matching event type
    hass.states.async_set(
        entity_id,
        dt_util.utcnow().isoformat(timespec="milliseconds"),
        {ATTR_EVENT_TYPE: "button_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Trigger different matching event type
    hass.states.async_set(
        entity_id,
        dt_util.utcnow().isoformat(timespec="milliseconds"),
        {ATTR_EVENT_TYPE: "button_hold"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
    service_calls.clear()

    # Trigger non-matching event type - should not trigger
    hass.states.async_set(
        entity_id,
        dt_util.utcnow().isoformat(timespec="milliseconds"),
        {ATTR_EVENT_TYPE: "button_release"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_event_detected_trigger_ignores_unavailable(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the event detected trigger ignores unavailable states."""
    entity_id = "event.test_event"
    await async_setup_component(hass, "event", {})

    # Set initial state
    hass.states.async_set(
        entity_id,
        dt_util.utcnow().isoformat(timespec="milliseconds"),
        {ATTR_EVENT_TYPE: "button_press"},
    )
    await hass.async_block_till_done()

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "event.detected",
                    "target": {
                        CONF_ENTITY_ID: entity_id,
                    },
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                    },
                },
            }
        },
    )

    # Set to unavailable - should not trigger
    hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Trigger event after unavailable - should trigger
    hass.states.async_set(
        entity_id,
        dt_util.utcnow().isoformat(timespec="milliseconds"),
        {ATTR_EVENT_TYPE: "button_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id


async def test_event_detected_trigger_sequential_same_event_type(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the event detected trigger fires for sequential events of the same type."""
    entity_id = "event.test_event"
    await async_setup_component(hass, "event", {})

    # Set initial state
    hass.states.async_set(
        entity_id,
        dt_util.utcnow().isoformat(timespec="milliseconds"),
        {ATTR_EVENT_TYPE: "button_press"},
    )

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "event.detected",
                    "target": {CONF_ENTITY_ID: entity_id},
                },
                "actions": {
                    "action": "test.automation",
                    "data": {CONF_ENTITY_ID: entity_id},
                },
            }
        },
    )

    # Trigger same event type multiple times in a row
    for _ in range(3):
        hass.states.async_set(
            entity_id,
            dt_util.utcnow().isoformat(timespec="milliseconds"),
            {ATTR_EVENT_TYPE: "button_press"},
        )
        await hass.async_block_till_done()

    # Should have triggered 3 times
    assert len(service_calls) == 3
    for service_call in service_calls:
        assert service_call.data[CONF_ENTITY_ID] == entity_id


async def test_event_detected_trigger_from_unknown_state(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the trigger fires when entity goes from unknown/None to first event.

    Event entities restore their state, so on first creation they have no state.
    """
    entity_id = "event.test_event"
    await async_setup_component(hass, "event", {})

    # Do NOT set any initial state - entity starts with None state

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "event.detected",
                    "target": {CONF_ENTITY_ID: entity_id},
                },
                "actions": {
                    "action": "test.automation",
                    "data": {
                        CONF_ENTITY_ID: "{{ trigger.entity_id }}",
                    },
                },
            }
        },
    )

    # First event should trigger even though entity had no previous state
    hass.states.async_set(
        entity_id,
        dt_util.utcnow().isoformat(timespec="milliseconds"),
        {ATTR_EVENT_TYPE: "button_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id
