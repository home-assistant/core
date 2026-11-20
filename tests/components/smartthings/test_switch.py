"""Test for the SmartThings switch platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, Command
from pysmartthings.models import HealthStatus
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smartthings.const import MAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
    TargetKey,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import (
    set_attribute_value,
    setup_integration,
    snapshot_smartthings_entities,
    trigger_health_update,
    trigger_update,
)


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.SWITCH)


@pytest.mark.parametrize("device_fixture", ["c2c_arlo_pro_3_switch"])
@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_TURN_ON, Command.ON),
        (SERVICE_TURN_OFF, Command.OFF),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    command: Command,
) -> None:
    """Test switch turn on and off command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        action,
        {ATTR_ENTITY_ID: "switch.theater_2nd_floor_hallway"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "10e06a70-ee7d-4832-85e9-a0a06a7a05bd", Capability.SWITCH, command, MAIN
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
@pytest.mark.parametrize(
    ("action", "argument"),
    [
        (SERVICE_TURN_ON, "on"),
        (SERVICE_TURN_OFF, "off"),
    ],
)
async def test_command_switch_turn_on_off(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    argument: str,
) -> None:
    """Test switch turn on and off command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        action,
        {ATTR_ENTITY_ID: "switch.theater_dryer_wrinkle_prevent"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "02f7256e-8353-5bdd-547f-bd5b1647e01b",
        Capability.CUSTOM_DRYER_WRINKLE_PREVENT,
        Command.SET_DRYER_WRINKLE_PREVENT,
        MAIN,
        argument,
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
@pytest.mark.parametrize(
    ("action", "argument"),
    [
        (SERVICE_TURN_ON, True),
        (SERVICE_TURN_OFF, False),
    ],
)
async def test_dishwasher_washing_option_switch_turn_on_off(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    argument: str,
) -> None:
    """Test switch turn on and off command."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        "true",
    )
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        action,
        {ATTR_ENTITY_ID: "switch.dishwasher_1_speed_booster"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "7ff318f3-3772-524d-3c9f-72fcd26413ed",
        Capability.SAMSUNG_CE_DISHWASHER_WASHING_OPTIONS,
        Command.SET_SPEED_BOOSTER,
        MAIN,
        argument,
    )


@pytest.mark.parametrize("device_fixture", ["da_ref_normal_000001"])
@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_TURN_ON, Command.ACTIVATE),
        (SERVICE_TURN_OFF, Command.DEACTIVATE),
    ],
)
async def test_custom_commands(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    command: Command,
) -> None:
    """Test switch turn on and off command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        action,
        {ATTR_ENTITY_ID: "switch.theater_refrigerator_power_cool"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "7db87911-7dce-1cf2-7119-b953432a2f09",
        Capability.SAMSUNG_CE_POWER_COOL,
        command,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
@pytest.mark.parametrize(
    ("action", "argument"),
    [
        (SERVICE_TURN_ON, "on"),
        (SERVICE_TURN_OFF, "off"),
    ],
)
async def test_ac_purify_switch(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    argument: str,
) -> None:
    """Test Samsung OCF AC purify switch."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        action,
        {ATTR_ENTITY_ID: "switch.theater_ac_office_granit_purify"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "96a5ef74-5832-a84b-f1f7-ca799957065d",
        Capability.CUSTOM_SPI_MODE,
        Command.SET_SPI_MODE,
        MAIN,
        argument,
    )


@pytest.mark.parametrize("device_fixture", ["c2c_arlo_pro_3_switch"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.theater_2nd_floor_hallway").state == STATE_ON

    await trigger_update(
        hass,
        devices,
        "10e06a70-ee7d-4832-85e9-a0a06a7a05bd",
        Capability.SWITCH,
        Attribute.SWITCH,
        "off",
    )

    assert hass.states.get("switch.theater_2nd_floor_hallway").state == STATE_OFF


@pytest.mark.parametrize("device_fixture", ["c2c_arlo_pro_3_switch"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.theater_2nd_floor_hallway").state == STATE_ON

    await trigger_health_update(
        hass, devices, "10e06a70-ee7d-4832-85e9-a0a06a7a05bd", HealthStatus.OFFLINE
    )

    assert (
        hass.states.get("switch.theater_2nd_floor_hallway").state == STATE_UNAVAILABLE
    )

    await trigger_health_update(
        hass, devices, "10e06a70-ee7d-4832-85e9-a0a06a7a05bd", HealthStatus.ONLINE
    )

    assert hass.states.get("switch.theater_2nd_floor_hallway").state == STATE_ON


@pytest.mark.parametrize("device_fixture", ["c2c_arlo_pro_3_switch"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert (
        hass.states.get("switch.theater_2nd_floor_hallway").state == STATE_UNAVAILABLE
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
async def test_turn_on_without_remote_control(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        "false",
    )
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        ServiceValidationError,
        match="Can only be changed when remote control is enabled",
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_ON,
            {TargetKey.ENTITY_ID: "switch.dishwasher_1_speed_booster"},
            blocking=True,
        )
    devices.execute_device_command.assert_not_called()


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
async def test_turn_on_with_wrong_dishwasher_machine_state(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        "true",
    )
    set_attribute_value(
        devices,
        Capability.DISHWASHER_OPERATING_STATE,
        Attribute.MACHINE_STATE,
        "run",
    )
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        ServiceValidationError,
        match="Can only be changed when the dishwasher machine state is stop",
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_ON,
            {TargetKey.ENTITY_ID: "switch.dishwasher_1_speed_booster"},
            blocking=True,
        )
    devices.execute_device_command.assert_not_called()


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_01011"])
async def test_turn_on_with_wrong_dishwasher_cycle(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    set_attribute_value(
        devices,
        Capability.REMOTE_CONTROL_STATUS,
        Attribute.REMOTE_CONTROL_ENABLED,
        "true",
    )
    set_attribute_value(
        devices,
        Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE,
        Attribute.WASHING_COURSE,
        "preWash",
    )
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        ServiceValidationError,
        match="Option is not supported by the selected cycle",
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_ON,
            {TargetKey.ENTITY_ID: "switch.dishwasher_1_speed_booster"},
            blocking=True,
        )
    devices.execute_device_command.assert_not_called()
