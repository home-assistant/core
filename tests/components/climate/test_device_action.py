"""The tests for Climate device actions."""
import pytest
from pytest_unordered import unordered
import voluptuous_serialize

import homeassistant.components.automation as automation
from homeassistant.components.climate import DOMAIN, HVACMode, const, device_action
from homeassistant.components.device_automation import (
    DeviceAutomationType,
)
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


@pytest.mark.parametrize(
    ("set_state", "features_reg", "features_state", "expected_action_types"),
    [
        (False, 0, 0, ["set_hvac_mode"]),
        (
            False,
            const.ClimateEntityFeature.PRESET_MODE,
            0,
            ["set_hvac_mode", "set_preset_mode"],
        ),
        (True, 0, 0, ["set_hvac_mode"]),
        (
            True,
            0,
            const.ClimateEntityFeature.PRESET_MODE,
            ["set_hvac_mode", "set_preset_mode"],
        ),
    ],
)
async def test_get_actions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    set_state,
    features_reg,
    features_state,
    expected_action_types,
) -> None:
    """Test we get the expected actions from a climate."""
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

    expected_actions = []

    expected_actions += [
        {
            "domain": DOMAIN,
            "type": action,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        }
        for action in expected_action_types
    ]

    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert actions == unordered(expected_actions)


@pytest.mark.parametrize(
    ("hidden_by", "entity_category"),
    (
        (RegistryEntryHider.INTEGRATION, None),
        (RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ),
)
async def test_get_actions_hidden_auxiliary(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hidden_by,
    entity_category,
) -> None:
    """Test we get the expected actions from a hidden or auxiliary entity."""
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
        supported_features=0,
    )
    expected_actions = []
    expected_actions += [
        {
            "domain": DOMAIN,
            "type": action,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": True},
        }
        for action in ["set_hvac_mode"]
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert actions == unordered(expected_actions)


async def test_action(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
    """Test for actions."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

    hass.states.async_set(
        entry.entity_id,
        HVACMode.COOL,
        {
            const.ATTR_HVAC_MODES: [HVACMode.COOL, HVACMode.OFF],
            const.ATTR_PRESET_MODES: [const.PRESET_HOME, const.PRESET_AWAY],
        },
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_hvac_mode",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": entry.id,
                        "type": "set_hvac_mode",
                        "hvac_mode": HVACMode.OFF,
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_preset_mode",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": entry.id,
                        "type": "set_preset_mode",
                        "preset_mode": const.PRESET_AWAY,
                    },
                },
            ]
        },
    )

    set_hvac_mode_calls = async_mock_service(hass, "climate", "set_hvac_mode")
    set_preset_mode_calls = async_mock_service(hass, "climate", "set_preset_mode")

    hass.bus.async_fire("test_event_set_hvac_mode")
    await hass.async_block_till_done()
    assert len(set_hvac_mode_calls) == 1
    assert len(set_preset_mode_calls) == 0

    hass.bus.async_fire("test_event_set_preset_mode")
    await hass.async_block_till_done()
    assert len(set_hvac_mode_calls) == 1
    assert len(set_preset_mode_calls) == 1

    assert set_hvac_mode_calls[0].domain == DOMAIN
    assert set_hvac_mode_calls[0].service == "set_hvac_mode"
    assert set_hvac_mode_calls[0].data == {
        "entity_id": entry.entity_id,
        "hvac_mode": const.HVAC_MODE_OFF,
    }
    assert set_preset_mode_calls[0].domain == DOMAIN
    assert set_preset_mode_calls[0].service == "set_preset_mode"
    assert set_preset_mode_calls[0].data == {
        "entity_id": entry.entity_id,
        "preset_mode": const.PRESET_AWAY,
    }


async def test_action_legacy(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test for actions."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

    hass.states.async_set(
        entry.entity_id,
        HVACMode.COOL,
        {
            const.ATTR_HVAC_MODES: [HVACMode.COOL, HVACMode.OFF],
            const.ATTR_PRESET_MODES: [const.PRESET_HOME, const.PRESET_AWAY],
        },
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_hvac_mode",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": entry.entity_id,
                        "type": "set_hvac_mode",
                        "hvac_mode": HVACMode.OFF,
                    },
                },
            ]
        },
    )

    set_hvac_mode_calls = async_mock_service(hass, "climate", "set_hvac_mode")

    hass.bus.async_fire("test_event_set_hvac_mode")
    await hass.async_block_till_done()
    assert len(set_hvac_mode_calls) == 1

    assert set_hvac_mode_calls[0].domain == DOMAIN
    assert set_hvac_mode_calls[0].service == "set_hvac_mode"
    assert set_hvac_mode_calls[0].data == {
        "entity_id": entry.entity_id,
        "hvac_mode": const.HVAC_MODE_OFF,
    }


@pytest.mark.parametrize(
    (
        "set_state",
        "capabilities_reg",
        "capabilities_state",
        "action",
        "expected_capabilities",
    ),
    [
        (
            False,
            {const.ATTR_HVAC_MODES: [HVACMode.COOL, HVACMode.OFF]},
            {},
            "set_hvac_mode",
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
            "set_preset_mode",
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
            "set_hvac_mode",
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
            "set_preset_mode",
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
    action,
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
            f"{DOMAIN}.test_5678",
            HVACMode.COOL,
            capabilities_state,
        )

    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "domain": DOMAIN,
            "device_id": "abcdefgh",
            "entity_id": entity_entry.id,
            "type": action,
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
        "action",
        "expected_capabilities",
    ),
    [
        (
            False,
            {const.ATTR_HVAC_MODES: [HVACMode.COOL, HVACMode.OFF]},
            {},
            "set_hvac_mode",
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
            "set_preset_mode",
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
            "set_hvac_mode",
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
            "set_preset_mode",
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
    action,
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
            f"{DOMAIN}.test_5678",
            HVACMode.COOL,
            capabilities_state,
        )

    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "domain": DOMAIN,
            "device_id": "abcdefgh",
            "entity_id": entity_entry.entity_id,
            "type": action,
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
    ("action", "capability_name"),
    [("set_hvac_mode", "hvac_mode"), ("set_preset_mode", "preset_mode")],
)
async def test_capabilities_missing_entity(
    hass: HomeAssistant, action, capability_name
) -> None:
    """Test getting capabilities."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)

    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "domain": DOMAIN,
            "device_id": "abcdefgh",
            "entity_id": f"{DOMAIN}.test_5678",
            "type": action,
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
