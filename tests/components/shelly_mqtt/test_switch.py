"""The tests for the Shelly MQTT switch platform."""
import asyncio

from homeassistant.components import switch
from homeassistant.components.shelly_mqtt.const import CONF_MODEL, CONF_TOPIC, DOMAIN
from homeassistant.const import (
    CONF_DEVICE_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)

from .common import send_msg

from tests.async_mock import AsyncMock, MagicMock, patch
from tests.common import MockConfigEntry

MOCK_ID = "shellyswitch-AAABBB"
MOCK_SECOND_ID = MOCK_ID + "_2"
MOCK_ENTITY_ID = "switch.shellyswitch_aaabbb"
MOCK_SECOND_ENTITY_ID = "switch.shellyswitch_aaabbb_2"
MOCK_TOPIC = "shellies/shellyswitch-AAABBB/"
MOCK_SWITCH_TOPIC = "shellies/shellyswitch-AAABBB/relay/0"
MOCK_SECOND_SWITCH_TOPIC = "shellies/shellyswitch-AAABBB/relay/1"
MOCK_MODEL = "shellyswitch"
MOCK_TITLE = "Shelly 2"
MOCK_CONFIG = {CONF_DEVICE_ID: MOCK_ID, CONF_MODEL: MOCK_MODEL, CONF_TOPIC: MOCK_TOPIC}


async def _setup_shelly(hass):
    hass.config.components.add("mqtt")
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)

    first_msg_callback = asyncio.Future()
    second_msg_callback = asyncio.Future()

    def subscribed(topic, callback):
        if topic.startswith(MOCK_SWITCH_TOPIC):
            first_msg_callback.set_result(callback)
        elif topic.startswith(MOCK_SECOND_SWITCH_TOPIC):
            second_msg_callback.set_result(callback)

    with patch.object(
        hass.components.mqtt, "async_subscribe", AsyncMock(side_effect=subscribed)
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await asyncio.gather(first_msg_callback, second_msg_callback)
    return (first_msg_callback.result(), second_msg_callback.result())


def _get_entity_id(registry, unique_id):
    return registry.async_get_entity_id(switch.DOMAIN, DOMAIN, unique_id)


async def test_setup(hass):
    """Tests setup of Switch platform."""
    registry = await hass.helpers.entity_registry.async_get_registry()

    assert (_get_entity_id(registry, MOCK_ID)) is None
    assert (_get_entity_id(registry, MOCK_SECOND_ID)) is None

    await _setup_shelly(hass)

    assert (_get_entity_id(registry, MOCK_ID)) is not None
    assert (_get_entity_id(registry, MOCK_SECOND_ID)) is not None

    registry = await hass.helpers.device_registry.async_get_registry()
    device = registry.async_get_device({(DOMAIN, MOCK_ID)}, {})
    assert device is not None
    assert device.manufacturer == "Shelly"
    assert device.model == MOCK_TITLE
    assert device.name == MOCK_ID

    first_device_id = device.id

    device = registry.async_get_device({(DOMAIN, MOCK_SECOND_ID)}, {})
    assert device is not None
    assert device.manufacturer == "Shelly"
    assert device.model == MOCK_TITLE
    assert device.name == MOCK_SECOND_ID
    assert device.via_device_id == first_device_id


async def _test_controlling_switch_via_topic(hass, callback, entity_id, topic):

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    send_msg(callback, "on", topic)
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    send_msg(callback, "off", topic)
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    send_msg(callback, 30, topic + "/power")
    state = hass.states.get(entity_id)
    assert state.attributes["current_power_w"] == 30

    send_msg(callback, 120000, topic + "/energy")
    state = hass.states.get(entity_id)
    assert state.attributes["today_energy_kwh"] == 2.0


async def test_controlling_first_switch_via_topic(hass):
    """Test the controlling first switch via topic."""
    (callback, _callback) = await _setup_shelly(hass)
    await _test_controlling_switch_via_topic(
        hass, callback, MOCK_ENTITY_ID, MOCK_SWITCH_TOPIC
    )


async def test_controlling_second_switch_via_topic(hass):
    """Test the controlling second switch via topic."""
    (_callback, callback) = await _setup_shelly(hass)
    await _test_controlling_switch_via_topic(
        hass, callback, MOCK_SECOND_ENTITY_ID, MOCK_SECOND_SWITCH_TOPIC
    )


async def _call_service_and_assert_publish(hass, service, entity_id, topic, payload):
    with patch.object(hass.components.mqtt, "async_publish") as publish_mock:
        await hass.services.async_call(
            switch.DOMAIN, service, service_data={"entity_id": entity_id}, blocking=True
        )
        publish_mock.assert_called_once_with(topic, payload)


async def test_first_switch_services(hass):
    """Test turning on/off/toggling the first switch."""
    await _setup_shelly(hass)
    command_topic = MOCK_SWITCH_TOPIC + "/command"
    await _call_service_and_assert_publish(
        hass, SERVICE_TURN_ON, MOCK_ENTITY_ID, command_topic, "on"
    )
    await _call_service_and_assert_publish(
        hass, SERVICE_TURN_OFF, MOCK_ENTITY_ID, command_topic, "off"
    )
    await _call_service_and_assert_publish(
        hass, SERVICE_TOGGLE, MOCK_ENTITY_ID, command_topic, "toggle"
    )


async def test_second_switch_services(hass):
    """Test turning on/off/toggling the second switch."""
    await _setup_shelly(hass)
    command_topic = MOCK_SECOND_SWITCH_TOPIC + "/command"
    await _call_service_and_assert_publish(
        hass, SERVICE_TURN_ON, MOCK_SECOND_ENTITY_ID, command_topic, "on"
    )
    await _call_service_and_assert_publish(
        hass, SERVICE_TURN_OFF, MOCK_SECOND_ENTITY_ID, command_topic, "off"
    )
    await _call_service_and_assert_publish(
        hass, SERVICE_TOGGLE, MOCK_SECOND_ENTITY_ID, command_topic, "toggle"
    )


async def test_unsubscribe(hass):
    """Test calling unsubscribe on unload."""
    hass.config.components.add("mqtt")
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)

    unsubscribe = MagicMock()

    with patch.object(
        hass.components.mqtt, "async_subscribe", AsyncMock(return_value=unsubscribe)
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert unsubscribe.call_count == 2
