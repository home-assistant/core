"""The tests for Netatmo device triggers."""
import pytest

import homeassistant.components.automation as automation
from homeassistant.components.netatmo import DOMAIN as NETATMO_DOMAIN
from homeassistant.components.netatmo.const import (
    INDOOR_CAMERA_TRIGGERS,
    MODEL_NACAMERA,
    MODEL_NOC,
    NETATMO_EVENT,
    OUTDOOR_CAMERA_TRIGGERS,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_capture_events,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)


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


@pytest.mark.parametrize(
    "camera_type,event_types",
    [
        (MODEL_NOC, OUTDOOR_CAMERA_TRIGGERS),
        (MODEL_NACAMERA, INDOOR_CAMERA_TRIGGERS),
    ],
)
async def test_get_triggers_camera(
    hass, device_reg, entity_reg, camera_type, event_types
):
    """Test we get the expected triggers from a netatmo cameras."""
    config_entry = MockConfigEntry(domain=NETATMO_DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        model=camera_type,
    )
    entity_reg.async_get_or_create(
        "camera", NETATMO_DOMAIN, "5678", device_id=device_entry.id
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": NETATMO_DOMAIN,
            "type": event_type,
            "device_id": device_entry.id,
            "entity_id": f"camera.{NETATMO_DOMAIN}_5678",
        }
        for event_type in event_types
    ]
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, expected_triggers)


@pytest.mark.parametrize(
    "camera_type,event_type",
    [(MODEL_NOC, trigger) for trigger in OUTDOOR_CAMERA_TRIGGERS]
    + [(MODEL_NACAMERA, trigger) for trigger in INDOOR_CAMERA_TRIGGERS],
)
async def test_if_fires_on_camera_event(
    hass, calls, device_reg, entity_reg, camera_type, event_type
):
    """Test for camera event triggers firing."""
    mac_address = "12:34:56:AB:CD:EF"
    connection = (device_registry.CONNECTION_NETWORK_MAC, mac_address)
    config_entry = MockConfigEntry(domain=NETATMO_DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={connection},
        identifiers={(NETATMO_DOMAIN, mac_address)},
        model=camera_type,
    )
    entity_reg.async_get_or_create(
        "camera", NETATMO_DOMAIN, "5678", device_id=device_entry.id
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
                        "entity_id": f"camera.{NETATMO_DOMAIN}_5678",
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

    device = device_reg.async_get_device(set(), {connection})
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
