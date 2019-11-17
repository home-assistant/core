"""The tests for Humidifier device actions."""
import pytest
import voluptuous_serialize

from homeassistant.components.humidifier import DOMAIN, const, device_action
from homeassistant.setup import async_setup_component
import homeassistant.components.automation as automation
from homeassistant.helpers import device_registry, config_validation as cv

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_mock_service,
    mock_device_registry,
    mock_registry,
    async_get_device_automations,
)


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


async def test_get_actions(hass, device_reg, entity_reg):
    """Test we get the expected actions from a humidifier."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(DOMAIN, "test", "5678", device_id=device_entry.id)
    hass.states.async_set("humidifier.test_5678", const.HUMIDIFIER_MODE_DRY, {})
    expected_actions = [
        {
            "domain": DOMAIN,
            "type": "set_humidifier_mode",
            "device_id": device_entry.id,
            "entity_id": "humidifier.test_5678",
        },
        {
            "domain": DOMAIN,
            "type": "set_preset_mode",
            "device_id": device_entry.id,
            "entity_id": "humidifier.test_5678",
        },
    ]
    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert_lists_same(actions, expected_actions)


async def test_action(hass):
    """Test for actions."""
    hass.states.async_set(
        "humidifier.entity",
        const.HUMIDIFIER_MODE_DRY,
        {
            const.ATTR_HUMIDIFIER_MODES: [
                const.HUMIDIFIER_MODE_DRY,
                const.HUMIDIFIER_MODE_OFF,
            ],
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
                        "event_type": "test_event_set_humidifier_mode",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "humidifier.entity",
                        "type": "set_humidifier_mode",
                        "humidifier_mode": const.HUMIDIFIER_MODE_OFF,
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
                        "entity_id": "humidifier.entity",
                        "type": "set_preset_mode",
                        "preset_mode": const.PRESET_AWAY,
                    },
                },
            ]
        },
    )

    set_humidifier_mode_calls = async_mock_service(
        hass, "humidifier", "set_humidifier_mode"
    )
    set_preset_mode_calls = async_mock_service(hass, "humidifier", "set_preset_mode")

    hass.bus.async_fire("test_event_set_humidifier_mode")
    await hass.async_block_till_done()
    assert len(set_humidifier_mode_calls) == 1
    assert len(set_preset_mode_calls) == 0

    hass.bus.async_fire("test_event_set_preset_mode")
    await hass.async_block_till_done()
    assert len(set_humidifier_mode_calls) == 1
    assert len(set_preset_mode_calls) == 1


async def test_capabilities(hass):
    """Test getting capabilities."""
    hass.states.async_set(
        "humidifier.entity",
        const.HUMIDIFIER_MODE_DRY,
        {
            const.ATTR_HUMIDIFIER_MODES: [
                const.HUMIDIFIER_MODE_DRY,
                const.HUMIDIFIER_MODE_OFF,
            ],
            const.ATTR_PRESET_MODES: [const.PRESET_HOME, const.PRESET_AWAY],
        },
    )

    # Set HUMIDIFIER mode
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "domain": DOMAIN,
            "device_id": "abcdefgh",
            "entity_id": "humidifier.entity",
            "type": "set_humidifier_mode",
        },
    )

    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "humidifier_mode",
            "options": [("dry", "dry"), ("off", "off")],
            "required": True,
            "type": "select",
        }
    ]

    # Set preset mode
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "domain": DOMAIN,
            "device_id": "abcdefgh",
            "entity_id": "humidifier.entity",
            "type": "set_preset_mode",
        },
    )

    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "preset_mode",
            "options": [("home", "home"), ("away", "away")],
            "required": True,
            "type": "select",
        }
    ]
