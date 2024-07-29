"""ZHA device automation trigger tests."""

from unittest.mock import patch

import pytest
from zha.application.const import ATTR_ENDPOINT_ID
from zigpy.application import ControllerApplication
from zigpy.device import Device as ZigpyDevice
import zigpy.profiles.zha
import zigpy.types

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.zha.helpers import get_zha_gateway
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_get_device_automations


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


@pytest.fixture(autouse=True)
def sensor_platforms_only():
    """Only set up the sensor platform and required base platforms to speed up tests."""
    with patch("homeassistant.components.zha.PLATFORMS", (Platform.SENSOR,)):
        yield


def _same_lists(list_a, list_b):
    if len(list_a) != len(list_b):
        return False

    return all(item in list_b for item in list_a)


async def test_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    setup_zha,
) -> None:
    """Test ZHA device triggers."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = ZigpyDevice(
        application=gateway.application_controller,
        ieee=zigpy.types.EUI64.convert("aa:bb:cc:dd:11:22:33:44"),
        nwk=0x1234,
    )
    zigpy_device.device_automation_triggers = {
        (SHAKEN, SHAKEN): {COMMAND: COMMAND_SHAKE},
        (DOUBLE_PRESS, DOUBLE_PRESS): {COMMAND: COMMAND_DOUBLE},
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE},
        (LONG_PRESS, LONG_PRESS): {COMMAND: COMMAND_HOLD},
        (LONG_RELEASE, LONG_RELEASE): {COMMAND: COMMAND_HOLD},
    }

    zha_device = gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zha_device.device)
    await hass.async_block_till_done(wait_background_tasks=True)

    reg_device = device_registry.async_get_device(
        identifiers={("zha", str(zha_device.ieee))}
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


async def test_no_triggers(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, setup_zha
) -> None:
    """Test ZHA device with no triggers."""
    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = ZigpyDevice(
        application=gateway.application_controller,
        ieee=zigpy.types.EUI64.convert("aa:bb:cc:dd:11:22:33:44"),
        nwk=0x1234,
    )
    zigpy_device.device_automation_triggers = {}

    zha_device = gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zha_device.device)
    await hass.async_block_till_done(wait_background_tasks=True)

    reg_device = device_registry.async_get_device(
        identifiers={("zha", str(zha_device.ieee))}
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


async def test_if_fires_on_event(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    setup_zha,
) -> None:
    """Test for remote triggers firing."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = ZigpyDevice(
        application=gateway.application_controller,
        ieee=zigpy.types.EUI64.convert("aa:bb:cc:dd:11:22:33:44"),
        nwk=0x1234,
    )
    ep = zigpy_device.add_endpoint(1)
    ep.add_output_cluster(0x0006)

    zigpy_device.device_automation_triggers = {
        (SHAKEN, SHAKEN): {COMMAND: COMMAND_SHAKE},
        (DOUBLE_PRESS, DOUBLE_PRESS): {COMMAND: COMMAND_DOUBLE},
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE, ATTR_ENDPOINT_ID: 1},
        (LONG_PRESS, LONG_PRESS): {COMMAND: COMMAND_HOLD},
        (LONG_RELEASE, LONG_RELEASE): {COMMAND: COMMAND_HOLD},
    }

    zha_device = gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zha_device.device)
    await hass.async_block_till_done(wait_background_tasks=True)

    reg_device = device_registry.async_get_device(
        identifiers={("zha", str(zha_device.ieee))}
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

    zha_device.emit_zha_event(
        {
            "unique_id": f"{zha_device.ieee}:1:0x0006",
            "endpoint_id": 1,
            "cluster_id": 0x0006,
            "command": COMMAND_SINGLE,
            "args": [],
            "params": {},
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["message"] == "service called"


async def test_device_offline_fires(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    setup_zha,
) -> None:
    """Test for device offline triggers firing."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = ZigpyDevice(
        application=gateway.application_controller,
        ieee=zigpy.types.EUI64.convert("aa:bb:cc:dd:11:22:33:44"),
        nwk=0x1234,
    )

    zha_device = gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zha_device.device)
    await hass.async_block_till_done(wait_background_tasks=True)

    reg_device = device_registry.async_get_device(
        identifiers={("zha", str(zha_device.ieee))}
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

    assert zha_device.available is True
    zha_device.available = False
    zha_device.emit_zha_event({"device_event_type": "device_offline"})
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["message"] == "service called"


async def test_exception_no_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    setup_zha,
) -> None:
    """Test for exception when validating device triggers."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = ZigpyDevice(
        application=gateway.application_controller,
        ieee=zigpy.types.EUI64.convert("aa:bb:cc:dd:11:22:33:44"),
        nwk=0x1234,
    )

    zha_device = gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zha_device.device)
    await hass.async_block_till_done(wait_background_tasks=True)

    reg_device = device_registry.async_get_device(
        identifiers={("zha", str(zha_device.ieee))}
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
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    setup_zha,
) -> None:
    """Test for exception when validating device triggers."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = ZigpyDevice(
        application=gateway.application_controller,
        ieee=zigpy.types.EUI64.convert("aa:bb:cc:dd:11:22:33:44"),
        nwk=0x1234,
    )
    zigpy_device.device_automation_triggers = {
        (SHAKEN, SHAKEN): {COMMAND: COMMAND_SHAKE},
        (DOUBLE_PRESS, DOUBLE_PRESS): {COMMAND: COMMAND_DOUBLE},
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE},
        (LONG_PRESS, LONG_PRESS): {COMMAND: COMMAND_HOLD},
        (LONG_RELEASE, LONG_RELEASE): {COMMAND: COMMAND_HOLD},
    }

    zha_device = gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zha_device.device)
    await hass.async_block_till_done(wait_background_tasks=True)

    reg_device = device_registry.async_get_device(
        identifiers={("zha", str(zha_device.ieee))}
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
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    setup_zha,
) -> None:
    """Test device triggers referring to a missing device."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = ZigpyDevice(
        application=gateway.application_controller,
        ieee=zigpy.types.EUI64.convert("aa:bb:cc:dd:11:22:33:44"),
        nwk=0x1234,
    )
    zigpy_device.device_automation_triggers = {
        (SHAKEN, SHAKEN): {COMMAND: COMMAND_SHAKE},
        (DOUBLE_PRESS, DOUBLE_PRESS): {COMMAND: COMMAND_DOUBLE},
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE},
        (LONG_PRESS, LONG_PRESS): {COMMAND: COMMAND_HOLD},
        (LONG_RELEASE, LONG_RELEASE): {COMMAND: COMMAND_HOLD},
    }

    zha_device = gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zha_device.device)
    await hass.async_block_till_done(wait_background_tasks=True)

    # After we unload the config entry, trigger info was not cached on startup, nor can
    # it be pulled from the current device, making it impossible to validate triggers
    await hass.config_entries.async_unload(config_entry.entry_id)

    reg_device = device_registry.async_get_device(
        identifiers={("zha", str(zha_device.ieee))}
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
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    zigpy_app_controller: ControllerApplication,
    setup_zha,
) -> None:
    """Test device triggers referring to a missing device."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = ZigpyDevice(
        application=gateway.application_controller,
        ieee=zigpy.types.EUI64.convert("aa:bb:cc:dd:11:22:33:44"),
        nwk=0x1234,
    )
    zigpy_device.device_automation_triggers = {
        (SHAKEN, SHAKEN): {COMMAND: COMMAND_SHAKE},
        (DOUBLE_PRESS, DOUBLE_PRESS): {COMMAND: COMMAND_DOUBLE},
        (SHORT_PRESS, SHORT_PRESS): {COMMAND: COMMAND_SINGLE},
        (LONG_PRESS, LONG_PRESS): {COMMAND: COMMAND_HOLD},
        (LONG_RELEASE, LONG_RELEASE): {COMMAND: COMMAND_HOLD},
    }

    zigpy_app_controller.devices[zigpy_device.ieee] = zigpy_device
    zha_device = gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zha_device.device)
    await hass.async_block_till_done(wait_background_tasks=True)

    # After we unload the config entry, trigger info was not cached on startup, nor can
    # it be pulled from the current device, making it impossible to validate triggers
    await hass.config_entries.async_unload(config_entry.entry_id)

    # Reload ZHA to persist the device info in the cache
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    await hass.config_entries.async_unload(config_entry.entry_id)

    reg_device = device_registry.async_get_device(
        identifiers={("zha", str(zha_device.ieee))}
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
