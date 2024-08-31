"""The tests for Samsung TV device triggers."""
import pytest

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.samsungtv import DOMAIN, device_trigger
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import async_get as get_dev_reg
from homeassistant.setup import async_setup_component

from . import setup_samsungtv_entry
from .test_media_player import ENTITY_ID, MOCK_ENTRYDATA_ENCRYPTED_WS

from tests.common import MockConfigEntry, async_get_device_automations


@pytest.mark.usefixtures("remoteencws", "rest_api")
async def test_get_triggers(hass: HomeAssistant) -> None:
    """Test we get the expected triggers."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

    device_reg = get_dev_reg(hass)
    device = device_reg.async_get_device(identifiers={(DOMAIN, "any")})

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


@pytest.mark.usefixtures("remoteencws", "rest_api")
async def test_if_fires_on_turn_on_request(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for turn_on and turn_off triggers firing."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

    device_reg = get_dev_reg(hass)
    device = device_reg.async_get_device(identifiers={(DOMAIN, "any")})

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
                        "entity_id": ENTITY_ID,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": ENTITY_ID,
                            "id": "{{ trigger.id }}",
                        },
                    },
                },
            ],
        },
    )

    await hass.services.async_call(
        "media_player", "turn_on", {"entity_id": ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()

    assert len(calls) == 2
    assert calls[0].data["some"] == device.id
    assert calls[0].data["id"] == 0
    assert calls[1].data["some"] == ENTITY_ID
    assert calls[1].data["id"] == 0


@pytest.mark.usefixtures("remoteencws", "rest_api")
async def test_failure_scenarios(hass: HomeAssistant) -> None:
    """Test failure scenarios."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

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
    device_reg = get_dev_reg(hass)

    device = device_reg.async_get_or_create(
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
