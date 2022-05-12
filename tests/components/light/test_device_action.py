"""The test for light device automation."""
import pytest

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.light import (
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN,
    FLASH_LONG,
    FLASH_SHORT,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.const import CONF_PLATFORM, STATE_OFF, STATE_ON
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_registry import RegistryEntryHider
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automation_capabilities,
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


async def test_get_actions(hass, device_reg, entity_reg):
    """Test we get the expected actions from a light."""
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
        supported_features=LightEntityFeature.FLASH,
        capabilities={"supported_color_modes": ["brightness"]},
    )
    expected_actions = []
    expected_actions += [
        {
            "domain": DOMAIN,
            "type": action,
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
            "metadata": {"secondary": False},
        }
        for action in [
            "turn_off",
            "turn_on",
            "toggle",
            "brightness_decrease",
            "brightness_increase",
            "flash",
        ]
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert_lists_same(actions, expected_actions)


@pytest.mark.parametrize(
    "hidden_by,entity_category",
    (
        (RegistryEntryHider.INTEGRATION, None),
        (RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ),
)
async def test_get_actions_hidden_auxiliary(
    hass,
    device_reg,
    entity_reg,
    hidden_by,
    entity_category,
):
    """Test we get the expected actions from a hidden or auxiliary entity."""
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
        supported_features=0,
        capabilities={"supported_color_modes": ["onoff"]},
    )
    expected_actions = []
    expected_actions += [
        {
            "domain": DOMAIN,
            "type": action,
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
            "metadata": {"secondary": True},
        }
        for action in ["turn_on", "turn_off", "toggle"]
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert_lists_same(actions, expected_actions)


async def test_get_action_capabilities(hass, device_reg, entity_reg):
    """Test we get the expected capabilities from a light action."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    # Test with entity without optional capabilities
    entity_id = entity_reg.async_get_or_create(
        DOMAIN,
        "test",
        "5678",
        device_id=device_entry.id,
    ).entity_id
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert len(actions) == 3
    action_types = {action["type"] for action in actions}
    assert action_types == {"turn_on", "toggle", "turn_off"}
    for action in actions:
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.ACTION, action
        )
        assert capabilities == {"extra_fields": []}

    # Test without entity
    entity_reg.async_remove(entity_id)
    for action in actions:
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.ACTION, action
        )
        assert capabilities == {"extra_fields": []}


@pytest.mark.parametrize(
    "set_state,expected_actions,supported_features_reg,supported_features_state,capabilities_reg,attributes_state,expected_capabilities",
    [
        (
            False,
            {
                "turn_on",
                "toggle",
                "turn_off",
                "brightness_increase",
                "brightness_decrease",
            },
            0,
            0,
            {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS]},
            {},
            {
                "turn_on": [
                    {
                        "name": "brightness_pct",
                        "optional": True,
                        "type": "float",
                        "valueMax": 100,
                        "valueMin": 0,
                    }
                ]
            },
        ),
        (
            True,
            {
                "turn_on",
                "toggle",
                "turn_off",
                "brightness_increase",
                "brightness_decrease",
            },
            0,
            0,
            None,
            {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS]},
            {
                "turn_on": [
                    {
                        "name": "brightness_pct",
                        "optional": True,
                        "type": "float",
                        "valueMax": 100,
                        "valueMin": 0,
                    }
                ]
            },
        ),
        (
            False,
            {"turn_on", "toggle", "turn_off", "flash"},
            LightEntityFeature.FLASH,
            0,
            None,
            {},
            {
                "turn_on": [
                    {
                        "name": "flash",
                        "optional": True,
                        "type": "select",
                        "options": [("short", "short"), ("long", "long")],
                    }
                ]
            },
        ),
        (
            True,
            {"turn_on", "toggle", "turn_off", "flash"},
            0,
            LightEntityFeature.FLASH,
            None,
            {},
            {
                "turn_on": [
                    {
                        "name": "flash",
                        "optional": True,
                        "type": "select",
                        "options": [("short", "short"), ("long", "long")],
                    }
                ]
            },
        ),
    ],
)
async def test_get_action_capabilities_features(
    hass,
    device_reg,
    entity_reg,
    set_state,
    expected_actions,
    supported_features_reg,
    supported_features_state,
    capabilities_reg,
    attributes_state,
    expected_capabilities,
):
    """Test we get the expected capabilities from a light action."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_id = entity_reg.async_get_or_create(
        DOMAIN,
        "test",
        "5678",
        device_id=device_entry.id,
        supported_features=supported_features_reg,
        capabilities=capabilities_reg,
    ).entity_id
    if set_state:
        hass.states.async_set(
            entity_id,
            None,
            {"supported_features": supported_features_state, **attributes_state},
        )

    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert len(actions) == len(expected_actions)
    action_types = {action["type"] for action in actions}
    assert action_types == expected_actions
    for action in actions:
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.ACTION, action
        )
        expected = {"extra_fields": expected_capabilities.get(action["type"], [])}
        assert capabilities == expected


async def test_action(hass, calls, enable_custom_integrations):
    """Test for turn_on and turn_off actions."""
    platform = getattr(hass.components, f"test.{DOMAIN}")

    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_off"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": ent1.entity_id,
                        "type": "turn_off",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_on"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": ent1.entity_id,
                        "type": "turn_on",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_toggle"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": ent1.entity_id,
                        "type": "toggle",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_flash_short"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": ent1.entity_id,
                        "type": "flash",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_flash_long"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": ent1.entity_id,
                        "type": "flash",
                        "flash": "long",
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_brightness_increase",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": ent1.entity_id,
                        "type": "brightness_increase",
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_brightness_decrease",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": ent1.entity_id,
                        "type": "brightness_decrease",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_brightness"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": ent1.entity_id,
                        "type": "turn_on",
                        "brightness_pct": 75,
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_ON
    assert len(calls) == 0

    hass.bus.async_fire("test_off")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_OFF

    hass.bus.async_fire("test_off")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_OFF

    hass.bus.async_fire("test_on")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_ON

    hass.bus.async_fire("test_on")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_ON

    hass.bus.async_fire("test_toggle")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_OFF

    hass.bus.async_fire("test_toggle")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_ON

    hass.bus.async_fire("test_toggle")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_OFF

    hass.bus.async_fire("test_flash_short")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_ON

    hass.bus.async_fire("test_toggle")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_OFF

    hass.bus.async_fire("test_flash_long")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_ON

    turn_on_calls = async_mock_service(hass, DOMAIN, "turn_on")

    hass.bus.async_fire("test_brightness_increase")
    await hass.async_block_till_done()

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].data["entity_id"] == ent1.entity_id
    assert turn_on_calls[0].data["brightness_step_pct"] == 10

    hass.bus.async_fire("test_brightness_decrease")
    await hass.async_block_till_done()

    assert len(turn_on_calls) == 2
    assert turn_on_calls[1].data["entity_id"] == ent1.entity_id
    assert turn_on_calls[1].data["brightness_step_pct"] == -10

    hass.bus.async_fire("test_brightness")
    await hass.async_block_till_done()

    assert len(turn_on_calls) == 3
    assert turn_on_calls[2].data["entity_id"] == ent1.entity_id
    assert turn_on_calls[2].data["brightness_pct"] == 75

    hass.bus.async_fire("test_on")
    await hass.async_block_till_done()

    assert len(turn_on_calls) == 4
    assert turn_on_calls[3].data["entity_id"] == ent1.entity_id
    assert "brightness_pct" not in turn_on_calls[3].data

    hass.bus.async_fire("test_flash_short")
    await hass.async_block_till_done()

    assert len(turn_on_calls) == 5
    assert turn_on_calls[4].data["entity_id"] == ent1.entity_id
    assert turn_on_calls[4].data["flash"] == FLASH_SHORT

    hass.bus.async_fire("test_flash_long")
    await hass.async_block_till_done()

    assert len(turn_on_calls) == 6
    assert turn_on_calls[5].data["entity_id"] == ent1.entity_id
    assert turn_on_calls[5].data["flash"] == FLASH_LONG
