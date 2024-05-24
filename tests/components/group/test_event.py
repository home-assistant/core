"""The tests for the group event platform."""

from pytest_unordered import unordered

from homeassistant.components.event import DOMAIN as EVENT_DOMAIN
from homeassistant.components.event.const import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES
from homeassistant.components.group import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_default_state(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test event group default state."""
    await async_setup_component(
        hass,
        EVENT_DOMAIN,
        {
            EVENT_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["event.button_1", "event.button_2"],
                "name": "Remote control",
                "unique_id": "unique_identifier",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("event.remote_control")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set(
        "event.button_1",
        "2021-01-01T23:59:59.123+00:00",
        {"event_type": "double_press", "event_types": ["single_press", "double_press"]},
    )
    await hass.async_block_till_done()

    state = hass.states.get("event.remote_control")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ENTITY_ID) == ["event.button_1", "event.button_2"]
    assert not state.attributes.get(ATTR_EVENT_TYPE)
    assert state.attributes.get(ATTR_EVENT_TYPES) == unordered(
        ["single_press", "double_press"]
    )

    # State changed
    hass.states.async_set(
        "event.button_1",
        "2021-01-01T23:59:59.123+00:00",
        {"event_type": "single_press", "event_types": ["single_press", "double_press"]},
    )
    await hass.async_block_till_done()

    state = hass.states.get("event.remote_control")
    assert state is not None
    assert state.state
    assert state.attributes.get(ATTR_ENTITY_ID) == ["event.button_1", "event.button_2"]
    assert state.attributes.get(ATTR_EVENT_TYPE) == "single_press"
    assert state.attributes.get(ATTR_EVENT_TYPES) == unordered(
        ["single_press", "double_press"]
    )

    # State changed, second remote came online
    hass.states.async_set(
        "event.button_2",
        "2021-01-01T23:59:59.123+00:00",
        {"event_type": "double_press", "event_types": ["double_press", "triple_press"]},
    )
    await hass.async_block_till_done()

    # State should be single_press, because button coming online is not an event
    state = hass.states.get("event.remote_control")
    assert state is not None
    assert state.state
    assert state.attributes.get(ATTR_ENTITY_ID) == ["event.button_1", "event.button_2"]
    assert state.attributes.get(ATTR_EVENT_TYPE) == "single_press"
    assert state.attributes.get(ATTR_EVENT_TYPES) == unordered(
        ["single_press", "double_press", "triple_press"]
    )

    # State changed, now it fires an event
    hass.states.async_set(
        "event.button_2",
        "2021-01-01T23:59:59.123+00:00",
        {
            "event_type": "triple_press",
            "event_types": ["double_press", "triple_press"],
            "device_class": "doorbell",
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("event.remote_control")
    assert state is not None
    assert state.state
    assert state.attributes.get(ATTR_ENTITY_ID) == ["event.button_1", "event.button_2"]
    assert state.attributes.get(ATTR_EVENT_TYPE) == "triple_press"
    assert state.attributes.get(ATTR_EVENT_TYPES) == unordered(
        ["single_press", "double_press", "triple_press"]
    )
    assert ATTR_DEVICE_CLASS not in state.attributes

    # Mark button 1 unavailable
    hass.states.async_set("event.button_1", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get("event.remote_control")
    assert state is not None
    assert state.state
    assert state.attributes.get(ATTR_ENTITY_ID) == ["event.button_1", "event.button_2"]
    assert state.attributes.get(ATTR_EVENT_TYPE) == "triple_press"
    assert state.attributes.get(ATTR_EVENT_TYPES) == unordered(
        ["double_press", "triple_press"]
    )

    # Mark button 2 unavailable
    hass.states.async_set("event.button_2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get("event.remote_control")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    entry = entity_registry.async_get("event.remote_control")
    assert entry
    assert entry.unique_id == "unique_identifier"


async def test_device_id(hass: HomeAssistant) -> None:
    """Test for device for Group - Event."""
    group_type = "event"
    device_registry = dr.async_get(hass)

    device_config_entry = MockConfigEntry()
    device_config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=device_config_entry.entry_id,
        identifiers={("sensor", "identifier_test")},
        connections={("mac", "30:31:32:33:34:35")},
    )
    await hass.async_block_till_done()
    assert device_entry is not None
    assert device_entry.id is not None

    group_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My group",
            "entities": [f"{group_type}.one", f"{group_type}.two"],
            "group_type": group_type,
            "device_id": device_entry.id,
        },
        title="My group",
    )
    group_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(group_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    group_entity = entity_registry.async_get(f"{group_type}.my_group")
    assert group_entity is not None
    assert group_entity.device_id == device_entry.id
