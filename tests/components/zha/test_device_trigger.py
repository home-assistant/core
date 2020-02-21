"""ZHA device automation trigger tests."""
import pytest
import zigpy.zcl.clusters.general as general

import homeassistant.components.automation as automation
from homeassistant.helpers.device_registry import async_get_registry
from homeassistant.setup import async_setup_component

from tests.common import async_get_device_automations, async_mock_service

ON = 1
OFF = 0
SHAKEN = "device_shaken"
COMMAND = "command"
COMMAND_SHAKE = "shake"
COMMAND_HOLD = "hold"
COMMAND_SINGLE = "single"
COMMAND_DOUBLE = "double"
DOUBLE_PRESS = "remote_button_double_press"
SHORT_PRESS = "remote_button_short_press"
LONG_PRESS = "remote_button_long_press"
LONG_RELEASE = "remote_button_long_release"


def _same_lists(list_a, list_b):
    if len(list_a) != len(list_b):
        return False

    for item in list_a:
        if item not in list_b:
            return False
    return True


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture
async def mock_devices(hass, zigpy_device_mock, zha_device_joined_restored):
    """IAS device fixture."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [general.Basic.cluster_id],
                "out_clusters": [general.OnOff.cluster_id],
                "device_type": 0,
            }
        },
    )

    zha_device = await zha_device_joined_restored(zigpy_device)
    zha_device.update_available(True)
    await hass.async_block_till_done()
    return zigpy_device, zha_device


async def test_triggers(hass, mock_devices):
    """Test zha device triggers."""

    zigpy_device, zha_device = mock_devices

    zigpy_device.device_automation_triggers = {
        (SHAKEN, SHAKEN): {COMMAND: COMMAND_SHAKE},
        (DOUBLE_PRESS, DOUBLE_PRESS): {COMMAND: COMMAND_DOUBLE},
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE},
        (LONG_PRESS, LONG_PRESS): {COMMAND: COMMAND_HOLD},
        (LONG_RELEASE, LONG_RELEASE): {COMMAND: COMMAND_HOLD},
    }

    ieee_address = str(zha_device.ieee)

    ha_device_registry = await async_get_registry(hass)
    reg_device = ha_device_registry.async_get_device({("zha", ieee_address)}, set())

    triggers = await async_get_device_automations(hass, "trigger", reg_device.id)

    expected_triggers = [
        {
            "device_id": reg_device.id,
            "domain": "zha",
            "platform": "device",
            "type": SHAKEN,
            "subtype": SHAKEN,
        },
        {
            "device_id": reg_device.id,
            "domain": "zha",
            "platform": "device",
            "type": DOUBLE_PRESS,
            "subtype": DOUBLE_PRESS,
        },
        {
            "device_id": reg_device.id,
            "domain": "zha",
            "platform": "device",
            "type": SHORT_PRESS,
            "subtype": SHORT_PRESS,
        },
        {
            "device_id": reg_device.id,
            "domain": "zha",
            "platform": "device",
            "type": LONG_PRESS,
            "subtype": LONG_PRESS,
        },
        {
            "device_id": reg_device.id,
            "domain": "zha",
            "platform": "device",
            "type": LONG_RELEASE,
            "subtype": LONG_RELEASE,
        },
    ]
    assert _same_lists(triggers, expected_triggers)


async def test_no_triggers(hass, mock_devices):
    """Test zha device with no triggers."""

    _, zha_device = mock_devices
    ieee_address = str(zha_device.ieee)

    ha_device_registry = await async_get_registry(hass)
    reg_device = ha_device_registry.async_get_device({("zha", ieee_address)}, set())

    triggers = await async_get_device_automations(hass, "trigger", reg_device.id)
    assert triggers == []


async def test_if_fires_on_event(hass, mock_devices, calls):
    """Test for remote triggers firing."""

    zigpy_device, zha_device = mock_devices

    zigpy_device.device_automation_triggers = {
        (SHAKEN, SHAKEN): {COMMAND: COMMAND_SHAKE},
        (DOUBLE_PRESS, DOUBLE_PRESS): {COMMAND: COMMAND_DOUBLE},
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE},
        (LONG_PRESS, LONG_PRESS): {COMMAND: COMMAND_HOLD},
        (LONG_RELEASE, LONG_RELEASE): {COMMAND: COMMAND_HOLD},
    }

    ieee_address = str(zha_device.ieee)
    ha_device_registry = await async_get_registry(hass)
    reg_device = ha_device_registry.async_get_device({("zha", ieee_address)}, set())

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "device_id": reg_device.id,
                        "domain": "zha",
                        "platform": "device",
                        "type": SHORT_PRESS,
                        "subtype": SHORT_PRESS,
                    },
                    "action": {
                        "service": "test.automation",
                        "data": {"message": "service called"},
                    },
                }
            ]
        },
    )

    await hass.async_block_till_done()

    channel = zha_device.channels.pools[0].relay_channels["1:0x0006"]
    channel.zha_send_event(COMMAND_SINGLE, [])
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["message"] == "service called"


async def test_exception_no_triggers(hass, mock_devices, calls, caplog):
    """Test for exception on event triggers firing."""

    _, zha_device = mock_devices

    ieee_address = str(zha_device.ieee)
    ha_device_registry = await async_get_registry(hass)
    reg_device = ha_device_registry.async_get_device({("zha", ieee_address)}, set())

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "device_id": reg_device.id,
                        "domain": "zha",
                        "platform": "device",
                        "type": "junk",
                        "subtype": "junk",
                    },
                    "action": {
                        "service": "test.automation",
                        "data": {"message": "service called"},
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert "Invalid config for [automation]" in caplog.text


async def test_exception_bad_trigger(hass, mock_devices, calls, caplog):
    """Test for exception on event triggers firing."""

    zigpy_device, zha_device = mock_devices

    zigpy_device.device_automation_triggers = {
        (SHAKEN, SHAKEN): {COMMAND: COMMAND_SHAKE},
        (DOUBLE_PRESS, DOUBLE_PRESS): {COMMAND: COMMAND_DOUBLE},
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE},
        (LONG_PRESS, LONG_PRESS): {COMMAND: COMMAND_HOLD},
        (LONG_RELEASE, LONG_RELEASE): {COMMAND: COMMAND_HOLD},
    }

    ieee_address = str(zha_device.ieee)
    ha_device_registry = await async_get_registry(hass)
    reg_device = ha_device_registry.async_get_device({("zha", ieee_address)}, set())

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "device_id": reg_device.id,
                        "domain": "zha",
                        "platform": "device",
                        "type": "junk",
                        "subtype": "junk",
                    },
                    "action": {
                        "service": "test.automation",
                        "data": {"message": "service called"},
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert "Invalid config for [automation]" in caplog.text
