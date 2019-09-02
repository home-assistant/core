"""The test for light device automation."""
import pytest

from homeassistant.components import light
from homeassistant.const import STATE_ON, STATE_OFF, CONF_PLATFORM
from homeassistant.setup import async_setup_component
import homeassistant.components.automation as automation
from homeassistant.components.device_automation import (
    _async_get_device_automations as async_get_device_automations,
)
from homeassistant.helpers import device_registry

from tests.common import (
    MockConfigEntry,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture
def calls(hass):
    """Track calls to a mock serivce."""
    return async_mock_service(hass, "test", "automation")


def _same_lists(a, b):
    if len(a) != len(b):
        return False

    for d in a:
        if d not in b:
            return False
    return True


async def test_get_actions(hass, device_reg, entity_reg):
    """Test we get the expected actions from a light."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create("light", "test", "5678", device_id=device_entry.id)
    expected_actions = [
        {
            "device": None,
            "domain": "light",
            "type": "turn_off",
            "device_id": device_entry.id,
            "entity_id": "light.test_5678",
        },
        {
            "device": None,
            "domain": "light",
            "type": "turn_on",
            "device_id": device_entry.id,
            "entity_id": "light.test_5678",
        },
        {
            "device": None,
            "domain": "light",
            "type": "toggle",
            "device_id": device_entry.id,
            "entity_id": "light.test_5678",
        },
    ]
    actions = await async_get_device_automations(
        hass, "async_get_actions", device_entry.id
    )
    assert _same_lists(actions, expected_actions)


async def test_get_conditions(hass, device_reg, entity_reg):
    """Test we get the expected conditions from a light."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create("light", "test", "5678", device_id=device_entry.id)
    expected_conditions = [
        {
            "condition": "device",
            "domain": "light",
            "type": "is_off",
            "device_id": device_entry.id,
            "entity_id": "light.test_5678",
        },
        {
            "condition": "device",
            "domain": "light",
            "type": "is_on",
            "device_id": device_entry.id,
            "entity_id": "light.test_5678",
        },
    ]
    conditions = await async_get_device_automations(
        hass, "async_get_conditions", device_entry.id
    )
    assert _same_lists(conditions, expected_conditions)


async def test_get_triggers(hass, device_reg, entity_reg):
    """Test we get the expected triggers from a light."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create("light", "test", "5678", device_id=device_entry.id)
    expected_triggers = [
        {
            "platform": "device",
            "domain": "light",
            "type": "turn_off",
            "device_id": device_entry.id,
            "entity_id": "light.test_5678",
        },
        {
            "platform": "device",
            "domain": "light",
            "type": "turn_on",
            "device_id": device_entry.id,
            "entity_id": "light.test_5678",
        },
    ]
    triggers = await async_get_device_automations(
        hass, "async_get_triggers", device_entry.id
    )
    assert _same_lists(triggers, expected_triggers)


async def test_if_fires_on_state_change(hass, calls):
    """Test for turn_on and turn_off triggers firing."""
    platform = getattr(hass.components, "test.light")

    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )

    dev1, dev2, dev3 = platform.DEVICES

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": light.DOMAIN,
                        "entity_id": dev1.entity_id,
                        "type": "turn_on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "turn_on {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                (
                                    "platform",
                                    "entity_id",
                                    "from_state.state",
                                    "to_state.state",
                                    "for",
                                )
                            )
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": light.DOMAIN,
                        "entity_id": dev1.entity_id,
                        "type": "turn_off",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "turn_off {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                (
                                    "platform",
                                    "entity_id",
                                    "from_state.state",
                                    "to_state.state",
                                    "for",
                                )
                            )
                        },
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(dev1.entity_id).state == STATE_ON
    assert len(calls) == 0

    hass.states.async_set(dev1.entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "turn_off state - {} - on - off - None".format(
        dev1.entity_id
    )

    hass.states.async_set(dev1.entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "turn_on state - {} - off - on - None".format(
        dev1.entity_id
    )


async def test_if_state(hass, calls):
    """Test for turn_on and turn_off conditions."""
    platform = getattr(hass.components, "test.light")

    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )

    dev1, dev2, dev3 = platform.DEVICES

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": "light",
                            "entity_id": dev1.entity_id,
                            "type": "is_on",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "is_on {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(("platform", "event.event_type"))
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event2"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": "light",
                            "entity_id": dev1.entity_id,
                            "type": "is_off",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "is_off {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(("platform", "event.event_type"))
                        },
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(dev1.entity_id).state == STATE_ON
    assert len(calls) == 0

    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "is_on event - test_event1"

    hass.states.async_set(dev1.entity_id, STATE_OFF)
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "is_off event - test_event2"


async def test_action(hass, calls):
    """Test for turn_on and turn_off actions."""
    platform = getattr(hass.components, "test.light")

    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )

    dev1, dev2, dev3 = platform.DEVICES

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "action": {
                        "device": None,
                        "domain": "light",
                        "entity_id": dev1.entity_id,
                        "type": "turn_off",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event2"},
                    "action": {
                        "device": None,
                        "domain": "light",
                        "entity_id": dev1.entity_id,
                        "type": "turn_on",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event3"},
                    "action": {
                        "device": None,
                        "domain": "light",
                        "entity_id": dev1.entity_id,
                        "type": "toggle",
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(dev1.entity_id).state == STATE_ON
    assert len(calls) == 0

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert hass.states.get(dev1.entity_id).state == STATE_OFF

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert hass.states.get(dev1.entity_id).state == STATE_OFF

    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert hass.states.get(dev1.entity_id).state == STATE_ON

    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert hass.states.get(dev1.entity_id).state == STATE_ON

    hass.bus.async_fire("test_event3")
    await hass.async_block_till_done()
    assert hass.states.get(dev1.entity_id).state == STATE_OFF

    hass.bus.async_fire("test_event3")
    await hass.async_block_till_done()
    assert hass.states.get(dev1.entity_id).state == STATE_ON
