"""The test for remote device automation."""
import pytest

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.remote import DOMAIN
from homeassistant.const import CONF_PLATFORM, STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryHider
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
)
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_actions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected actions from a remote."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )
    expected_actions = [
        {
            "domain": DOMAIN,
            "type": action,
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
            "metadata": {"secondary": False},
        }
        for action in ["turn_off", "turn_on", "toggle"]
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert_lists_same(actions, expected_actions)


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
    entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        "5678",
        device_id=device_entry.id,
        entity_category=entity_category,
        hidden_by=hidden_by,
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
        for action in ["turn_off", "turn_on", "toggle"]
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert_lists_same(actions, expected_actions)


async def test_action(
    hass: HomeAssistant, calls, enable_custom_integrations: None
) -> None:
    """Test for turn_on and turn_off actions."""
    platform = getattr(hass.components, f"test.{DOMAIN}")

    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    ent1, ent2, ent3 = platform.ENTITIES

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": ent1.entity_id,
                        "type": "turn_off",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event2"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": ent1.entity_id,
                        "type": "turn_on",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event3"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": ent1.entity_id,
                        "type": "toggle",
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_ON
    assert len(calls) == 0

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_OFF

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_OFF

    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_ON

    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_ON

    hass.bus.async_fire("test_event3")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_OFF

    hass.bus.async_fire("test_event3")
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_ON
