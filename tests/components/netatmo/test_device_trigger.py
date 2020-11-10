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


@pytest.mark.parametrize(
    "camera_type,event_types",
    [
        (netatmo_const.MODEL_NOC, ["animal", "human", "vehicle", "outdoor"]),
        (
            netatmo_const.MODEL_NACAMERA,
            [
                "person",
                "person_away",
                "movement",
            ],
        ),
    ],
)
async def test_get_triggers_camera(
    hass, device_reg, entity_reg, camera_type, event_types
):
    """Test we get the expected triggers from a netatmo."""
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
