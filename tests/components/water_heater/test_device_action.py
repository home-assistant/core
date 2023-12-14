"""The tests for Water Heater device actions."""
import pytest
from pytest_unordered import unordered

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.water_heater import DOMAIN
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
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


async def test_get_actions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected actions from a water_heater."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )
    expected_actions = [
        {
            "domain": DOMAIN,
            "type": action,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        }
        for action in ["turn_on", "turn_off"]
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
        for action in ["turn_on", "turn_off"]
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert actions == unordered(expected_actions)


async def test_action(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for turn_on and turn_off actions."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_turn_off",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
                        "type": "turn_off",
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_turn_on",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
                        "type": "turn_on",
                    },
                },
            ]
        },
    )

    turn_off_calls = async_mock_service(hass, "water_heater", "turn_off")
    turn_on_calls = async_mock_service(hass, "water_heater", "turn_on")

    hass.bus.async_fire("test_event_turn_off")
    await hass.async_block_till_done()
    assert len(turn_off_calls) == 1
    assert len(turn_on_calls) == 0

    hass.bus.async_fire("test_event_turn_on")
    await hass.async_block_till_done()
    assert len(turn_off_calls) == 1
    assert len(turn_on_calls) == 1

    assert turn_off_calls[-1].data == {"entity_id": entry.entity_id}
    assert turn_on_calls[-1].data == {"entity_id": entry.entity_id}


async def test_action_legacy(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for turn_on and turn_off actions."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_turn_off",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entry.entity_id,
                        "type": "turn_off",
                    },
                },
            ]
        },
    )

    turn_off_calls = async_mock_service(hass, "water_heater", "turn_off")

    hass.bus.async_fire("test_event_turn_off")
    await hass.async_block_till_done()
    assert len(turn_off_calls) == 1

    assert turn_off_calls[-1].data == {"entity_id": entry.entity_id}
