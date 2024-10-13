"""ZHA logbook describe events tests."""

from unittest.mock import patch

import pytest
from zha.application.const import ZHA_EVENT
import zigpy.profiles.zha
from zigpy.zcl.clusters import general

from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_UNIQUE_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

from tests.components.logbook.common import MockRow, mock_humanify

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
UP = "up"
DOWN = "down"


@pytest.fixture(autouse=True)
def sensor_platform_only():
    """Only set up the sensor and required base platforms to speed up tests."""
    with patch("homeassistant.components.zha.PLATFORMS", (Platform.SENSOR,)):
        yield


@pytest.fixture
async def mock_devices(hass: HomeAssistant, setup_zha, zigpy_device_mock):
    """IAS device fixture."""

    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.Basic.cluster_id],
                SIG_EP_OUTPUT: [general.OnOff.cluster_id],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zigpy.profiles.zha.PROFILE_ID,
            }
        }
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)

    return zigpy_device, zha_device_proxy


async def test_zha_logbook_event_device_with_triggers(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, mock_devices
) -> None:
    """Test ZHA logbook events with device and triggers."""

    zigpy_device, zha_device = mock_devices

    zigpy_device.device_automation_triggers = {
        (SHAKEN, SHAKEN): {COMMAND: COMMAND_SHAKE},
        (UP, DOUBLE_PRESS): {COMMAND: COMMAND_DOUBLE, "endpoint_id": 1},
        (DOWN, DOUBLE_PRESS): {COMMAND: COMMAND_DOUBLE, "endpoint_id": 2},
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE},
        (LONG_PRESS, LONG_PRESS): {COMMAND: COMMAND_HOLD},
        (LONG_RELEASE, LONG_RELEASE): {COMMAND: COMMAND_HOLD},
    }

    ieee_address = str(zha_device.device.ieee)

    reg_device = device_registry.async_get_device(identifiers={("zha", ieee_address)})

    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()

    events = mock_humanify(
        hass,
        [
            MockRow(
                ZHA_EVENT,
                {
                    CONF_DEVICE_ID: reg_device.id,
                    COMMAND: COMMAND_SHAKE,
                    "device_ieee": str(ieee_address),
                    CONF_UNIQUE_ID: f"{ieee_address!s}:1:0x0006",
                    "endpoint_id": 1,
                    "cluster_id": 6,
                    "params": {
                        "test": "test",
                    },
                },
            ),
            MockRow(
                ZHA_EVENT,
                {
                    CONF_DEVICE_ID: reg_device.id,
                    COMMAND: COMMAND_DOUBLE,
                    "device_ieee": str(ieee_address),
                    CONF_UNIQUE_ID: f"{ieee_address!s}:1:0x0006",
                    "endpoint_id": 1,
                    "cluster_id": 6,
                    "params": {
                        "test": "test",
                    },
                },
            ),
            MockRow(
                ZHA_EVENT,
                {
                    CONF_DEVICE_ID: reg_device.id,
                    COMMAND: COMMAND_DOUBLE,
                    "device_ieee": str(ieee_address),
                    CONF_UNIQUE_ID: f"{ieee_address!s}:1:0x0006",
                    "endpoint_id": 2,
                    "cluster_id": 6,
                    "params": {
                        "test": "test",
                    },
                },
            ),
        ],
    )

    assert events[0]["name"] == "FakeManufacturer FakeModel"
    assert events[0]["domain"] == "zha"
    assert (
        events[0]["message"]
        == "Device Shaken event was fired with parameters: {'test': 'test'}"
    )

    assert events[1]["name"] == "FakeManufacturer FakeModel"
    assert events[1]["domain"] == "zha"
    assert events[1]["message"] == (
        "Up - Remote Button Double Press event was fired with parameters: "
        "{'test': 'test'}"
    )


async def test_zha_logbook_event_device_no_triggers(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, mock_devices
) -> None:
    """Test ZHA logbook events with device and without triggers."""

    zigpy_device, zha_device = mock_devices
    ieee_address = str(zha_device.device.ieee)
    reg_device = device_registry.async_get_device(identifiers={("zha", ieee_address)})

    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()

    events = mock_humanify(
        hass,
        [
            MockRow(
                ZHA_EVENT,
                {
                    CONF_DEVICE_ID: reg_device.id,
                    COMMAND: COMMAND_SHAKE,
                    "device_ieee": str(ieee_address),
                    CONF_UNIQUE_ID: f"{ieee_address!s}:1:0x0006",
                    "endpoint_id": 1,
                    "cluster_id": 6,
                    "params": {
                        "test": "test",
                    },
                },
            ),
            MockRow(
                ZHA_EVENT,
                {
                    CONF_DEVICE_ID: reg_device.id,
                    "device_ieee": str(ieee_address),
                    CONF_UNIQUE_ID: f"{ieee_address!s}:1:0x0006",
                    "endpoint_id": 1,
                    "cluster_id": 6,
                    "params": {
                        "test": "test",
                    },
                },
            ),
            MockRow(
                ZHA_EVENT,
                {
                    CONF_DEVICE_ID: reg_device.id,
                    "device_ieee": str(ieee_address),
                    CONF_UNIQUE_ID: f"{ieee_address!s}:1:0x0006",
                    "endpoint_id": 1,
                    "cluster_id": 6,
                    "params": {},
                },
            ),
            MockRow(
                ZHA_EVENT,
                {
                    CONF_DEVICE_ID: reg_device.id,
                    "device_ieee": str(ieee_address),
                    CONF_UNIQUE_ID: f"{ieee_address!s}:1:0x0006",
                    "endpoint_id": 1,
                    "cluster_id": 6,
                },
            ),
        ],
    )

    assert events[0]["name"] == "FakeManufacturer FakeModel"
    assert events[0]["domain"] == "zha"
    assert (
        events[0]["message"]
        == "Shake event was fired with parameters: {'test': 'test'}"
    )

    assert events[1]["name"] == "FakeManufacturer FakeModel"
    assert events[1]["domain"] == "zha"
    assert (
        events[1]["message"] == "Zha Event was fired with parameters: {'test': 'test'}"
    )

    assert events[2]["name"] == "FakeManufacturer FakeModel"
    assert events[2]["domain"] == "zha"
    assert events[2]["message"] == "Zha Event was fired"

    assert events[3]["name"] == "FakeManufacturer FakeModel"
    assert events[3]["domain"] == "zha"
    assert events[3]["message"] == "Zha Event was fired"


async def test_zha_logbook_event_device_no_device(
    hass: HomeAssistant, mock_devices
) -> None:
    """Test ZHA logbook events without device and without triggers."""

    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()

    events = mock_humanify(
        hass,
        [
            MockRow(
                ZHA_EVENT,
                {
                    CONF_DEVICE_ID: "non-existing-device",
                    COMMAND: COMMAND_SHAKE,
                    "device_ieee": "90:fd:9f:ff:fe:fe:d8:a1",
                    CONF_UNIQUE_ID: "90:fd:9f:ff:fe:fe:d8:a1:1:0x0006",
                    "endpoint_id": 1,
                    "cluster_id": 6,
                    "params": {
                        "test": "test",
                    },
                },
            ),
        ],
    )

    assert events[0]["name"] == "Unknown device"
    assert events[0]["domain"] == "zha"
    assert (
        events[0]["message"]
        == "Shake event was fired with parameters: {'test': 'test'}"
    )
