"""Test for the SmartThings select platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, Command
from pysmartthings.models import HealthStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.smartthings import MAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
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

from tests.common import MockConfigEntry


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.SELECT)


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.dryer").state == "stop"

    await trigger_update(
        hass,
        devices,
        "02f7256e-8353-5bdd-547f-bd5b1647e01b",
        Capability.DRYER_OPERATING_STATE,
        Attribute.MACHINE_STATE,
        "run",
    )

    assert hass.states.get("select.dryer").state == "run"


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
async def test_select_option(
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
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.dryer", ATTR_OPTION: "run"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "02f7256e-8353-5bdd-547f-bd5b1647e01b",
        Capability.DRYER_OPERATING_STATE,
        Command.SET_MACHINE_STATE,
        MAIN,
        argument="run",
    )


@pytest.mark.parametrize("device_fixture", ["da_ks_range_0101x"])
async def test_select_option_map(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.vulcan_lamp")
    assert state
    assert state.state == "extra_high"
    assert state.attributes[ATTR_OPTIONS] == [
        "off",
        "extra_high",
    ]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.vulcan_lamp", ATTR_OPTION: "extra_high"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "2c3cbaa0-1899-5ddc-7b58-9d657bd48f18",
        Capability.SAMSUNG_CE_LAMP,
        Command.SET_BRIGHTNESS_LEVEL,
        MAIN,
        argument="extraHigh",
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
async def test_select_option_without_remote_control(
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
        match="Can only be updated when remote control is enabled",
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.dryer", ATTR_OPTION: "run"},
            blocking=True,
        )
    devices.execute_device_command.assert_not_called()


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("select.dryer").state == "stop"

    await trigger_health_update(
        hass, devices, "02f7256e-8353-5bdd-547f-bd5b1647e01b", HealthStatus.OFFLINE
    )

    assert hass.states.get("select.dryer").state == STATE_UNAVAILABLE

    await trigger_health_update(
        hass, devices, "02f7256e-8353-5bdd-547f-bd5b1647e01b", HealthStatus.ONLINE
    )

    assert hass.states.get("select.dryer").state == "stop"


@pytest.mark.parametrize("device_fixture", ["da_wm_wd_000001"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("select.dryer").state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000003"])
async def test_select_option_as_integer(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting an option represented as an integer."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.clim_salon_dust_filter_alarm_threshold")
    assert state.state == "500"
    assert all(isinstance(option, str) for option in state.attributes[ATTR_OPTIONS])

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.clim_salon_dust_filter_alarm_threshold",
            ATTR_OPTION: "300",
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "1e3f7ca2-e005-e1a4-f6d7-bc231e3f7977",
        Capability.SAMSUNG_CE_DUST_FILTER_ALARM,
        Command.SET_ALARM_THRESHOLD,
        MAIN,
        argument=300,
    )


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000001_sub"])
async def test_fsv_select_state(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test FSV select state."""
    await setup_integration(hass, mock_config_entry)

    # Check that FSV select entities exist and have correct states and options
    fsv_2091_state = hass.states.get(
        "select.eco_heating_system_external_run_input_zone_1"
    )
    assert fsv_2091_state is not None
    assert fsv_2091_state.state == "disable"  # value=0 from fixture
    assert fsv_2091_state.attributes[ATTR_OPTIONS] == [
        "disable",
        "compressor_only",
        "compressor_pump_mode_2",
        "compressor_pump_mode_3",
        "compressor_pump_mode_4",
    ]

    fsv_3011_state = hass.states.get("select.eco_heating_system_dhw_tank_function")
    assert fsv_3011_state is not None
    assert fsv_3011_state.state == "enabled_thermo_off"  # value=2 from fixture
    assert fsv_3011_state.attributes[ATTR_OPTIONS] == [
        "disabled",
        "enabled_thermo_on",
        "enabled_thermo_off",
    ]

    fsv_3071_state = hass.states.get(
        "select.eco_heating_system_three_way_valve_direction"
    )
    assert fsv_3071_state is not None
    assert fsv_3071_state.state == "room_space_heating"  # value=0 from fixture
    assert fsv_3071_state.attributes[ATTR_OPTIONS] == [
        "room_space_heating",
        "tank_dhw",
    ]

    # Update FSV settings to change values
    await trigger_update(
        hass,
        devices,
        "1f98ebd0-ac48-d802-7f62-000001200100",
        Capability.SAMSUNG_CE_EHS_FSV_SETTINGS,
        Attribute.FSV_SETTINGS,
        [
            {
                "id": "2091",
                "inUse": True,
                "resolution": 1,
                "type": "etc",
                "minValue": 0,
                "maxValue": 4,
                "value": 3,  # Changed value
                "isValid": True,
            },
            {
                "id": "3011",
                "inUse": True,
                "resolution": 1,
                "type": "etc",
                "minValue": 0,
                "maxValue": 2,
                "value": 1,  # Changed value
                "isValid": True,
            },
            {
                "id": "3071",
                "inUse": True,
                "resolution": 1,
                "type": "etc",
                "minValue": 0,
                "maxValue": 1,
                "value": 1,  # Changed value
                "isValid": True,
            },
        ],
    )

    # Verify updated values
    fsv_2091_updated = hass.states.get(
        "select.eco_heating_system_external_run_input_zone_1"
    )
    assert fsv_2091_updated is not None
    assert fsv_2091_updated.state == "compressor_pump_mode_3"

    fsv_3011_updated = hass.states.get("select.eco_heating_system_dhw_tank_function")
    assert fsv_3011_updated is not None
    assert fsv_3011_updated.state == "enabled_thermo_on"

    fsv_3071_updated = hass.states.get(
        "select.eco_heating_system_three_way_valve_direction"
    )
    assert fsv_3071_updated is not None
    assert fsv_3071_updated.state == "tank_dhw"


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000001_sub"])
async def test_fsv_select_option(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test FSV select option."""
    await setup_integration(hass, mock_config_entry)

    # Test selecting option for FSV select 2092
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.eco_heating_system_external_run_input_zone_2",
            ATTR_OPTION: "pump_off",
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_with(
        "1f98ebd0-ac48-d802-7f62-000001200100",
        Capability.SAMSUNG_CE_EHS_FSV_SETTINGS,
        Command.SET_VALUE,
        MAIN,
        argument=["2092", 2],
    )

    # Test selecting option for FSV select 4021
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.eco_heating_system_backup_heater_application",
            ATTR_OPTION: "buh_two_step",
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_with(
        "1f98ebd0-ac48-d802-7f62-000001200100",
        Capability.SAMSUNG_CE_EHS_FSV_SETTINGS,
        Command.SET_VALUE,
        MAIN,
        argument=["4021", 1],
    )

    # Test selecting option for FSV select 3071
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.eco_heating_system_three_way_valve_direction",
            ATTR_OPTION: "tank_dhw",
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_with(
        "1f98ebd0-ac48-d802-7f62-000001200100",
        Capability.SAMSUNG_CE_EHS_FSV_SETTINGS,
        Command.SET_VALUE,
        MAIN,
        argument=["3071", 1],
    )
