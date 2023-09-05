"""The tests for RoonLabs music player device triggers."""
import pytest
from pytest_unordered import unordered

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.roon import DOMAIN
from homeassistant.components.roon.const import ROON_EVENT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    async_get_device_automations,
    async_mock_service,
)

UP_MESSAGE = {"message": "up"}
DOWN_MESSAGE = {"message": "down"}

entity_id = f"{DOMAIN}.test_5678"


@pytest.fixture
def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def setup_automation(hass, device_id, trigger_type):
    """Set up an automation trigger for testing triggering."""
    return await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_id,
                        "entity_id": entity_id,
                        "type": "volume_up",
                    },
                    "action": {
                        "service": "test.automation",
                        "data": UP_MESSAGE,
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_id,
                        "entity_id": entity_id,
                        "type": "volume_down",
                    },
                    "action": {
                        "service": "test.automation",
                        "data": DOWN_MESSAGE,
                    },
                },
            ]
        },
    )


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected triggers from roon."""
    config_entry = MockConfigEntry(domain="test", data={"roon_volume_hooks": True})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "volume_up",
            "device_id": device_entry.id,
            "entity_id": entity_id,
            "metadata": {"secondary": False},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "volume_down",
            "device_id": device_entry.id,
            "entity_id": entity_id,
            "metadata": {"secondary": False},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


async def test_events_fire_triggers(hass: HomeAssistant) -> None:
    """Test that sending roon volume events event fires the right triggers."""

    assert await setup_automation(hass, "mock-device-id", "volume_up")
    calls = async_mock_service(hass, "test", "automation")

    hass.bus.async_fire(
        ROON_EVENT,
        {
            "entity_id": entity_id,
            "type": "volume_up",
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data == UP_MESSAGE

    hass.bus.async_fire(
        ROON_EVENT,
        {
            "entity_id": entity_id,
            "type": "volume_down",
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[0].data == UP_MESSAGE
    assert calls[1].data == DOWN_MESSAGE
