"""The tests for Humidifier device conditions."""

import pytest
from pytest_unordered import unordered
import voluptuous_serialize

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.humidifier import DOMAIN, const, device_condition
from homeassistant.const import ATTR_MODE, STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.entity_registry import RegistryEntryHider
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    async_get_device_automations,
    async_mock_service,
)


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.mark.parametrize(
    ("set_state", "features_reg", "features_state", "expected_condition_types"),
    [
        (False, 0, 0, []),
        (False, const.HumidifierEntityFeature.MODES, 0, ["is_mode"]),
        (True, 0, 0, []),
        (True, 0, const.HumidifierEntityFeature.MODES, ["is_mode"]),
    ],
)
async def test_get_conditions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    set_state,
    features_reg,
    features_state,
    expected_condition_types,
) -> None:
    """Test we get the expected conditions from a humidifier."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
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
            "entity_id": entity_entry.id,
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
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        }
        for condition in expected_condition_types
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert conditions == unordered(expected_conditions)


@pytest.mark.parametrize(
    ("hidden_by", "entity_category"),
    [
        (RegistryEntryHider.INTEGRATION, None),
        (RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ],
)
async def test_get_conditions_hidden_auxiliary(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hidden_by,
    entity_category,
) -> None:
    """Test we get the expected conditions from a hidden or auxiliary entity."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
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
            "entity_id": entity_entry.id,
            "metadata": {"secondary": True},
        }
        for condition in ["is_off", "is_on"]
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert conditions == unordered(expected_conditions)


async def test_if_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    calls,
) -> None:
    """Test for turn_on and turn_off conditions."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    hass.states.async_set(entry.entity_id, STATE_ON, {ATTR_MODE: const.MODE_AWAY})

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
                            "device_id": device_entry.id,
                            "entity_id": entry.id,
                            "type": "is_on",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "is_on {{ trigger.platform }}"
                                " - {{ trigger.event.event_type }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event2"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device_entry.id,
                            "entity_id": entry.id,
                            "type": "is_off",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "is_off {{ trigger.platform }}"
                                " - {{ trigger.event.event_type }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event3"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device_entry.id,
                            "entity_id": entry.id,
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
    assert len(calls) == 0

    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "is_on event - test_event1"

    hass.states.async_set(entry.entity_id, STATE_OFF)
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "is_off event - test_event2"

    hass.states.async_set(entry.entity_id, STATE_ON, {ATTR_MODE: const.MODE_AWAY})

    hass.bus.async_fire("test_event3")
    await hass.async_block_till_done()

    assert len(calls) == 3
    assert calls[2].data["some"] == "is_mode - event - test_event3"

    hass.states.async_set(entry.entity_id, STATE_ON, {ATTR_MODE: const.MODE_HOME})

    # Should not fire
    hass.bus.async_fire("test_event3")
    await hass.async_block_till_done()
    assert len(calls) == 3


async def test_if_state_legacy(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    calls,
) -> None:
    """Test for turn_on and turn_off conditions."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    hass.states.async_set(entry.entity_id, STATE_ON, {ATTR_MODE: const.MODE_AWAY})

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
                            "device_id": device_entry.id,
                            "entity_id": entry.entity_id,
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
    assert len(calls) == 0

    hass.states.async_set(entry.entity_id, STATE_ON, {ATTR_MODE: const.MODE_AWAY})

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "is_mode - event - test_event1"


@pytest.mark.parametrize(
    (
        "set_state",
        "capabilities_reg",
        "capabilities_state",
        "condition",
        "expected_capabilities",
    ),
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
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    set_state,
    capabilities_reg,
    capabilities_state,
    condition,
    expected_capabilities,
) -> None:
    """Test getting capabilities."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        "5678",
        device_id=device_entry.id,
        capabilities=capabilities_reg,
    )
    if set_state:
        hass.states.async_set(
            entity_entry.entity_id,
            STATE_ON,
            capabilities_state,
        )

    capabilities = await device_condition.async_get_condition_capabilities(
        hass,
        {
            "domain": DOMAIN,
            "device_id": "abcdefgh",
            "entity_id": entity_entry.id,
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
    (
        "set_state",
        "capabilities_reg",
        "capabilities_state",
        "condition",
        "expected_capabilities",
    ),
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
async def test_capabilities_legacy(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    set_state,
    capabilities_reg,
    capabilities_state,
    condition,
    expected_capabilities,
) -> None:
    """Test getting capabilities."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        "5678",
        device_id=device_entry.id,
        capabilities=capabilities_reg,
    )
    if set_state:
        hass.states.async_set(
            entity_entry.entity_id,
            STATE_ON,
            capabilities_state,
        )

    capabilities = await device_condition.async_get_condition_capabilities(
        hass,
        {
            "domain": DOMAIN,
            "device_id": "abcdefgh",
            "entity_id": entity_entry.entity_id,
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
    ("condition", "capability_name", "extra"),
    [
        ("is_mode", "mode", {"type": "select", "options": []}),
    ],
)
async def test_capabilities_missing_entity(
    hass: HomeAssistant, condition, capability_name, extra
) -> None:
    """Test getting capabilities."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)

    capabilities = await device_condition.async_get_condition_capabilities(
        hass,
        {
            "domain": DOMAIN,
            "device_id": "abcdefgh",
            "entity_id": "0123456789",
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
