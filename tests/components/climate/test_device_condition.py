"""The tests for Climate device conditions."""
import pytest
from pytest_unordered import unordered
import voluptuous_serialize

import homeassistant.components.automation as automation
from homeassistant.components.climate import DOMAIN, HVACMode, const, device_condition
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.const import EntityCategory
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
        (False, 0, 0, ["is_hvac_mode"]),
        (
            False,
            const.ClimateEntityFeature.PRESET_MODE,
            0,
            ["is_hvac_mode", "is_preset_mode"],
        ),
        (True, 0, 0, ["is_hvac_mode"]),
        (
            True,
            0,
            const.ClimateEntityFeature.PRESET_MODE,
            ["is_hvac_mode", "is_preset_mode"],
        ),
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
    """Test we get the expected conditions from a climate."""
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
    (
        (RegistryEntryHider.INTEGRATION, None),
        (RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ),
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
        for condition in ["is_hvac_mode"]
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert conditions == unordered(expected_conditions)


async def test_if_state(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, calls
) -> None:
    """Test for turn_on and turn_off conditions."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

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
                            "entity_id": entry.id,
                            "type": "is_hvac_mode",
                            "hvac_mode": "cool",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "is_hvac_mode - {{ trigger.platform }} "
                                "- {{ trigger.event.event_type }}"
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
                            "device_id": "",
                            "entity_id": entry.id,
                            "type": "is_preset_mode",
                            "preset_mode": "away",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "is_preset_mode - {{ trigger.platform }} "
                                "- {{ trigger.event.event_type }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Should not fire, entity doesn't exist yet
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set(
        entry.entity_id,
        HVACMode.COOL,
        {
            const.ATTR_PRESET_MODE: const.PRESET_AWAY,
        },
    )

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "is_hvac_mode - event - test_event1"

    hass.states.async_set(
        entry.entity_id,
        HVACMode.AUTO,
        {
            const.ATTR_PRESET_MODE: const.PRESET_AWAY,
        },
    )

    # Should not fire
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()

    assert len(calls) == 2
    assert calls[1].data["some"] == "is_preset_mode - event - test_event2"

    hass.states.async_set(
        entry.entity_id,
        HVACMode.AUTO,
        {
            const.ATTR_PRESET_MODE: const.PRESET_HOME,
        },
    )

    # Should not fire
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_if_state_legacy(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, calls
) -> None:
    """Test for turn_on and turn_off conditions."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

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
                            "entity_id": entry.entity_id,
                            "type": "is_hvac_mode",
                            "hvac_mode": "cool",
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "is_hvac_mode - {{ trigger.platform }} "
                                "- {{ trigger.event.event_type }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    hass.states.async_set(
        entry.entity_id,
        HVACMode.COOL,
    )

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "is_hvac_mode - event - test_event1"


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
            {const.ATTR_HVAC_MODES: [HVACMode.COOL, HVACMode.OFF]},
            {},
            "is_hvac_mode",
            [
                {
                    "name": "hvac_mode",
                    "options": [("cool", "cool"), ("off", "off")],
                    "required": True,
                    "type": "select",
                }
            ],
        ),
        (
            False,
            {const.ATTR_PRESET_MODES: [const.PRESET_HOME, const.PRESET_AWAY]},
            {},
            "is_preset_mode",
            [
                {
                    "name": "preset_mode",
                    "options": [("home", "home"), ("away", "away")],
                    "required": True,
                    "type": "select",
                }
            ],
        ),
        (
            True,
            {},
            {const.ATTR_HVAC_MODES: [HVACMode.COOL, HVACMode.OFF]},
            "is_hvac_mode",
            [
                {
                    "name": "hvac_mode",
                    "options": [("cool", "cool"), ("off", "off")],
                    "required": True,
                    "type": "select",
                }
            ],
        ),
        (
            True,
            {},
            {const.ATTR_PRESET_MODES: [const.PRESET_HOME, const.PRESET_AWAY]},
            "is_preset_mode",
            [
                {
                    "name": "preset_mode",
                    "options": [("home", "home"), ("away", "away")],
                    "required": True,
                    "type": "select",
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
            HVACMode.COOL,
            capabilities_state,
        )

    capabilities = await device_condition.async_get_condition_capabilities(
        hass,
        {
            "condition": "device",
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
            {const.ATTR_HVAC_MODES: [HVACMode.COOL, HVACMode.OFF]},
            {},
            "is_hvac_mode",
            [
                {
                    "name": "hvac_mode",
                    "options": [("cool", "cool"), ("off", "off")],
                    "required": True,
                    "type": "select",
                }
            ],
        ),
        (
            False,
            {const.ATTR_PRESET_MODES: [const.PRESET_HOME, const.PRESET_AWAY]},
            {},
            "is_preset_mode",
            [
                {
                    "name": "preset_mode",
                    "options": [("home", "home"), ("away", "away")],
                    "required": True,
                    "type": "select",
                }
            ],
        ),
        (
            True,
            {},
            {const.ATTR_HVAC_MODES: [HVACMode.COOL, HVACMode.OFF]},
            "is_hvac_mode",
            [
                {
                    "name": "hvac_mode",
                    "options": [("cool", "cool"), ("off", "off")],
                    "required": True,
                    "type": "select",
                }
            ],
        ),
        (
            True,
            {},
            {const.ATTR_PRESET_MODES: [const.PRESET_HOME, const.PRESET_AWAY]},
            "is_preset_mode",
            [
                {
                    "name": "preset_mode",
                    "options": [("home", "home"), ("away", "away")],
                    "required": True,
                    "type": "select",
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
            HVACMode.COOL,
            capabilities_state,
        )

    capabilities = await device_condition.async_get_condition_capabilities(
        hass,
        {
            "condition": "device",
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
    ("condition", "capability_name"),
    [("is_hvac_mode", "hvac_mode"), ("is_preset_mode", "preset_mode")],
)
async def test_capabilities_missing_entity(
    hass: HomeAssistant, condition, capability_name
) -> None:
    """Test getting capabilities."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)

    capabilities = await device_condition.async_get_condition_capabilities(
        hass,
        {
            "condition": "device",
            "domain": DOMAIN,
            "device_id": "abcdefgh",
            "entity_id": "01234567890123456789012345678901",
            "type": condition,
        },
    )

    expected_capabilities = [
        {
            "name": capability_name,
            "options": [],
            "required": True,
            "type": "select",
        }
    ]

    assert capabilities and "extra_fields" in capabilities

    assert (
        voluptuous_serialize.convert(
            capabilities["extra_fields"], custom_serializer=cv.custom_serializer
        )
        == expected_capabilities
    )
