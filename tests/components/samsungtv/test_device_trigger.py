"""The tests for Samsung TV device triggers."""

import pytest

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.samsungtv import device_trigger
from homeassistant.components.samsungtv.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import setup_samsungtv_entry
from .const import ENTRYDATA_ENCRYPTED_WEBSOCKET

from tests.common import MockConfigEntry, async_get_device_automations


@pytest.mark.usefixtures("remote_encrypted_websocket", "rest_api")
async def test_get_triggers(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test we get the expected triggers."""
    await setup_samsungtv_entry(hass, ENTRYDATA_ENCRYPTED_WEBSOCKET)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "be9554b9-c9fb-41f4-8920-22da015376a4")}
    )

    turn_on_trigger = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "samsungtv.turn_on",
        "device_id": device.id,
        "metadata": {},
    }

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert turn_on_trigger in triggers


@pytest.mark.usefixtures("remote_encrypted_websocket", "rest_api")
async def test_if_fires_on_turn_on_request(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test for turn_on and turn_off triggers firing."""
    await setup_samsungtv_entry(hass, ENTRYDATA_ENCRYPTED_WEBSOCKET)
    entity_id = "media_player.mock_title"

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "be9554b9-c9fb-41f4-8920-22da015376a4")}
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
                        "device_id": device.id,
                        "type": "samsungtv.turn_on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "{{ trigger.device_id }}",
                            "id": "{{ trigger.id }}",
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "samsungtv.turn_on",
                        "entity_id": entity_id,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": entity_id,
                            "id": "{{ trigger.id }}",
                        },
                    },
                },
            ],
        },
    )

    await hass.services.async_call(
        "media_player", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 3
    assert service_calls[1].data["some"] == device.id
    assert service_calls[1].data["id"] == 0
    assert service_calls[2].data["some"] == entity_id
    assert service_calls[2].data["id"] == 0


@pytest.mark.usefixtures("remote_encrypted_websocket", "rest_api")
async def test_failure_scenarios(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test failure scenarios."""
    await setup_samsungtv_entry(hass, ENTRYDATA_ENCRYPTED_WEBSOCKET)

    # Test wrong trigger platform type
    with pytest.raises(HomeAssistantError):
        await device_trigger.async_attach_trigger(
            hass, {"type": "wrong.type", "device_id": "invalid_device_id"}, None, {}
        )

    # Test invalid device id
    with pytest.raises(InvalidDeviceAutomationConfig):
        await device_trigger.async_validate_trigger_config(
            hass,
            {
                "platform": "device",
                "domain": DOMAIN,
                "type": "samsungtv.turn_on",
                "device_id": "invalid_device_id",
            },
        )

    entry = MockConfigEntry(domain="fake", state=ConfigEntryState.LOADED, data={})
    entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("fake", "fake")}
    )

    config = {
        "platform": "device",
        "domain": DOMAIN,
        "device_id": device.id,
        "type": "samsungtv.turn_on",
    }

    # Test that device id from non samsungtv domain raises exception
    with pytest.raises(InvalidDeviceAutomationConfig):
        await device_trigger.async_validate_trigger_config(hass, config)
