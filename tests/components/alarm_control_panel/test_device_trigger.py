"""The tests for Alarm control panel device triggers."""
import pytest

from homeassistant.components.alarm_control_panel import DOMAIN
import homeassistant.components.automation as automation
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
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
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(hass, device_reg, entity_reg):
    """Test we get the expected triggers from a alarm_control_panel."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(DOMAIN, "test", "5678", device_id=device_entry.id)
    hass.states.async_set(
        "alarm_control_panel.test_5678", "attributes", {"supported_features": 15}
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "disarmed",
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "triggered",
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "arming",
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "armed_home",
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "armed_away",
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "armed_night",
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
        },
    ]
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, expected_triggers)


async def test_if_fires_on_state_change(hass, calls):
    """Test for turn_on and turn_off triggers firing."""
    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_PENDING)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "alarm_control_panel.entity",
                        "type": "triggered",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "triggered - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "alarm_control_panel.entity",
                        "type": "disarmed",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "disarmed - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "alarm_control_panel.entity",
                        "type": "armed_home",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "armed_home - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "alarm_control_panel.entity",
                        "type": "armed_away",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "armed_away - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "alarm_control_panel.entity",
                        "type": "armed_night",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "armed_night - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Fake that the entity is triggered.
    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_TRIGGERED)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert (
        calls[0].data["some"]
        == "triggered - device - alarm_control_panel.entity - pending - triggered - None"
    )

    # Fake that the entity is disarmed.
    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_DISARMED)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert (
        calls[1].data["some"]
        == "disarmed - device - alarm_control_panel.entity - triggered - disarmed - None"
    )

    # Fake that the entity is armed home.
    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_PENDING)
    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_ARMED_HOME)
    await hass.async_block_till_done()
    assert len(calls) == 3
    assert (
        calls[2].data["some"]
        == "armed_home - device - alarm_control_panel.entity - pending - armed_home - None"
    )

    # Fake that the entity is armed away.
    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_PENDING)
    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_ARMED_AWAY)
    await hass.async_block_till_done()
    assert len(calls) == 4
    assert (
        calls[3].data["some"]
        == "armed_away - device - alarm_control_panel.entity - pending - armed_away - None"
    )

    # Fake that the entity is armed night.
    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_PENDING)
    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_ARMED_NIGHT)
    await hass.async_block_till_done()
    assert len(calls) == 5
    assert (
        calls[4].data["some"]
        == "armed_night - device - alarm_control_panel.entity - pending - armed_night - None"
    )
