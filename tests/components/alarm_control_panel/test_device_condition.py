"""The tests for Alarm control panel device conditions."""
import pytest

from homeassistant.components.alarm_control_panel import DOMAIN, const
import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_VACATION,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_registry import RegistryEntryHider
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


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


@pytest.mark.parametrize(
    "set_state,features_reg,features_state,expected_condition_types",
    [
        (False, 0, 0, []),
        (False, const.AlarmControlPanelEntityFeature.ARM_AWAY, 0, ["is_armed_away"]),
        (False, const.AlarmControlPanelEntityFeature.ARM_HOME, 0, ["is_armed_home"]),
        (False, const.AlarmControlPanelEntityFeature.ARM_NIGHT, 0, ["is_armed_night"]),
        (
            False,
            const.AlarmControlPanelEntityFeature.ARM_VACATION,
            0,
            ["is_armed_vacation"],
        ),
        (
            False,
            const.AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS,
            0,
            ["is_armed_custom_bypass"],
        ),
        (True, 0, 0, []),
        (True, 0, const.AlarmControlPanelEntityFeature.ARM_AWAY, ["is_armed_away"]),
        (True, 0, const.AlarmControlPanelEntityFeature.ARM_HOME, ["is_armed_home"]),
        (True, 0, const.AlarmControlPanelEntityFeature.ARM_NIGHT, ["is_armed_night"]),
        (
            True,
            0,
            const.AlarmControlPanelEntityFeature.ARM_VACATION,
            ["is_armed_vacation"],
        ),
        (
            True,
            0,
            const.AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS,
            ["is_armed_custom_bypass"],
        ),
    ],
)
async def test_get_conditions(
    hass,
    device_reg,
    entity_reg,
    set_state,
    features_reg,
    features_state,
    expected_condition_types,
):
    """Test we get the expected conditions from a alarm_control_panel."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN,
        "test",
        "5678",
        device_id=device_entry.id,
        supported_features=features_reg,
    )
    if set_state:
        hass.states.async_set(
            "alarm_control_panel.test_5678",
            "attributes",
            {"supported_features": features_state},
        )
    expected_conditions = []
    basic_condition_types = ["is_disarmed", "is_triggered"]
    expected_conditions += [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": condition,
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
            "metadata": {"secondary": False},
        }
        for condition in basic_condition_types
    ]
    expected_conditions += [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": condition,
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
            "metadata": {"secondary": False},
        }
        for condition in expected_condition_types
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert_lists_same(conditions, expected_conditions)


@pytest.mark.parametrize(
    "hidden_by,entity_category",
    (
        (RegistryEntryHider.INTEGRATION, None),
        (RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ),
)
async def test_get_conditions_hidden_auxiliary(
    hass,
    device_reg,
    entity_reg,
    hidden_by,
    entity_category,
):
    """Test we get the expected conditions from a hidden or auxiliary entity."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN,
        "test",
        "5678",
        device_id=device_entry.id,
        entity_category=entity_category,
        hidden_by=hidden_by,
    )
    expected_conditions = [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": condition,
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
            "metadata": {"secondary": True},
        }
        for condition in ["is_disarmed", "is_triggered"]
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert_lists_same(conditions, expected_conditions)


async def test_if_state(hass, calls):
    """Test for all conditions."""
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
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": "alarm_control_panel.entity",
                            "type": "is_triggered",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "is_triggered - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event2"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": "alarm_control_panel.entity",
                            "type": "is_disarmed",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "is_disarmed - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event3"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": "alarm_control_panel.entity",
                            "type": "is_armed_home",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "is_armed_home - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event4"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": "alarm_control_panel.entity",
                            "type": "is_armed_away",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "is_armed_away - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event5"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": "alarm_control_panel.entity",
                            "type": "is_armed_night",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "is_armed_night - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event6"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": "alarm_control_panel.entity",
                            "type": "is_armed_vacation",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "is_armed_vacation - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event7"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": "alarm_control_panel.entity",
                            "type": "is_armed_custom_bypass",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "is_armed_custom_bypass - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
            ]
        },
    )
    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_TRIGGERED)
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    hass.bus.async_fire("test_event4")
    hass.bus.async_fire("test_event5")
    hass.bus.async_fire("test_event6")
    hass.bus.async_fire("test_event7")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "is_triggered - event - test_event1"

    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_DISARMED)
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    hass.bus.async_fire("test_event4")
    hass.bus.async_fire("test_event5")
    hass.bus.async_fire("test_event6")
    hass.bus.async_fire("test_event7")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "is_disarmed - event - test_event2"

    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_ARMED_HOME)
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    hass.bus.async_fire("test_event4")
    hass.bus.async_fire("test_event5")
    hass.bus.async_fire("test_event6")
    hass.bus.async_fire("test_event7")
    await hass.async_block_till_done()
    assert len(calls) == 3
    assert calls[2].data["some"] == "is_armed_home - event - test_event3"

    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_ARMED_AWAY)
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    hass.bus.async_fire("test_event4")
    hass.bus.async_fire("test_event5")
    hass.bus.async_fire("test_event6")
    hass.bus.async_fire("test_event7")
    await hass.async_block_till_done()
    assert len(calls) == 4
    assert calls[3].data["some"] == "is_armed_away - event - test_event4"

    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_ARMED_NIGHT)
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    hass.bus.async_fire("test_event4")
    hass.bus.async_fire("test_event5")
    hass.bus.async_fire("test_event6")
    hass.bus.async_fire("test_event7")
    await hass.async_block_till_done()
    assert len(calls) == 5
    assert calls[4].data["some"] == "is_armed_night - event - test_event5"

    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_ARMED_VACATION)
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    hass.bus.async_fire("test_event4")
    hass.bus.async_fire("test_event5")
    hass.bus.async_fire("test_event6")
    hass.bus.async_fire("test_event7")
    await hass.async_block_till_done()
    assert len(calls) == 6
    assert calls[5].data["some"] == "is_armed_vacation - event - test_event6"

    hass.states.async_set("alarm_control_panel.entity", STATE_ALARM_ARMED_CUSTOM_BYPASS)
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    hass.bus.async_fire("test_event4")
    hass.bus.async_fire("test_event5")
    hass.bus.async_fire("test_event6")
    hass.bus.async_fire("test_event7")
    await hass.async_block_till_done()
    assert len(calls) == 7
    assert calls[6].data["some"] == "is_armed_custom_bypass - event - test_event7"
