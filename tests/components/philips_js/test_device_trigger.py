"""The tests for Philips TV device triggers."""

import pytest
from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.philips_js.const import DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.common import async_get_device_automations


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


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
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    mock_tv,
    mock_entity,
    mock_device,
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
    assert len(service_calls) == 2
    assert service_calls[0].domain == "media_player"
    assert service_calls[0].service == "turn_on"
    assert service_calls[1].domain == "test"
    assert service_calls[1].service == "automation"
    assert service_calls[1].data["some"] == mock_device.id
    assert service_calls[1].data["id"] == 0
