"""The tests for Network UPS Tools (NUT) device actions."""

from unittest.mock import AsyncMock

from aionut import NUTError
import pytest
from pytest_unordered import unordered

from homeassistant.components import automation, device_automation
from homeassistant.components.device_automation import (
    DeviceAutomationType,
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.nut import DOMAIN
from homeassistant.components.nut.const import INTEGRATION_SUPPORTED_COMMANDS
from homeassistant.const import CONF_DEVICE_ID, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .util import async_init_integration

from tests.common import async_get_device_automations


async def test_get_all_actions_for_specified_user(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we get all the expected actions from a nut if user is specified."""
    list_commands_return_value = {
        supported_command: supported_command
        for supported_command in INTEGRATION_SUPPORTED_COMMANDS
    }

    await async_init_integration(
        hass,
        username="someuser",
        password="somepassword",
        list_vars={"ups.status": "OL"},
        list_commands_return_value=list_commands_return_value,
    )
    device_entry = next(device for device in device_registry.devices.values())
    expected_actions = [
        {
            "domain": DOMAIN,
            "type": action.replace(".", "_"),
            "device_id": device_entry.id,
            "metadata": {},
        }
        for action in INTEGRATION_SUPPORTED_COMMANDS
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert actions == unordered(expected_actions)


async def test_no_actions_for_anonymous_user(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we get no actions if user is not specified."""
    list_commands_return_value = {"some action": "some description"}

    await async_init_integration(
        hass,
        username=None,
        password=None,
        list_vars={"ups.status": "OL"},
        list_commands_return_value=list_commands_return_value,
    )
    device_entry = next(device for device in device_registry.devices.values())
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )

    assert len(actions) == 0


async def test_no_actions_invalid_device(
    hass: HomeAssistant,
) -> None:
    """Test we get no actions for an invalid device."""
    list_commands_return_value = {"beeper.enable": None}
    await async_init_integration(
        hass,
        list_vars={"ups.status": "OL"},
        list_commands_return_value=list_commands_return_value,
    )

    device_id = "invalid_device_id"
    platform = await device_automation.async_get_device_automation_platform(
        hass, DOMAIN, DeviceAutomationType.ACTION
    )
    actions = await platform.async_get_actions(hass, device_id)

    assert len(actions) == 0


async def test_list_commands_exception(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test there are no actions if list_commands raises exception."""
    await async_init_integration(
        hass, list_vars={"ups.status": "OL"}, list_commands_side_effect=NUTError
    )

    device_entry = next(device for device in device_registry.devices.values())
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert len(actions) == 0


async def test_unsupported_command(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test unsupported command is excluded."""

    list_commands_return_value = {
        "beeper.enable": None,
        "device.something": "Does something unsupported",
    }
    await async_init_integration(
        hass,
        list_vars={"ups.status": "OL"},
        list_commands_return_value=list_commands_return_value,
    )
    device_entry = next(device for device in device_registry.devices.values())
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    assert len(actions) == 1


async def test_action(hass: HomeAssistant, device_registry: dr.DeviceRegistry) -> None:
    """Test actions are executed."""

    list_commands_return_value = {
        "beeper.enable": None,
        "beeper.disable": None,
    }
    run_command = AsyncMock()
    await async_init_integration(
        hass,
        list_ups={"someUps": "Some UPS"},
        list_vars={"ups.status": "OL"},
        list_commands_return_value=list_commands_return_value,
        run_command=run_command,
    )
    device_entry = next(device for device in device_registry.devices.values())

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_some_event",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "type": "beeper_enable",
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_another_event",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "type": "beeper_disable",
                    },
                },
            ]
        },
    )

    hass.bus.async_fire("test_some_event")
    await hass.async_block_till_done()
    run_command.assert_called_with("someUps", "beeper.enable")

    hass.bus.async_fire("test_another_event")
    await hass.async_block_till_done()
    run_command.assert_called_with("someUps", "beeper.disable")


async def test_rund_command_exception(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test logged error if run command raises exception."""

    list_commands_return_value = {"beeper.enable": None}
    error_message = "Something wrong happened"
    run_command = AsyncMock(side_effect=NUTError(error_message))
    await async_init_integration(
        hass,
        list_vars={"ups.status": "OL"},
        list_commands_return_value=list_commands_return_value,
        run_command=run_command,
    )
    device_entry = next(device for device in device_registry.devices.values())

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_some_event",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "type": "beeper_enable",
                    },
                },
            ]
        },
    )

    hass.bus.async_fire("test_some_event")
    await hass.async_block_till_done()

    assert error_message in caplog.text


async def test_action_exception_invalid_device(hass: HomeAssistant) -> None:
    """Test raises exception if invalid device."""
    list_commands_return_value = {"beeper.enable": None}
    await async_init_integration(
        hass,
        list_vars={"ups.status": "OL"},
        list_commands_return_value=list_commands_return_value,
    )

    platform = await device_automation.async_get_device_automation_platform(
        hass, DOMAIN, DeviceAutomationType.ACTION
    )

    with pytest.raises(InvalidDeviceAutomationConfig):
        await platform.async_call_action_from_config(
            hass,
            {CONF_TYPE: "beeper.enable", CONF_DEVICE_ID: "invalid_device_id"},
            {},
            None,
        )
