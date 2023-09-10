"""The tests for Media player device triggers."""
from datetime import timedelta

import pytest
from pytest_unordered import unordered

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.media_player import DOMAIN
from homeassistant.const import (
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryHider
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_get_device_automation_capabilities,
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


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected triggers from a media player."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    trigger_types = {
        "buffering",
        "changed_states",
        "idle",
        "paused",
        "playing",
        "turned_off",
        "turned_on",
    }
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        }
        for trigger in trigger_types
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


@pytest.mark.parametrize(
    ("hidden_by", "entity_category"),
    (
        (RegistryEntryHider.INTEGRATION, None),
        (RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ),
)
async def test_get_triggers_hidden_auxiliary(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hidden_by,
    entity_category,
) -> None:
    """Test we get the expected triggers from a hidden or auxiliary entity."""
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
    trigger_types = {
        "buffering",
        "changed_states",
        "idle",
        "paused",
        "playing",
        "turned_off",
        "turned_on",
    }
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": True},
        }
        for trigger in trigger_types
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


async def test_get_trigger_capabilities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected capabilities from a media player."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 7
    for trigger in triggers:
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.TRIGGER, trigger
        )
        assert capabilities == {
            "extra_fields": [
                {"name": "for", "optional": True, "type": "positive_time_period_dict"}
            ]
        }


async def test_get_trigger_capabilities_legacy(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected capabilities from a media player."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 7
    for trigger in triggers:
        trigger["entity_id"] = entity_registry.async_get(trigger["entity_id"]).entity_id
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.TRIGGER, trigger
        )
        assert capabilities == {
            "extra_fields": [
                {"name": "for", "optional": True, "type": "positive_time_period_dict"}
            ]
        }


async def test_if_fires_on_state_change(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, calls
) -> None:
    """Test triggers firing."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

    hass.states.async_set(entry.entity_id, STATE_OFF)

    data_template = (
        "{label} - {{{{ trigger.platform}}}} - "
        "{{{{ trigger.entity_id}}}} - {{{{ trigger.from_state.state}}}} - "
        "{{{{ trigger.to_state.state}}}} - {{{{ trigger.for }}}}"
    )
    trigger_types = {
        "buffering",
        "changed_states",
        "idle",
        "paused",
        "playing",
        "turned_off",
        "turned_on",
    }

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
                        "entity_id": entry.id,
                        "type": trigger,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": data_template.format(label=trigger)},
                    },
                }
                for trigger in trigger_types
            ]
        },
    )

    # Fake that the entity is turning on.
    hass.states.async_set(entry.entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert {calls[0].data["some"], calls[1].data["some"]} == {
        "turned_on - device - media_player.test_5678 - off - on - None",
        "changed_states - device - media_player.test_5678 - off - on - None",
    }

    # Fake that the entity is turning off.
    hass.states.async_set(entry.entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(calls) == 4
    assert {calls[2].data["some"], calls[3].data["some"]} == {
        "turned_off - device - media_player.test_5678 - on - off - None",
        "changed_states - device - media_player.test_5678 - on - off - None",
    }

    # Fake that the entity becomes idle.
    hass.states.async_set(entry.entity_id, STATE_IDLE)
    await hass.async_block_till_done()
    assert len(calls) == 6
    assert {calls[4].data["some"], calls[5].data["some"]} == {
        "idle - device - media_player.test_5678 - off - idle - None",
        "changed_states - device - media_player.test_5678 - off - idle - None",
    }

    # Fake that the entity starts playing.
    hass.states.async_set(entry.entity_id, STATE_PLAYING)
    await hass.async_block_till_done()
    assert len(calls) == 8
    assert {calls[6].data["some"], calls[7].data["some"]} == {
        "playing - device - media_player.test_5678 - idle - playing - None",
        "changed_states - device - media_player.test_5678 - idle - playing - None",
    }

    # Fake that the entity is paused.
    hass.states.async_set(entry.entity_id, STATE_PAUSED)
    await hass.async_block_till_done()
    assert len(calls) == 10
    assert {calls[8].data["some"], calls[9].data["some"]} == {
        "paused - device - media_player.test_5678 - playing - paused - None",
        "changed_states - device - media_player.test_5678 - playing - paused - None",
    }

    # Fake that the entity is buffering.
    hass.states.async_set(entry.entity_id, STATE_BUFFERING)
    await hass.async_block_till_done()
    assert len(calls) == 12
    assert {calls[10].data["some"], calls[11].data["some"]} == {
        "buffering - device - media_player.test_5678 - paused - buffering - None",
        "changed_states - device - media_player.test_5678 - paused - buffering - None",
    }


async def test_if_fires_on_state_change_legacy(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, calls
) -> None:
    """Test triggers firing."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

    hass.states.async_set(entry.entity_id, STATE_OFF)

    data_template = (
        "{label} - {{{{ trigger.platform}}}} - "
        "{{{{ trigger.entity_id}}}} - {{{{ trigger.from_state.state}}}} - "
        "{{{{ trigger.to_state.state}}}} - {{{{ trigger.for }}}}"
    )

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
                        "entity_id": entry.entity_id,
                        "type": "turned_on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": data_template.format(label="turned_on")
                        },
                    },
                }
            ]
        },
    )

    # Fake that the entity is turning on.
    hass.states.async_set(entry.entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert (
        calls[0].data["some"]
        == "turned_on - device - media_player.test_5678 - off - on - None"
    )


async def test_if_fires_on_state_change_with_for(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, calls
) -> None:
    """Test for triggers firing with delay."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

    hass.states.async_set(entry.entity_id, STATE_OFF)

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
                        "entity_id": entry.id,
                        "type": "turned_on",
                        "for": {"seconds": 5},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "turn_off {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                (
                                    "platform",
                                    "entity_id",
                                    "from_state.state",
                                    "to_state.state",
                                    "for",
                                )
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set(entry.entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    await hass.async_block_till_done()
    assert (
        calls[0].data["some"]
        == f"turn_off device - {entry.entity_id} - off - on - 0:00:05"
    )
