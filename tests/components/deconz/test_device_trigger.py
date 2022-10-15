"""deCONZ device automation tests."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.binary_sensor.device_trigger import (
    CONF_BAT_LOW,
    CONF_NOT_BAT_LOW,
    CONF_NOT_TAMPERED,
    CONF_TAMPERED,
)
from homeassistant.components.deconz import device_trigger
from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
from homeassistant.components.deconz.device_trigger import CONF_SUBTYPE
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import async_initialize_triggers
from homeassistant.setup import async_setup_component

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

from tests.common import (
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
)
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


@pytest.fixture
def automation_calls(hass):
    """Track automation calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(hass, aioclient_mock):
    """Test triggers work."""
    data = {
        "sensors": {
            "1": {
                "config": {
                    "alert": "none",
                    "battery": 60,
                    "group": "10",
                    "on": True,
                    "reachable": True,
                },
                "ep": 1,
                "etag": "1b355c0b6d2af28febd7ca9165881952",
                "manufacturername": "IKEA of Sweden",
                "mode": 1,
                "modelid": "TRADFRI on/off switch",
                "name": "TRÅDFRI on/off switch ",
                "state": {"buttonevent": 2002, "lastupdated": "2019-09-07T07:39:39"},
                "swversion": "1.4.018",
                "type": "ZHASwitch",
                "uniqueid": "d0:cf:5e:ff:fe:71:a4:3a-01-1000",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "d0:cf:5e:ff:fe:71:a4:3a")}
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )

    expected_triggers = [
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DECONZ_DOMAIN,
            CONF_PLATFORM: "device",
            CONF_TYPE: device_trigger.CONF_SHORT_PRESS,
            CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
            "metadata": {},
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DECONZ_DOMAIN,
            CONF_PLATFORM: "device",
            CONF_TYPE: device_trigger.CONF_LONG_PRESS,
            CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
            "metadata": {},
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DECONZ_DOMAIN,
            CONF_PLATFORM: "device",
            CONF_TYPE: device_trigger.CONF_LONG_RELEASE,
            CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
            "metadata": {},
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DECONZ_DOMAIN,
            CONF_PLATFORM: "device",
            CONF_TYPE: device_trigger.CONF_SHORT_PRESS,
            CONF_SUBTYPE: device_trigger.CONF_TURN_OFF,
            "metadata": {},
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DECONZ_DOMAIN,
            CONF_PLATFORM: "device",
            CONF_TYPE: device_trigger.CONF_LONG_PRESS,
            CONF_SUBTYPE: device_trigger.CONF_TURN_OFF,
            "metadata": {},
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DECONZ_DOMAIN,
            CONF_PLATFORM: "device",
            CONF_TYPE: device_trigger.CONF_LONG_RELEASE,
            CONF_SUBTYPE: device_trigger.CONF_TURN_OFF,
            "metadata": {},
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: SENSOR_DOMAIN,
            ATTR_ENTITY_ID: "sensor.tradfri_on_off_switch_battery",
            CONF_PLATFORM: "device",
            CONF_TYPE: ATTR_BATTERY_LEVEL,
            "metadata": {"secondary": True},
        },
    ]

    assert_lists_same(triggers, expected_triggers)


async def test_get_triggers_for_alarm_event(hass, aioclient_mock):
    """Test triggers work."""
    data = {
        "sensors": {
            "1": {
                "config": {
                    "battery": 95,
                    "enrolled": 1,
                    "on": True,
                    "pending": [],
                    "reachable": True,
                },
                "ep": 1,
                "etag": "5aaa1c6bae8501f59929539c6e8f44d6",
                "lastseen": "2021-07-25T18:07Z",
                "manufacturername": "lk",
                "modelid": "ZB-KeypadGeneric-D0002",
                "name": "Keypad",
                "state": {
                    "action": "armed_stay",
                    "lastupdated": "2021-07-25T18:02:51.172",
                    "lowbattery": False,
                    "panel": "exit_delay",
                    "seconds_remaining": 55,
                    "tampered": False,
                },
                "swversion": "3.13",
                "type": "ZHAAncillaryControl",
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "00:00:00:00:00:00:00:00")}
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )

    expected_triggers = [
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: BINARY_SENSOR_DOMAIN,
            ATTR_ENTITY_ID: "binary_sensor.keypad_low_battery",
            CONF_PLATFORM: "device",
            CONF_TYPE: CONF_BAT_LOW,
            "metadata": {"secondary": True},
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: BINARY_SENSOR_DOMAIN,
            ATTR_ENTITY_ID: "binary_sensor.keypad_low_battery",
            CONF_PLATFORM: "device",
            CONF_TYPE: CONF_NOT_BAT_LOW,
            "metadata": {"secondary": True},
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: BINARY_SENSOR_DOMAIN,
            ATTR_ENTITY_ID: "binary_sensor.keypad_tampered",
            CONF_PLATFORM: "device",
            CONF_TYPE: CONF_TAMPERED,
            "metadata": {"secondary": True},
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: BINARY_SENSOR_DOMAIN,
            ATTR_ENTITY_ID: "binary_sensor.keypad_tampered",
            CONF_PLATFORM: "device",
            CONF_TYPE: CONF_NOT_TAMPERED,
            "metadata": {"secondary": True},
        },
        {
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: SENSOR_DOMAIN,
            ATTR_ENTITY_ID: "sensor.keypad_battery",
            CONF_PLATFORM: "device",
            CONF_TYPE: ATTR_BATTERY_LEVEL,
            "metadata": {"secondary": True},
        },
    ]

    assert_lists_same(triggers, expected_triggers)


async def test_get_triggers_manage_unsupported_remotes(hass, aioclient_mock):
    """Verify no triggers for an unsupported remote."""
    data = {
        "sensors": {
            "1": {
                "config": {
                    "alert": "none",
                    "group": "10",
                    "on": True,
                    "reachable": True,
                },
                "ep": 1,
                "etag": "1b355c0b6d2af28febd7ca9165881952",
                "manufacturername": "IKEA of Sweden",
                "mode": 1,
                "modelid": "Unsupported model",
                "name": "TRÅDFRI on/off switch ",
                "state": {"buttonevent": 2002, "lastupdated": "2019-09-07T07:39:39"},
                "swversion": "1.4.018",
                "type": "ZHASwitch",
                "uniqueid": "d0:cf:5e:ff:fe:71:a4:3a-01-1000",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "d0:cf:5e:ff:fe:71:a4:3a")}
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )

    expected_triggers = []

    assert_lists_same(triggers, expected_triggers)


async def test_functional_device_trigger(
    hass, aioclient_mock, mock_deconz_websocket, automation_calls
):
    """Test proper matching and attachment of device trigger automation."""

    data = {
        "sensors": {
            "1": {
                "config": {
                    "alert": "none",
                    "battery": 60,
                    "group": "10",
                    "on": True,
                    "reachable": True,
                },
                "ep": 1,
                "etag": "1b355c0b6d2af28febd7ca9165881952",
                "manufacturername": "IKEA of Sweden",
                "mode": 1,
                "modelid": "TRADFRI on/off switch",
                "name": "TRÅDFRI on/off switch ",
                "state": {"buttonevent": 2002, "lastupdated": "2019-09-07T07:39:39"},
                "swversion": "1.4.018",
                "type": "ZHASwitch",
                "uniqueid": "d0:cf:5e:ff:fe:71:a4:3a-01-1000",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "d0:cf:5e:ff:fe:71:a4:3a")}
    )

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DECONZ_DOMAIN,
                        CONF_DEVICE_ID: device.id,
                        CONF_TYPE: device_trigger.CONF_SHORT_PRESS,
                        CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )

    assert len(hass.states.async_entity_ids(AUTOMATION_DOMAIN)) == 1

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "state": {"buttonevent": 1002},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert len(automation_calls) == 1
    assert automation_calls[0].data["some"] == "test_trigger_button_press"


async def test_validate_trigger_unknown_device(hass, aioclient_mock):
    """Test unknown device does not return a trigger config."""
    await setup_deconz_integration(hass, aioclient_mock)

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DECONZ_DOMAIN,
                        CONF_DEVICE_ID: "unknown device",
                        CONF_TYPE: device_trigger.CONF_SHORT_PRESS,
                        CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(AUTOMATION_DOMAIN)) == 0


async def test_validate_trigger_unsupported_device(hass, aioclient_mock):
    """Test unsupported device doesn't return a trigger config."""
    config_entry = await setup_deconz_integration(hass, aioclient_mock)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DECONZ_DOMAIN, "d0:cf:5e:ff:fe:71:a4:3a")},
        model="unsupported",
    )

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DECONZ_DOMAIN,
                        CONF_DEVICE_ID: device.id,
                        CONF_TYPE: device_trigger.CONF_SHORT_PRESS,
                        CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(AUTOMATION_DOMAIN)) == 0


async def test_validate_trigger_unsupported_trigger(hass, aioclient_mock):
    """Test unsupported trigger does not return a trigger config."""
    config_entry = await setup_deconz_integration(hass, aioclient_mock)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DECONZ_DOMAIN, "d0:cf:5e:ff:fe:71:a4:3a")},
        model="TRADFRI on/off switch",
    )

    trigger_config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DECONZ_DOMAIN,
        CONF_DEVICE_ID: device.id,
        CONF_TYPE: "unsupported",
        CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
    }

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "trigger": trigger_config,
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(AUTOMATION_DOMAIN)) == 0


async def test_attach_trigger_no_matching_event(hass, aioclient_mock):
    """Test no matching event for device doesn't return a trigger config."""
    config_entry = await setup_deconz_integration(hass, aioclient_mock)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DECONZ_DOMAIN, "d0:cf:5e:ff:fe:71:a4:3a")},
        name="Tradfri switch",
        model="TRADFRI on/off switch",
    )

    trigger_config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DECONZ_DOMAIN,
        CONF_DEVICE_ID: device.id,
        CONF_TYPE: device_trigger.CONF_SHORT_PRESS,
        CONF_SUBTYPE: device_trigger.CONF_TURN_ON,
    }

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "trigger": trigger_config,
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(AUTOMATION_DOMAIN)) == 1

    # Assert that deCONZ async_attach_trigger raises InvalidDeviceAutomationConfig
    assert not await async_initialize_triggers(
        hass,
        [trigger_config],
        action=Mock(),
        domain=AUTOMATION_DOMAIN,
        name="mock-name",
        log_cb=Mock(),
    )
