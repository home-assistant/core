"""The tests for Philips Hue device triggers."""
import pytest

from homeassistant.components import hue
import homeassistant.components.automation as automation
from homeassistant.components.hue import device_trigger
from homeassistant.setup import async_setup_component

from .conftest import setup_bridge_for_sensors as setup_bridge
from .test_sensor_base import HUE_DIMMER_REMOTE_1, HUE_TAP_REMOTE_1

from tests.common import (
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
)

REMOTES_RESPONSE = {"7": HUE_TAP_REMOTE_1, "8": HUE_DIMMER_REMOTE_1}


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(hass, mock_bridge, device_reg):
    """Test we get the expected triggers from a hue remote."""
    mock_bridge.mock_sensor_responses.append(REMOTES_RESPONSE)
    await setup_bridge(hass, mock_bridge)

    assert len(mock_bridge.mock_requests) == 1
    # 2 remotes, just 1 battery sensor
    assert len(hass.states.async_all()) == 1

    # Get triggers for specific tap switch
    hue_tap_device = device_reg.async_get_device(
        {(hue.DOMAIN, "00:00:00:00:00:44:23:08")}, connections={}
    )
    triggers = await async_get_device_automations(hass, "trigger", hue_tap_device.id)

    expected_triggers = [
        {
            "platform": "device",
            "domain": hue.DOMAIN,
            "device_id": hue_tap_device.id,
            "type": t_type,
            "subtype": t_subtype,
        }
        for t_type, t_subtype in device_trigger.HUE_TAP_REMOTE.keys()
    ]
    assert_lists_same(triggers, expected_triggers)

    # Get triggers for specific dimmer switch
    hue_dimmer_device = device_reg.async_get_device(
        {(hue.DOMAIN, "00:17:88:01:10:3e:3a:dc")}, connections={}
    )
    triggers = await async_get_device_automations(hass, "trigger", hue_dimmer_device.id)

    trigger_batt = {
        "platform": "device",
        "domain": "sensor",
        "device_id": hue_dimmer_device.id,
        "type": "battery_level",
        "entity_id": "sensor.hue_dimmer_switch_1_battery_level",
    }
    expected_triggers = [
        trigger_batt,
        *[
            {
                "platform": "device",
                "domain": hue.DOMAIN,
                "device_id": hue_dimmer_device.id,
                "type": t_type,
                "subtype": t_subtype,
            }
            for t_type, t_subtype in device_trigger.HUE_DIMMER_REMOTE.keys()
        ],
    ]
    assert_lists_same(triggers, expected_triggers)


async def test_if_fires_on_state_change(hass, mock_bridge, device_reg, calls):
    """Test for button press trigger firing."""
    mock_bridge.mock_sensor_responses.append(REMOTES_RESPONSE)
    await setup_bridge(hass, mock_bridge)
    assert len(mock_bridge.mock_requests) == 1
    assert len(hass.states.async_all()) == 1

    # Set an automation with a specific tap switch trigger
    hue_tap_device = device_reg.async_get_device(
        {(hue.DOMAIN, "00:00:00:00:00:44:23:08")}, connections={}
    )
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": hue.DOMAIN,
                        "device_id": hue_tap_device.id,
                        "type": "remote_button_short_press",
                        "subtype": "button_4",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "B4 - {{ trigger.event.data.event }}"
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": hue.DOMAIN,
                        "device_id": "mock-device-id",
                        "type": "remote_button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "B1 - {{ trigger.event.data.event }}"
                        },
                    },
                },
            ]
        },
    )

    # Fake that the remote is being pressed.
    new_sensor_response = dict(REMOTES_RESPONSE)
    new_sensor_response["7"]["state"] = {
        "buttonevent": 18,
        "lastupdated": "2019-12-28T22:58:02",
    }
    mock_bridge.mock_sensor_responses.append(new_sensor_response)

    # Force updates to run again
    await mock_bridge.sensor_manager.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert len(mock_bridge.mock_requests) == 2

    assert len(calls) == 1
    assert calls[0].data["some"] == "B4 - 18"

    # Fake another button press.
    new_sensor_response = dict(REMOTES_RESPONSE)
    new_sensor_response["7"]["state"] = {
        "buttonevent": 34,
        "lastupdated": "2019-12-28T22:58:05",
    }
    mock_bridge.mock_sensor_responses.append(new_sensor_response)

    # Force updates to run again
    await mock_bridge.sensor_manager.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert len(mock_bridge.mock_requests) == 3
    assert len(calls) == 1
