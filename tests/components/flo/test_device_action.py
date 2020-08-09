"""Tests for Flo device automation actions."""
from aioflo.location import SYSTEM_MODE_HOME

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import (
    _async_get_device_automations as async_get_device_automations,
)
from homeassistant.components.flo.const import DOMAIN as FLO_DOMAIN
from homeassistant.components.flo.device import FloDeviceDataUpdateCoordinator
from homeassistant.components.flo.services import (
    ATTR_DEVICE_ID,
    ATTR_LOCATION_ID,
    ATTR_REVERT_TO_MODE,
    ATTR_SLEEP_MINUTES,
    SERVICE_RUN_HEALTH_TEST,
    SERVICE_SET_AWAY_MODE,
    SERVICE_SET_HOME_MODE,
    SERVICE_SET_SLEEP_MODE,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.device_registry import async_get_registry
from homeassistant.setup import async_setup_component

from .common import TEST_PASSWORD, TEST_USER_ID

from tests.common import async_mock_service


async def test_get_actions(hass, config_entry, aioclient_mock_fixture):
    """Test we get the expected actions from a Flo device."""

    config_entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, FLO_DOMAIN, {CONF_USERNAME: TEST_USER_ID, CONF_PASSWORD: TEST_PASSWORD}
    )
    await hass.async_block_till_done()
    assert len(hass.data[FLO_DOMAIN]["devices"]) == 1

    device: FloDeviceDataUpdateCoordinator = hass.data[FLO_DOMAIN]["devices"][0]

    ha_device_registry = await async_get_registry(hass)
    reg_device = ha_device_registry.async_get_device({(FLO_DOMAIN, device.id)}, set())

    actions = await async_get_device_automations(hass, "action", reg_device.id)

    expected_actions = [
        {
            "domain": FLO_DOMAIN,
            "type": SERVICE_RUN_HEALTH_TEST,
            "device_id": reg_device.id,
        },
        {
            "domain": FLO_DOMAIN,
            "type": SERVICE_SET_AWAY_MODE,
            "device_id": reg_device.id,
        },
        {
            "domain": FLO_DOMAIN,
            "type": SERVICE_SET_HOME_MODE,
            "device_id": reg_device.id,
        },
        {
            "domain": FLO_DOMAIN,
            "type": SERVICE_SET_SLEEP_MODE,
            "device_id": reg_device.id,
        },
    ]

    assert actions == expected_actions


async def test_action(hass, config_entry, aioclient_mock_fixture):
    """Test for executing a zha device action."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, FLO_DOMAIN, {CONF_USERNAME: TEST_USER_ID, CONF_PASSWORD: TEST_PASSWORD}
    )
    await hass.async_block_till_done()
    assert len(hass.data[FLO_DOMAIN]["devices"]) == 1

    device: FloDeviceDataUpdateCoordinator = hass.data[FLO_DOMAIN]["devices"][0]

    ha_device_registry = await async_get_registry(hass)
    reg_device = ha_device_registry.async_get_device({(FLO_DOMAIN, device.id)}, set())

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "event_type": "test_event",
                        "platform": "event",
                        "event_data": {},
                    },
                    "action": {
                        "domain": FLO_DOMAIN,
                        "device_id": reg_device.id,
                        "type": SERVICE_RUN_HEALTH_TEST,
                    },
                },
                {
                    "trigger": {
                        "event_type": "test_event",
                        "platform": "event",
                        "event_data": {},
                    },
                    "action": {
                        "domain": FLO_DOMAIN,
                        "device_id": reg_device.id,
                        "type": SERVICE_SET_SLEEP_MODE,
                    },
                },
            ]
        },
    )

    await hass.async_block_till_done()
    calls = async_mock_service(hass, FLO_DOMAIN, SERVICE_RUN_HEALTH_TEST)
    calls2 = async_mock_service(hass, FLO_DOMAIN, SERVICE_SET_SLEEP_MODE)

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].domain == FLO_DOMAIN
    assert calls[0].service == SERVICE_RUN_HEALTH_TEST
    assert calls[0].data[ATTR_DEVICE_ID] == device.id

    assert len(calls2) == 1
    assert calls2[0].domain == FLO_DOMAIN
    assert calls2[0].service == SERVICE_SET_SLEEP_MODE
    assert calls2[0].data[ATTR_LOCATION_ID] == device.location_id
    assert calls2[0].data[ATTR_SLEEP_MINUTES] == 120
    assert calls2[0].data[ATTR_REVERT_TO_MODE] == SYSTEM_MODE_HOME

    # remove the Flo device and make sure we don't explode
    hass.data[FLO_DOMAIN]["devices"] = []
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
