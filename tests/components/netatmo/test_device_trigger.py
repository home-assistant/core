"""The tests for Netatmo device triggers."""
import pytest
from pytest_unordered import unordered

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.netatmo import DOMAIN as NETATMO_DOMAIN
from homeassistant.components.netatmo.const import (
    CLIMATE_TRIGGERS,
    INDOOR_CAMERA_TRIGGERS,
    NETATMO_EVENT,
    OUTDOOR_CAMERA_TRIGGERS,
)
from homeassistant.components.netatmo.device_trigger import SUBTYPES
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    async_capture_events,
    async_get_device_automations,
    async_mock_service,
)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.mark.parametrize(
    ("platform", "device_type", "event_types"),
    [
        ("camera", "Smart Outdoor Camera", OUTDOOR_CAMERA_TRIGGERS),
        ("camera", "Smart Indoor Camera", INDOOR_CAMERA_TRIGGERS),
        ("climate", "Smart Valve", CLIMATE_TRIGGERS),
        ("climate", "Smart Thermostat", CLIMATE_TRIGGERS),
    ],
)
async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    platform,
    device_type,
    event_types,
) -> None:
    """Test we get the expected triggers from a netatmo devices."""
    config_entry = MockConfigEntry(domain=NETATMO_DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        model=device_type,
    )
    entity_entry = entity_registry.async_get_or_create(
        platform, NETATMO_DOMAIN, "5678", device_id=device_entry.id
    )
    expected_triggers = []
    for event_type in event_types:
        if event_type in SUBTYPES:
            for subtype in SUBTYPES[event_type]:
                expected_triggers.append(
                    {
                        "platform": "device",
                        "domain": NETATMO_DOMAIN,
                        "type": event_type,
                        "subtype": subtype,
                        "device_id": device_entry.id,
                        "entity_id": entity_entry.id,
                        "metadata": {"secondary": False},
                    }
                )
        else:
            expected_triggers.append(
                {
                    "platform": "device",
                    "domain": NETATMO_DOMAIN,
                    "type": event_type,
                    "device_id": device_entry.id,
                    "entity_id": entity_entry.id,
                    "metadata": {"secondary": False},
                }
            )
    triggers = [
        trigger
        for trigger in await async_get_device_automations(
            hass, DeviceAutomationType.TRIGGER, device_entry.id
        )
        if trigger["domain"] == NETATMO_DOMAIN
    ]
    assert triggers == unordered(expected_triggers)


@pytest.mark.parametrize(
    ("platform", "camera_type", "event_type"),
    [("camera", "Smart Outdoor Camera", trigger) for trigger in OUTDOOR_CAMERA_TRIGGERS]
    + [("camera", "Smart Indoor Camera", trigger) for trigger in INDOOR_CAMERA_TRIGGERS]
    + [
        ("climate", "Smart Valve", trigger)
        for trigger in CLIMATE_TRIGGERS
        if trigger not in SUBTYPES
    ]
    + [
        ("climate", "Smart Thermostat", trigger)
        for trigger in CLIMATE_TRIGGERS
        if trigger not in SUBTYPES
    ],
)
async def test_if_fires_on_event(
    hass: HomeAssistant,
    calls,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    platform,
    camera_type,
    event_type,
) -> None:
    """Test for event triggers firing."""
    mac_address = "12:34:56:AB:CD:EF"
    connection = (dr.CONNECTION_NETWORK_MAC, mac_address)
    config_entry = MockConfigEntry(domain=NETATMO_DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={connection},
        identifiers={(NETATMO_DOMAIN, mac_address)},
        model=camera_type,
    )
    entity_entry = entity_registry.async_get_or_create(
        platform, NETATMO_DOMAIN, "5678", device_id=device_entry.id
    )
    events = async_capture_events(hass, "netatmo_event")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": NETATMO_DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entity_entry.id,
                        "type": event_type,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "{{trigger.event.data.type}} - {{trigger.platform}} - {{trigger.event.data.device_id}}"
                            )
                        },
                    },
                },
            ]
        },
    )

    device = device_registry.async_get_device(connections={connection})
    assert device is not None

    # Fake that the entity is turning on.
    hass.bus.async_fire(
        event_type=NETATMO_EVENT,
        event_data={
            "type": event_type,
            ATTR_DEVICE_ID: device.id,
        },
    )
    await hass.async_block_till_done()
    assert len(events) == 1
    assert len(calls) == 1
    assert calls[0].data["some"] == f"{event_type} - device - {device.id}"


@pytest.mark.parametrize(
    ("platform", "camera_type", "event_type"),
    [("camera", "Smart Outdoor Camera", trigger) for trigger in OUTDOOR_CAMERA_TRIGGERS]
    + [("camera", "Smart Indoor Camera", trigger) for trigger in INDOOR_CAMERA_TRIGGERS]
    + [
        ("climate", "Smart Valve", trigger)
        for trigger in CLIMATE_TRIGGERS
        if trigger not in SUBTYPES
    ]
    + [
        ("climate", "Smart Thermostat", trigger)
        for trigger in CLIMATE_TRIGGERS
        if trigger not in SUBTYPES
    ],
)
async def test_if_fires_on_event_legacy(
    hass: HomeAssistant,
    calls,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    platform,
    camera_type,
    event_type,
) -> None:
    """Test for event triggers firing."""
    mac_address = "12:34:56:AB:CD:EF"
    connection = (dr.CONNECTION_NETWORK_MAC, mac_address)
    config_entry = MockConfigEntry(domain=NETATMO_DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={connection},
        identifiers={(NETATMO_DOMAIN, mac_address)},
        model=camera_type,
    )
    entity_entry = entity_registry.async_get_or_create(
        platform, NETATMO_DOMAIN, "5678", device_id=device_entry.id
    )
    events = async_capture_events(hass, "netatmo_event")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": NETATMO_DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entity_entry.entity_id,
                        "type": event_type,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "{{trigger.event.data.type}} - {{trigger.platform}} - {{trigger.event.data.device_id}}"
                            )
                        },
                    },
                },
            ]
        },
    )

    device = device_registry.async_get_device(connections={connection})
    assert device is not None

    # Fake that the entity is turning on.
    hass.bus.async_fire(
        event_type=NETATMO_EVENT,
        event_data={
            "type": event_type,
            ATTR_DEVICE_ID: device.id,
        },
    )
    await hass.async_block_till_done()
    assert len(events) == 1
    assert len(calls) == 1
    assert calls[0].data["some"] == f"{event_type} - device - {device.id}"


@pytest.mark.parametrize(
    ("platform", "camera_type", "event_type", "sub_type"),
    [
        ("climate", "Smart Valve", trigger, subtype)
        for trigger in SUBTYPES
        for subtype in SUBTYPES[trigger]
    ]
    + [
        ("climate", "Smart Thermostat", trigger, subtype)
        for trigger in SUBTYPES
        for subtype in SUBTYPES[trigger]
    ],
)
async def test_if_fires_on_event_with_subtype(
    hass: HomeAssistant,
    calls,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    platform,
    camera_type,
    event_type,
    sub_type,
) -> None:
    """Test for event triggers firing."""
    mac_address = "12:34:56:AB:CD:EF"
    connection = (dr.CONNECTION_NETWORK_MAC, mac_address)
    config_entry = MockConfigEntry(domain=NETATMO_DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={connection},
        identifiers={(NETATMO_DOMAIN, mac_address)},
        model=camera_type,
    )
    entity_entry = entity_registry.async_get_or_create(
        platform, NETATMO_DOMAIN, "5678", device_id=device_entry.id
    )
    events = async_capture_events(hass, "netatmo_event")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": NETATMO_DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entity_entry.id,
                        "type": event_type,
                        "subtype": sub_type,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "{{trigger.event.data.type}} - {{trigger.event.data.data.mode}} - "
                                "{{trigger.platform}} - {{trigger.event.data.device_id}}"
                            )
                        },
                    },
                },
            ]
        },
    )

    device = device_registry.async_get_device(connections={connection})
    assert device is not None

    # Fake that the entity is turning on.
    hass.bus.async_fire(
        event_type=NETATMO_EVENT,
        event_data={
            "type": event_type,
            "data": {
                "mode": sub_type,
            },
            ATTR_DEVICE_ID: device.id,
        },
    )
    await hass.async_block_till_done()
    assert len(events) == 1
    assert len(calls) == 1
    assert calls[0].data["some"] == f"{event_type} - {sub_type} - device - {device.id}"


@pytest.mark.parametrize(
    ("platform", "device_type", "event_type"),
    [("climate", "NAPlug", trigger) for trigger in CLIMATE_TRIGGERS],
)
async def test_if_invalid_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    platform,
    device_type,
    event_type,
) -> None:
    """Test for event triggers firing."""
    mac_address = "12:34:56:AB:CD:EF"
    connection = (dr.CONNECTION_NETWORK_MAC, mac_address)
    config_entry = MockConfigEntry(domain=NETATMO_DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={connection},
        identifiers={(NETATMO_DOMAIN, mac_address)},
        model=device_type,
    )
    entity_entry = entity_registry.async_get_or_create(
        platform, NETATMO_DOMAIN, "5678", device_id=device_entry.id
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": NETATMO_DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entity_entry.id,
                        "type": event_type,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "{{trigger.event.data.type}} - {{trigger.platform}} - {{trigger.event.data.device_id}}"
                            )
                        },
                    },
                },
            ]
        },
    )
