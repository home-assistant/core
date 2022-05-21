"""The tests for Humidifier device conditions."""
import pytest
import voluptuous_serialize

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.humidifier import DOMAIN, const, device_condition
from homeassistant.const import ATTR_MODE, STATE_OFF, STATE_ON
from homeassistant.helpers import config_validation as cv, device_registry
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
        (False, const.HumidifierEntityFeature.MODES, 0, ["is_mode"]),
        (True, 0, 0, []),
        (True, 0, const.HumidifierEntityFeature.MODES, ["is_mode"]),
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
    """Test we get the expected conditions from a humidifier."""
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
            f"{DOMAIN}.test_5678", "attributes", {"supported_features": features_state}
        )
    expected_conditions = []
    basic_condition_types = ["is_on", "is_off"]
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
        for condition in ["is_off", "is_on"]
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert_lists_same(conditions, expected_conditions)


async def test_if_state(hass, calls):
    """Test for turn_on and turn_off conditions."""
    hass.states.async_set("humidifier.entity", STATE_ON, {ATTR_MODE: const.MODE_AWAY})

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
                            "entity_id": "humidifier.entity",
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
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": "humidifier.entity",
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
                {
                    "trigger": {"platform": "event", "event_type": "test_event3"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": "humidifier.entity",
                            "type": "is_mode",
                            "mode": "away",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "is_mode - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get("humidifier.entity").state == STATE_ON
    assert len(calls) == 0

    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "is_on event - test_event1"

    hass.states.async_set("humidifier.entity", STATE_OFF)
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "is_off event - test_event2"

    hass.states.async_set("humidifier.entity", STATE_ON, {ATTR_MODE: const.MODE_AWAY})

    hass.bus.async_fire("test_event3")
    await hass.async_block_till_done()

    assert len(calls) == 3
    assert calls[2].data["some"] == "is_mode - event - test_event3"

    hass.states.async_set("humidifier.entity", STATE_ON, {ATTR_MODE: const.MODE_HOME})

    # Should not fire
    hass.bus.async_fire("test_event3")
    await hass.async_block_till_done()
    assert len(calls) == 3


@pytest.mark.parametrize(
    "set_state,capabilities_reg,capabilities_state,condition,expected_capabilities",
    [
        (
            False,
            {},
            {},
            "is_mode",
            [
                {
                    "name": "mode",
                    "options": [],
                    "required": True,
                    "type": "select",
                }
            ],
        ),
        (
            False,
            {const.ATTR_AVAILABLE_MODES: [const.MODE_HOME, const.MODE_AWAY]},
            {},
            "is_mode",
            [
                {
                    "name": "mode",
                    "options": [("home", "home"), ("away", "away")],
                    "required": True,
                    "type": "select",
                }
            ],
        ),
        (
            False,
            {},
            {},
            "is_off",
            [
                {
                    "name": "for",
                    "optional": True,
                    "type": "positive_time_period_dict",
                }
            ],
        ),
        (
            False,
            {},
            {},
            "is_on",
            [
                {
                    "name": "for",
                    "optional": True,
                    "type": "positive_time_period_dict",
                }
            ],
        ),
        (
            True,
            {},
            {},
            "is_mode",
            [
                {
                    "name": "mode",
                    "options": [],
                    "required": True,
                    "type": "select",
                }
            ],
        ),
        (
            True,
            {},
            {const.ATTR_AVAILABLE_MODES: [const.MODE_HOME, const.MODE_AWAY]},
            "is_mode",
            [
                {
                    "name": "mode",
                    "options": [("home", "home"), ("away", "away")],
                    "required": True,
                    "type": "select",
                }
            ],
        ),
        (
            True,
            {},
            {},
            "is_off",
            [
                {
                    "name": "for",
                    "optional": True,
                    "type": "positive_time_period_dict",
                }
            ],
        ),
        (
            True,
            {},
            {},
            "is_on",
            [
                {
                    "name": "for",
                    "optional": True,
                    "type": "positive_time_period_dict",
                }
            ],
        ),
    ],
)
async def test_capabilities(
    hass,
    device_reg,
    entity_reg,
    set_state,
    capabilities_reg,
    capabilities_state,
    condition,
    expected_capabilities,
):
    """Test getting capabilities."""
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
        capabilities=capabilities_reg,
    )
    if set_state:
        hass.states.async_set(
            f"{DOMAIN}.test_5678",
            STATE_ON,
            capabilities_state,
        )

    capabilities = await device_condition.async_get_condition_capabilities(
        hass,
        {
            "domain": DOMAIN,
            "device_id": "abcdefgh",
            "entity_id": f"{DOMAIN}.test_5678",
            "type": condition,
        },
    )

    assert capabilities and "extra_fields" in capabilities

    assert (
        voluptuous_serialize.convert(
            capabilities["extra_fields"], custom_serializer=cv.custom_serializer
        )
        == expected_capabilities
    )


@pytest.mark.parametrize(
    "condition,capability_name,extra",
    [
        ("is_mode", "mode", {"type": "select", "options": []}),
    ],
)
async def test_capabilities_missing_entity(
    hass, device_reg, entity_reg, condition, capability_name, extra
):
    """Test getting capabilities."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)

    capabilities = await device_condition.async_get_condition_capabilities(
        hass,
        {
            "domain": DOMAIN,
            "device_id": "abcdefgh",
            "entity_id": f"{DOMAIN}.test_5678",
            "type": condition,
        },
    )

    expected_capabilities = [
        {
            "name": capability_name,
            "required": True,
            **extra,
        }
    ]

    assert capabilities and "extra_fields" in capabilities

    assert (
        voluptuous_serialize.convert(
            capabilities["extra_fields"], custom_serializer=cv.custom_serializer
        )
        == expected_capabilities
    )
