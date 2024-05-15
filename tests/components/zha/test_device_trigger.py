"""ZHA device automation trigger tests."""

from datetime import timedelta
import time
from unittest.mock import patch

import pytest
from zigpy.application import ControllerApplication
import zigpy.profiles.zha
from zigpy.zcl.clusters import general

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.zha.core.const import ATTR_ENDPOINT_ID
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .common import async_enable_traffic
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_get_device_automations,
    async_mock_service,
)


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


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


SWITCH_SIGNATURE = {
    1: {
        SIG_EP_INPUT: [general.Basic.cluster_id],
        SIG_EP_OUTPUT: [general.OnOff.cluster_id],
        SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
        SIG_EP_PROFILE: zigpy.profiles.zha.PROFILE_ID,
    }
}


@pytest.fixture(autouse=True)
def sensor_platforms_only():
    """Only set up the sensor platform and required base platforms to speed up tests."""
    with patch("homeassistant.components.zha.PLATFORMS", (Platform.SENSOR,)):
        yield


def _same_lists(list_a, list_b):
    if len(list_a) != len(list_b):
        return False

    return all(item in list_b for item in list_a)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture
async def mock_devices(hass, zigpy_device_mock, zha_device_joined_restored):
    """IAS device fixture."""

    zigpy_device = zigpy_device_mock(SWITCH_SIGNATURE)

    zha_device = await zha_device_joined_restored(zigpy_device)
    zha_device.update_available(True)
    await hass.async_block_till_done()
    return zigpy_device, zha_device


async def test_triggers(hass: HomeAssistant, mock_devices) -> None:
    """Test ZHA device triggers."""

    zigpy_device, zha_device = mock_devices

    zigpy_device.device_automation_triggers = {
        (SHAKEN, SHAKEN): {COMMAND: COMMAND_SHAKE},
        (DOUBLE_PRESS, DOUBLE_PRESS): {COMMAND: COMMAND_DOUBLE},
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE},
        (LONG_PRESS, LONG_PRESS): {COMMAND: COMMAND_HOLD},
        (LONG_RELEASE, LONG_RELEASE): {COMMAND: COMMAND_HOLD},
    }

    ieee_address = str(zha_device.ieee)

    ha_device_registry = dr.async_get(hass)
    reg_device = ha_device_registry.async_get_device(
        identifiers={("zha", ieee_address)}
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, reg_device.id
    )

    expected_triggers = [
        {
            "device_id": reg_device.id,
            "domain": "zha",
            "platform": "device",
            "type": "device_offline",
            "subtype": "device_offline",
            "metadata": {},
        },
        {
            "device_id": reg_device.id,
            "domain": "zha",
            "platform": "device",
            "type": SHAKEN,
            "subtype": SHAKEN,
            "metadata": {},
        },
        {
            "device_id": reg_device.id,
            "domain": "zha",
            "platform": "device",
            "type": DOUBLE_PRESS,
            "subtype": DOUBLE_PRESS,
            "metadata": {},
        },
        {
            "device_id": reg_device.id,
            "domain": "zha",
            "platform": "device",
            "type": SHORT_PRESS,
            "subtype": SHORT_PRESS,
            "metadata": {},
        },
        {
            "device_id": reg_device.id,
            "domain": "zha",
            "platform": "device",
            "type": LONG_PRESS,
            "subtype": LONG_PRESS,
            "metadata": {},
        },
        {
            "device_id": reg_device.id,
            "domain": "zha",
            "platform": "device",
            "type": LONG_RELEASE,
            "subtype": LONG_RELEASE,
            "metadata": {},
        },
    ]
    assert _same_lists(triggers, expected_triggers)


async def test_no_triggers(hass: HomeAssistant, mock_devices) -> None:
    """Test ZHA device with no triggers."""

    _, zha_device = mock_devices
    ieee_address = str(zha_device.ieee)

    ha_device_registry = dr.async_get(hass)
    reg_device = ha_device_registry.async_get_device(
        identifiers={("zha", ieee_address)}
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, reg_device.id
    )
    assert triggers == [
        {
            "device_id": reg_device.id,
            "domain": "zha",
            "platform": "device",
            "type": "device_offline",
            "subtype": "device_offline",
            "metadata": {},
        }
    ]


async def test_if_fires_on_event(hass: HomeAssistant, mock_devices, calls) -> None:
    """Test for remote triggers firing."""

    zigpy_device, zha_device = mock_devices

    zigpy_device.device_automation_triggers = {
        (SHAKEN, SHAKEN): {COMMAND: COMMAND_SHAKE},
        (DOUBLE_PRESS, DOUBLE_PRESS): {COMMAND: COMMAND_DOUBLE},
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE, ATTR_ENDPOINT_ID: 1},
        (LONG_PRESS, LONG_PRESS): {COMMAND: COMMAND_HOLD},
        (LONG_RELEASE, LONG_RELEASE): {COMMAND: COMMAND_HOLD},
    }

    ieee_address = str(zha_device.ieee)
    ha_device_registry = dr.async_get(hass)
    reg_device = ha_device_registry.async_get_device(
        identifiers={("zha", ieee_address)}
    )

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

    cluster_handler = zha_device.endpoints[1].client_cluster_handlers["1:0x0006"]
    cluster_handler.zha_send_event(COMMAND_SINGLE, [])
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["message"] == "service called"


async def test_device_offline_fires(
    hass: HomeAssistant, zigpy_device_mock, zha_device_restored, calls
) -> None:
    """Test for device offline triggers firing."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [general.Basic.cluster_id],
                "out_clusters": [general.OnOff.cluster_id],
                "device_type": 0,
            }
        }
    )

    zha_device = await zha_device_restored(zigpy_device, last_seen=time.time())
    await async_enable_traffic(hass, [zha_device])
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "device_id": zha_device.device_id,
                        "domain": "zha",
                        "platform": "device",
                        "type": "device_offline",
                        "subtype": "device_offline",
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
    assert zha_device.available is True

    zigpy_device.last_seen = time.time() - zha_device.consider_unavailable_time - 2

    # there are 3 checkins to perform before marking the device unavailable
    future = dt_util.utcnow() + timedelta(seconds=90)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    future = dt_util.utcnow() + timedelta(seconds=90)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    future = dt_util.utcnow() + timedelta(
        seconds=zha_device.consider_unavailable_time + 100
    )
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert zha_device.available is False
    assert len(calls) == 1
    assert calls[0].data["message"] == "service called"


async def test_exception_no_triggers(
    hass: HomeAssistant, mock_devices, calls, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for exception when validating device triggers."""

    _, zha_device = mock_devices

    ieee_address = str(zha_device.ieee)
    ha_device_registry = dr.async_get(hass)
    reg_device = ha_device_registry.async_get_device(
        identifiers={("zha", ieee_address)}
    )

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
    assert (
        "Unnamed automation failed to setup triggers and has been disabled: "
        "device does not have trigger ('junk', 'junk')" in caplog.text
    )


async def test_exception_bad_trigger(
    hass: HomeAssistant, mock_devices, calls, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for exception when validating device triggers."""

    zigpy_device, zha_device = mock_devices

    zigpy_device.device_automation_triggers = {
        (SHAKEN, SHAKEN): {COMMAND: COMMAND_SHAKE},
        (DOUBLE_PRESS, DOUBLE_PRESS): {COMMAND: COMMAND_DOUBLE},
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE},
        (LONG_PRESS, LONG_PRESS): {COMMAND: COMMAND_HOLD},
        (LONG_RELEASE, LONG_RELEASE): {COMMAND: COMMAND_HOLD},
    }

    ieee_address = str(zha_device.ieee)
    ha_device_registry = dr.async_get(hass)
    reg_device = ha_device_registry.async_get_device(
        identifiers={("zha", ieee_address)}
    )

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
    assert (
        "Unnamed automation failed to setup triggers and has been disabled: "
        "device does not have trigger ('junk', 'junk')" in caplog.text
    )


async def test_validate_trigger_config_missing_info(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    zigpy_device_mock,
    mock_zigpy_connect: ControllerApplication,
    zha_device_joined,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device triggers referring to a missing device."""

    # Join a device
    switch = zigpy_device_mock(SWITCH_SIGNATURE)
    await zha_device_joined(switch)

    # After we unload the config entry, trigger info was not cached on startup, nor can
    # it be pulled from the current device, making it impossible to validate triggers
    await hass.config_entries.async_unload(config_entry.entry_id)

    ha_device_registry = dr.async_get(hass)
    reg_device = ha_device_registry.async_get_device(
        identifiers={("zha", str(switch.ieee))}
    )

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

    assert "Unable to get zha device" in caplog.text

    with pytest.raises(InvalidDeviceAutomationConfig):
        await async_get_device_automations(
            hass, DeviceAutomationType.TRIGGER, reg_device.id
        )


async def test_validate_trigger_config_unloaded_bad_info(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    zigpy_device_mock,
    mock_zigpy_connect: ControllerApplication,
    zha_device_joined,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device triggers referring to a missing device."""

    # Join a device
    switch = zigpy_device_mock(SWITCH_SIGNATURE)
    await zha_device_joined(switch)

    # After we unload the config entry, trigger info was not cached on startup, nor can
    # it be pulled from the current device, making it impossible to validate triggers
    await hass.config_entries.async_unload(config_entry.entry_id)

    # Reload ZHA to persist the device info in the cache
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)

    ha_device_registry = dr.async_get(hass)
    reg_device = ha_device_registry.async_get_device(
        identifiers={("zha", str(switch.ieee))}
    )

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

    assert "Unable to find trigger" in caplog.text
