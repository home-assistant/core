"""Verify that WeMo device triggers work as expected."""

import pytest
from pytest_unordered import unordered
from pywemo.subscribe import EVENT_TYPE_LONG_PRESS

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.wemo.const import DOMAIN, WEMO_SUBSCRIPTION_EVENT
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import async_get_device_automations, async_mock_service

DATA_MESSAGE = {"message": "service-called"}


@pytest.fixture
def pywemo_model():
    """Pywemo LightSwitch models use the switch platform."""
    return "LightSwitchLongPress"


async def setup_automation(
    hass: HomeAssistant, device_id: str, trigger_type: str
) -> None:
    """Set up an automation trigger for testing triggering."""
    return await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_TYPE: trigger_type,
                    },
                    "action": {
                        "service": "test.automation",
                        "data": DATA_MESSAGE,
                    },
                },
            ]
        },
    )


async def test_get_triggers(hass: HomeAssistant, wemo_entity) -> None:
    """Test that the triggers appear for a supported device."""
    assert wemo_entity.device_id is not None

    expected_triggers = [
        {
            CONF_DEVICE_ID: wemo_entity.device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_PLATFORM: "device",
            CONF_TYPE: EVENT_TYPE_LONG_PRESS,
            "metadata": {},
        },
        {
            CONF_DEVICE_ID: wemo_entity.device_id,
            CONF_DOMAIN: Platform.SWITCH,
            CONF_ENTITY_ID: wemo_entity.id,
            CONF_PLATFORM: "device",
            CONF_TYPE: "changed_states",
            "metadata": {"secondary": False},
        },
        {
            CONF_DEVICE_ID: wemo_entity.device_id,
            CONF_DOMAIN: Platform.SWITCH,
            CONF_ENTITY_ID: wemo_entity.id,
            CONF_PLATFORM: "device",
            CONF_TYPE: "turned_off",
            "metadata": {"secondary": False},
        },
        {
            CONF_DEVICE_ID: wemo_entity.device_id,
            CONF_DOMAIN: Platform.SWITCH,
            CONF_ENTITY_ID: wemo_entity.id,
            CONF_PLATFORM: "device",
            CONF_TYPE: "turned_on",
            "metadata": {"secondary": False},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, wemo_entity.device_id
    )
    assert triggers == unordered(expected_triggers)


async def test_fires_on_long_press(
    hass: HomeAssistant, wemo_entity: er.RegistryEntry
) -> None:
    """Test wemo long press trigger firing."""
    assert await setup_automation(hass, wemo_entity.device_id, EVENT_TYPE_LONG_PRESS)
    calls = async_mock_service(hass, "test", "automation")

    message = {CONF_DEVICE_ID: wemo_entity.device_id, CONF_TYPE: EVENT_TYPE_LONG_PRESS}
    hass.bus.async_fire(WEMO_SUBSCRIPTION_EVENT, message)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data == DATA_MESSAGE
