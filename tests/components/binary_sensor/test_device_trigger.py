"""The test for binary_sensor device automation."""

from datetime import timedelta

import pytest
from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.binary_sensor import DOMAIN, BinarySensorDeviceClass
from homeassistant.components.binary_sensor.device_trigger import ENTITY_TRIGGERS
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.const import CONF_PLATFORM, STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .common import MockBinarySensor

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_get_device_automation_capabilities,
    async_get_device_automations,
    async_mock_service,
    setup_test_component_platform,
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
    mock_binary_sensor_entities: dict[str, MockBinarySensor],
) -> None:
    """Test we get the expected triggers from a binary_sensor."""
    registry_entries: dict[BinarySensorDeviceClass, er.RegistryEntry] = {}
    setup_test_component_platform(hass, DOMAIN, mock_binary_sensor_entities.values())
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    for device_class in BinarySensorDeviceClass:
        registry_entries[device_class] = entity_registry.async_get_or_create(
            DOMAIN,
            "test",
            mock_binary_sensor_entities[device_class].unique_id,
            device_id=device_entry.id,
        )

    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger["type"],
            "device_id": device_entry.id,
            "entity_id": registry_entries[device_class].id,
            "metadata": {"secondary": False},
        }
        for device_class in BinarySensorDeviceClass
        for trigger in ENTITY_TRIGGERS[device_class]
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


@pytest.mark.parametrize(
    ("hidden_by", "entity_category"),
    [
        (er.RegistryEntryHider.INTEGRATION, None),
        (er.RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ],
)
async def test_get_triggers_hidden_auxiliary(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hidden_by: er.RegistryEntryHider | None,
    entity_category: EntityCategory | None,
) -> None:
    """Test we get the expected triggers from a hidden or auxiliary entity."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
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
            "entity_id": entry.id,
            "metadata": {"secondary": True},
        }
        for trigger in ["turned_on", "turned_off"]
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


async def test_get_triggers_no_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_binary_sensor_entities: dict[str, MockBinarySensor],
) -> None:
    """Test we get the expected triggers from a binary_sensor."""
    registry_entries: dict[BinarySensorDeviceClass, er.RegistryEntry] = {}
    setup_test_component_platform(hass, DOMAIN, mock_binary_sensor_entities.values())

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    for device_class in BinarySensorDeviceClass:
        registry_entries[device_class] = entity_registry.async_get_or_create(
            DOMAIN,
            "test",
            f"5678_{device_class}",
            device_id=device_entry.id,
            original_device_class=device_class,
        )

    await hass.async_block_till_done()

    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger["type"],
            "device_id": device_entry.id,
            "entity_id": registry_entries[device_class].id,
            "metadata": {"secondary": False},
        }
        for device_class in BinarySensorDeviceClass
        for trigger in ENTITY_TRIGGERS[device_class]
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
    """Test we get the expected capabilities from a binary_sensor trigger."""
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
    """Test we get the expected capabilities from a binary_sensor trigger."""
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


async def test_if_fires_on_state_change(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    calls,
    mock_binary_sensor_entities: dict[str, MockBinarySensor],
) -> None:
    """Test for on and off triggers firing."""
    setup_test_component_platform(hass, DOMAIN, mock_binary_sensor_entities.values())
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        mock_binary_sensor_entities["battery"].unique_id,
        device_id=device_entry.id,
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
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
                        "type": "bat_low",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "bat_low {{ trigger.platform }}"
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
                        "type": "not_bat_low",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "not_bat_low {{ trigger.platform }}"
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
    assert hass.states.get(entry.entity_id).state == STATE_ON
    assert len(calls) == 0

    hass.states.async_set(entry.entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert (
        calls[0].data["some"]
        == f"not_bat_low device - {entry.entity_id} - on - off - None"
    )

    hass.states.async_set(entry.entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert (
        calls[1].data["some"] == f"bat_low device - {entry.entity_id} - off - on - None"
    )


async def test_if_fires_on_state_change_with_for(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    calls,
    mock_binary_sensor_entities: dict[str, MockBinarySensor],
) -> None:
    """Test for triggers firing with delay."""
    setup_test_component_platform(hass, DOMAIN, mock_binary_sensor_entities.values())
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        mock_binary_sensor_entities["battery"].unique_id,
        device_id=device_entry.id,
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
    assert hass.states.get(entry.entity_id).state == STATE_ON
    assert len(calls) == 0

    hass.states.async_set(entry.entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    await hass.async_block_till_done()
    assert (
        calls[0].data["some"]
        == f"turn_off device - {entry.entity_id} - on - off - 0:00:05"
    )


async def test_if_fires_on_state_change_legacy(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    calls,
    mock_binary_sensor_entities: dict[str, MockBinarySensor],
) -> None:
    """Test for triggers firing."""
    setup_test_component_platform(hass, DOMAIN, mock_binary_sensor_entities.values())
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        mock_binary_sensor_entities["battery"].unique_id,
        device_id=device_entry.id,
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
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(entry.entity_id).state == STATE_ON
    assert len(calls) == 0

    hass.states.async_set(entry.entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert (
        calls[0].data["some"]
        == f"turn_off device - {entry.entity_id} - on - off - None"
    )
