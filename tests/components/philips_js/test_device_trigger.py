"""The tests for Philips TV device triggers."""
import pytest
from pytest_unordered import unordered

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.philips_js.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_get_device_automations, async_mock_service


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(hass: HomeAssistant, mock_device) -> None:
    """Test we get the expected triggers."""
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "turn_on",
            "device_id": mock_device.id,
            "metadata": {},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, mock_device.id
    )
    triggers = [trigger for trigger in triggers if trigger["domain"] == DOMAIN]
    assert triggers == unordered(expected_triggers)


async def test_if_fires_on_turn_on_request(
    hass: HomeAssistant, calls, mock_tv, mock_entity, mock_device
) -> None:
    """Test for turn_on and turn_off triggers firing."""

    mock_tv.on = False

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": mock_device.id,
                        "type": "turn_on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "{{ trigger.device_id }}",
                            "id": "{{ trigger.id}}",
                        },
                    },
                }
            ]
        },
    )

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": mock_entity},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == mock_device.id
    assert calls[0].data["id"] == 0
