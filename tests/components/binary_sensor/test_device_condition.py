"""The test for binary_sensor device automation."""

from datetime import timedelta

from freezegun import freeze_time
import pytest
from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.binary_sensor import DOMAIN, BinarySensorDeviceClass
from homeassistant.components.binary_sensor.device_condition import ENTITY_CONDITIONS
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.const import CONF_PLATFORM, STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .common import MockBinarySensor

from tests.common import (
    MockConfigEntry,
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


async def test_get_conditions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_binary_sensor_entities: dict[str, MockBinarySensor],
) -> None:
    """Test we get the expected conditions from a binary_sensor."""
    setup_test_component_platform(hass, DOMAIN, mock_binary_sensor_entities.values())
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()
    binary_sensor_entries = {}

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    for device_class in BinarySensorDeviceClass:
        binary_sensor_entries[device_class] = entity_registry.async_get_or_create(
            DOMAIN,
            "test",
            mock_binary_sensor_entities[device_class].unique_id,
            device_id=device_entry.id,
        )

    expected_conditions = [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": condition["type"],
            "device_id": device_entry.id,
            "entity_id": binary_sensor_entries[device_class].id,
            "metadata": {"secondary": False},
        }
        for device_class in BinarySensorDeviceClass
        for condition in ENTITY_CONDITIONS[device_class]
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert conditions == unordered(expected_conditions)


@pytest.mark.parametrize(
    ("hidden_by", "entity_category"),
    [
        (er.RegistryEntryHider.INTEGRATION, None),
        (er.RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ],
)
async def test_get_conditions_hidden_auxiliary(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hidden_by: er.RegistryEntryHider | None,
    entity_category: EntityCategory | None,
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
        for condition in ["is_on", "is_off"]
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert conditions == unordered(expected_conditions)


async def test_get_conditions_no_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected conditions from a binary_sensor."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    binary_sensor_entries = {}
    for device_class in BinarySensorDeviceClass:
        binary_sensor_entries[device_class] = entity_registry.async_get_or_create(
            DOMAIN,
            "test",
            f"5678_{device_class}",
            device_id=device_entry.id,
            original_device_class=device_class,
        )

    await hass.async_block_till_done()

    expected_conditions = [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": condition["type"],
            "device_id": device_entry.id,
            "entity_id": binary_sensor_entries[device_class].id,
            "metadata": {"secondary": False},
        }
        for device_class in BinarySensorDeviceClass
        for condition in ENTITY_CONDITIONS[device_class]
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert conditions == expected_conditions


async def test_get_condition_capabilities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected capabilities from a binary_sensor condition."""
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
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    for condition in conditions:
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.CONDITION, condition
        )
        assert capabilities == expected_capabilities


async def test_get_condition_capabilities_legacy(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected capabilities from a binary_sensor condition."""
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
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    for condition in conditions:
        condition["entity_id"] = entity_registry.async_get(
            condition["entity_id"]
        ).entity_id
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.CONDITION, condition
        )
        assert capabilities == expected_capabilities


async def test_if_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    calls,
    mock_binary_sensor_entities: dict[str, MockBinarySensor],
) -> None:
    """Test for turn_on and turn_off conditions."""
    setup_test_component_platform(hass, DOMAIN, mock_binary_sensor_entities.values())
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get(mock_binary_sensor_entities["battery"].entity_id)
    entity_registry.async_update_entity(entry.entity_id, device_id=device_entry.id)

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
                            "type": "is_bat_low",
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
                            "type": "is_not_bat_low",
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
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(entry.entity_id).state == STATE_ON
    assert len(calls) == 0

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "is_on event - test_event1"

    hass.states.async_set(entry.entity_id, STATE_OFF)
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "is_off event - test_event2"


async def test_if_state_legacy(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    calls,
    mock_binary_sensor_entities: dict[str, MockBinarySensor],
) -> None:
    """Test for turn_on and turn_off conditions."""
    setup_test_component_platform(hass, DOMAIN, mock_binary_sensor_entities.values())
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get(mock_binary_sensor_entities["battery"].entity_id)
    entity_registry.async_update_entity(entry.entity_id, device_id=device_entry.id)

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
                            "type": "is_bat_low",
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
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(entry.entity_id).state == STATE_ON
    assert len(calls) == 0

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "is_on event - test_event1"


async def test_if_fires_on_for_condition(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    calls,
    mock_binary_sensor_entities: dict[str, MockBinarySensor],
) -> None:
    """Test for firing if condition is on with delay."""
    point1 = dt_util.utcnow()
    point2 = point1 + timedelta(seconds=10)
    point3 = point2 + timedelta(seconds=10)

    setup_test_component_platform(hass, DOMAIN, mock_binary_sensor_entities.values())
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get(mock_binary_sensor_entities["battery"].entity_id)
    entity_registry.async_update_entity(entry.entity_id, device_id=device_entry.id)

    with freeze_time(point1) as time_freeze:
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: [
                    {
                        "trigger": {"platform": "event", "event_type": "test_event1"},
                        "condition": {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device_entry.id,
                            "entity_id": entry.id,
                            "type": "is_not_bat_low",
                            "for": {"seconds": 5},
                        },
                        "action": {
                            "service": "test.automation",
                            "data_template": {
                                "some": (
                                    "is_off {{ trigger.platform }}"
                                    " - {{ trigger.event.event_type }}"
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

        hass.bus.async_fire("test_event1")
        await hass.async_block_till_done()
        assert len(calls) == 0

        # Time travel 10 secs into the future
        time_freeze.move_to(point2)
        hass.bus.async_fire("test_event1")
        await hass.async_block_till_done()
        assert len(calls) == 0

        hass.states.async_set(entry.entity_id, STATE_OFF)
        hass.bus.async_fire("test_event1")
        await hass.async_block_till_done()
        assert len(calls) == 0

        # Time travel 20 secs into the future
        time_freeze.move_to(point3)
        hass.bus.async_fire("test_event1")
        await hass.async_block_till_done()
        assert len(calls) == 1
        assert calls[0].data["some"] == "is_off event - test_event1"
