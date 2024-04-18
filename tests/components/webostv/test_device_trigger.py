"""The tests for WebOS TV device triggers."""

import pytest

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.webostv import DOMAIN, device_trigger
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import async_get as get_dev_reg
from homeassistant.setup import async_setup_component

from . import setup_webostv
from .const import ENTITY_ID, FAKE_UUID

from tests.common import MockConfigEntry, async_get_device_automations


async def test_get_triggers(hass: HomeAssistant, client) -> None:
    """Test we get the expected triggers."""
    await setup_webostv(hass)

    device_reg = get_dev_reg(hass)
    device = device_reg.async_get_device(identifiers={(DOMAIN, FAKE_UUID)})

    turn_on_trigger = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "webostv.turn_on",
        "device_id": device.id,
        "metadata": {},
    }

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert turn_on_trigger in triggers


async def test_if_fires_on_turn_on_request(hass: HomeAssistant, calls, client) -> None:
    """Test for turn_on and turn_off triggers firing."""
    await setup_webostv(hass)

    device_reg = get_dev_reg(hass)
    device = device_reg.async_get_device(identifiers={(DOMAIN, FAKE_UUID)})

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
                        "type": "webostv.turn_on",
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
                        "platform": "webostv.turn_on",
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
        "media_player",
        "turn_on",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[0].data["some"] == device.id
    assert calls[0].data["id"] == 0
    assert calls[1].data["some"] == ENTITY_ID
    assert calls[1].data["id"] == 0


async def test_failure_scenarios(hass: HomeAssistant, client) -> None:
    """Test failure scenarios."""
    await setup_webostv(hass)

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
                "type": "webostv.turn_on",
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
        "type": "webostv.turn_on",
    }

    # Test that device id from non webostv domain raises exception
    with pytest.raises(InvalidDeviceAutomationConfig):
        await device_trigger.async_validate_trigger_config(hass, config)
