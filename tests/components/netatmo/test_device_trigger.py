"""The tests for Netatmo device triggers."""
import pytest

from homeassistant.components.netatmo import (
    DOMAIN as NETATMO_DOMAIN,
    const as netatmo_const,
)
from homeassistant.helpers import device_registry

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
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


async def test_get_triggers_camera_indoor(hass, device_reg, entity_reg):
    """Test we get the expected triggers from a netatmo."""
    config_entry = MockConfigEntry(domain=NETATMO_DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        model=netatmo_const.MODEL_NACAMERA,
    )
    entity_reg.async_get_or_create(
        "camera", NETATMO_DOMAIN, "5678", device_id=device_entry.id
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": NETATMO_DOMAIN,
            "type": "person",
            "device_id": device_entry.id,
            "entity_id": f"camera.{NETATMO_DOMAIN}_5678",
        },
        {
            "platform": "device",
            "domain": NETATMO_DOMAIN,
            "type": "person_away",
            "device_id": device_entry.id,
            "entity_id": f"camera.{NETATMO_DOMAIN}_5678",
        },
        {
            "platform": "device",
            "domain": NETATMO_DOMAIN,
            "type": "movement",
            "device_id": device_entry.id,
            "entity_id": f"camera.{NETATMO_DOMAIN}_5678",
        },
    ]
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, expected_triggers)


async def test_get_triggers_camera_outdoor(hass, device_reg, entity_reg):
    """Test we get the expected triggers from a netatmo."""
    config_entry = MockConfigEntry(domain=NETATMO_DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        model=netatmo_const.MODEL_NOC,
    )
    entity_reg.async_get_or_create(
        "camera", NETATMO_DOMAIN, "5678", device_id=device_entry.id
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": NETATMO_DOMAIN,
            "type": "animal",
            "device_id": device_entry.id,
            "entity_id": f"camera.{NETATMO_DOMAIN}_5678",
        },
        {
            "platform": "device",
            "domain": NETATMO_DOMAIN,
            "type": "human",
            "device_id": device_entry.id,
            "entity_id": f"camera.{NETATMO_DOMAIN}_5678",
        },
        {
            "platform": "device",
            "domain": NETATMO_DOMAIN,
            "type": "vehicle",
            "device_id": device_entry.id,
            "entity_id": f"camera.{NETATMO_DOMAIN}_5678",
        },
        {
            "platform": "device",
            "domain": NETATMO_DOMAIN,
            "type": "outdoor",
            "device_id": device_entry.id,
            "entity_id": f"camera.{NETATMO_DOMAIN}_5678",
        },
    ]
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, expected_triggers)
