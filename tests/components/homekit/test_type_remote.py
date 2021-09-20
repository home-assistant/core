"""Test different accessory types: Remotes."""

from homeassistant.components.homekit.const import (
    ATTR_KEY_NAME,
    ATTR_VALUE,
    EVENT_HOMEKIT_TV_REMOTE_KEY_PRESSED,
    KEY_ARROW_RIGHT,
)
from homeassistant.components.homekit.type_remotes import ActivityRemote
from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_ACTIVITY_LIST,
    ATTR_CURRENT_ACTIVITY,
    DOMAIN,
    SUPPORT_ACTIVITY,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_STANDBY,
)

from tests.common import async_mock_service


async def test_activity_remote(hass, hk_driver, events, caplog):
    """Test if remote accessory and HA are updated accordingly."""
    entity_id = "remote.harmony"
    hass.states.async_set(
        entity_id,
        None,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_ACTIVITY,
            ATTR_CURRENT_ACTIVITY: "Apple TV",
            ATTR_ACTIVITY_LIST: ["TV", "Apple TV"],
        },
    )
    await hass.async_block_till_done()
    acc = ActivityRemote(hass, hk_driver, "ActivityRemote", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 31  # Television

    assert acc.char_active.value == 0
    assert acc.char_remote_key.value == 0
    assert acc.char_input_source.value == 1

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_ACTIVITY,
            ATTR_CURRENT_ACTIVITY: "Apple TV",
            ATTR_ACTIVITY_LIST: ["TV", "Apple TV"],
        },
    )
    await hass.async_block_till_done()
    assert acc.char_active.value == 1

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert acc.char_active.value == 1

    hass.states.async_set(entity_id, STATE_STANDBY)
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_ACTIVITY,
            ATTR_CURRENT_ACTIVITY: "TV",
            ATTR_ACTIVITY_LIST: ["TV", "Apple TV"],
        },
    )
    await hass.async_block_till_done()
    assert acc.char_input_source.value == 0

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_ACTIVITY,
            ATTR_CURRENT_ACTIVITY: "Apple TV",
            ATTR_ACTIVITY_LIST: ["TV", "Apple TV"],
        },
    )
    await hass.async_block_till_done()
    assert acc.char_input_source.value == 1

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, "turn_on")
    call_turn_off = async_mock_service(hass, DOMAIN, "turn_off")

    acc.char_active.client_update_value(1)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_active.client_update_value(0)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_input_source.client_update_value(1)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[1].data[ATTR_ACTIVITY] == "Apple TV"
    assert len(events) == 3
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_input_source.client_update_value(0)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[2].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[2].data[ATTR_ACTIVITY] == "TV"
    assert len(events) == 4
    assert events[-1].data[ATTR_VALUE] is None

    events = []

    def listener(event):
        events.append(event)

    hass.bus.async_listen(EVENT_HOMEKIT_TV_REMOTE_KEY_PRESSED, listener)

    acc.char_remote_key.client_update_value(20)
    await hass.async_block_till_done()

    acc.char_remote_key.client_update_value(7)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[ATTR_KEY_NAME] == KEY_ARROW_RIGHT
