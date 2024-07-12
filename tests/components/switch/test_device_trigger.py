"""The test for switch device automation."""

from datetime import timedelta

import pytest
from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.switch import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryHider
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_get_device_automation_capabilities,
    async_get_device_automations,
)


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected triggers from a switch."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        }
        for trigger in ("changed_states", "turned_off", "turned_on")
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


@pytest.mark.parametrize(
    ("hidden_by", "entity_category"),
    [
        (RegistryEntryHider.INTEGRATION, None),
        (RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ],
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
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": True},
        }
        for trigger in ("changed_states", "turned_off", "turned_on")
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
    """Test we get the expected capabilities from a switch trigger."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )
    expected_capabilities = {
        "extra_fields": [
            {"name": "for", "optional": True, "type": "positive_time_period_dict"}
        ]
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    for trigger in triggers:
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.TRIGGER, trigger
        )
        assert capabilities == expected_capabilities


async def test_get_trigger_capabilities_legacy(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected capabilities from a switch trigger."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )
    expected_capabilities = {
        "extra_fields": [
            {"name": "for", "optional": True, "type": "positive_time_period_dict"}
        ]
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    for trigger in triggers:
        trigger["entity_id"] = entity_registry.async_get(trigger["entity_id"]).entity_id
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.TRIGGER, trigger
        )
        assert capabilities == expected_capabilities


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_if_fires_on_state_change(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test for turn_on and turn_off triggers firing."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    hass.states.async_set(entry.entity_id, STATE_ON)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
                        "type": "turned_on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "turn_on {{ trigger.platform }}"
                                " - {{ trigger.entity_id }}"
                                " - {{ trigger.from_state.state }}"
                                " - {{ trigger.to_state.state }}"
                                " - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
                        "type": "turned_off",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "turn_off {{ trigger.platform }}"
                                " - {{ trigger.entity_id }}"
                                " - {{ trigger.from_state.state }}"
                                " - {{ trigger.to_state.state }}"
                                " - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
                        "type": "changed_states",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "turn_on_or_off {{ trigger.platform }}"
                                " - {{ trigger.entity_id }}"
                                " - {{ trigger.from_state.state }}"
                                " - {{ trigger.to_state.state }}"
                                " - {{ trigger.for }}"
                            )
                        },
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(entry.entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(service_calls) == 2
    assert {service_calls[0].data["some"], service_calls[1].data["some"]} == {
        f"turn_off device - {entry.entity_id} - on - off - None",
        f"turn_on_or_off device - {entry.entity_id} - on - off - None",
    }

    hass.states.async_set(entry.entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert len(service_calls) == 4
    assert {service_calls[2].data["some"], service_calls[3].data["some"]} == {
        f"turn_on device - {entry.entity_id} - off - on - None",
        f"turn_on_or_off device - {entry.entity_id} - off - on - None",
    }


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_if_fires_on_state_change_legacy(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test for turn_on and turn_off triggers firing."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    hass.states.async_set(entry.entity_id, STATE_ON)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entry.entity_id,
                        "type": "turned_off",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "turn_off {{ trigger.platform }}"
                                " - {{ trigger.entity_id }}"
                                " - {{ trigger.from_state.state }}"
                                " - {{ trigger.to_state.state }}"
                                " - {{ trigger.for }}"
                            )
                        },
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(entry.entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert (
        service_calls[0].data["some"]
        == f"turn_off device - {entry.entity_id} - on - off - None"
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_if_fires_on_state_change_with_for(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test for triggers firing with delay."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    hass.states.async_set(entry.entity_id, STATE_ON)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
                        "type": "turned_off",
                        "for": {"seconds": 5},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "turn_off {{ trigger.platform }}"
                                " - {{ trigger.entity_id }}"
                                " - {{ trigger.from_state.state }}"
                                " - {{ trigger.to_state.state }}"
                                " - {{ trigger.for }}"
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(entry.entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(service_calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    await hass.async_block_till_done()
    assert (
        service_calls[0].data["some"]
        == f"turn_off device - {entry.entity_id} - on - off - 0:00:05"
    )
