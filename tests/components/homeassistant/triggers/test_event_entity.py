"""The tests for the event entity automation."""

import pytest

from homeassistant.components import automation
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import mock_component


@pytest.fixture(autouse=True)
def setup_comp(hass: HomeAssistant) -> None:
    """Initialize components."""
    mock_component(hass, "group")


async def test_if_fires_on_event(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test for firing on event entity change."""
    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:00.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event_entity",
                    "entity_id": "event.doorbell",
                    "event_type": "button_press",
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": (
                            "{{ trigger.platform }}"
                            " - {{ trigger.entity_id }}"
                            " - {{ trigger.event_type }}"
                            " - {{ trigger.description }}"
                        )
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()

    context = Context()
    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:01.000+00:00",
        {"event_type": "button_press"},
        context=context,
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id
    assert service_calls[0].data["some"] == (
        "event_entity - event.doorbell - button_press"
        " - button_press event of event.doorbell"
    )

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )
    assert len(service_calls) == 2

    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:02.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 2


async def test_if_fires_on_event_uuid(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test for firing on event entity change using a registry id."""
    entry = entity_registry.async_get_or_create(
        "event", "test", "1234", suggested_object_id="doorbell"
    )
    assert entry.entity_id == "event.doorbell"

    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:00.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event_entity",
                    "entity_id": entry.id,
                    "event_type": "button_press",
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    context = Context()
    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:01.000+00:00",
        {"event_type": "button_press"},
        context=context,
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id


async def test_if_fires_on_multiple_entities(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test for firing when multiple entity ids are configured."""
    hass.states.async_set(
        "event.front",
        "2026-01-01T00:00:00.000+00:00",
        {"event_type": "button_press"},
    )
    hass.states.async_set(
        "event.back",
        "2026-01-01T00:00:00.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event_entity",
                    "entity_id": ["event.front", "event.back"],
                    "event_type": "button_press",
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        "event.front",
        "2026-01-01T00:00:01.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    hass.states.async_set(
        "event.back",
        "2026-01-01T00:00:01.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 2


async def test_if_not_fires_on_other_event_type(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the trigger does not fire for non-matching event types."""
    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:00.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event_entity",
                    "entity_id": "event.doorbell",
                    "event_type": "button_press",
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:01.000+00:00",
        {"event_type": "button_long_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:02.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_on_repeated_event_type(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the trigger fires every time the event entity state changes."""
    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:00.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event_entity",
                    "entity_id": "event.doorbell",
                    "event_type": "button_press",
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:01.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:02.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 2


async def test_if_not_fires_when_to_unavailable(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the trigger does not fire when transitioning to unavailable."""
    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:00.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event_entity",
                    "entity_id": "event.doorbell",
                    "event_type": "button_press",
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("event.doorbell", STATE_UNAVAILABLE, {})
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_if_not_fires_when_to_unknown(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the trigger does not fire when transitioning to unknown."""
    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:00.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event_entity",
                    "entity_id": "event.doorbell",
                    "event_type": "button_press",
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("event.doorbell", STATE_UNKNOWN, {})
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_if_not_fires_from_unavailable(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the first event after an unavailable state is suppressed."""
    hass.states.async_set("event.doorbell", STATE_UNAVAILABLE, {})
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event_entity",
                    "entity_id": "event.doorbell",
                    "event_type": "button_press",
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    # First valid state after unavailable should not trigger
    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:00.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Subsequent state changes should trigger
    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:01.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_from_unknown(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the first event after an unknown state still triggers."""
    hass.states.async_set("event.doorbell", STATE_UNKNOWN, {})
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event_entity",
                    "entity_id": "event.doorbell",
                    "event_type": "button_press",
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:00.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_not_fires_for_other_entity(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that the trigger only fires for the configured entity."""
    hass.states.async_set(
        "event.doorbell",
        "2026-01-01T00:00:00.000+00:00",
        {"event_type": "button_press"},
    )
    hass.states.async_set(
        "event.other",
        "2026-01-01T00:00:00.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event_entity",
                    "entity_id": "event.doorbell",
                    "event_type": "button_press",
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        "event.other",
        "2026-01-01T00:00:01.000+00:00",
        {"event_type": "button_press"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0
