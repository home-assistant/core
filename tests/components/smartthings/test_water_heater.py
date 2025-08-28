"""Test for the SmartThings water heater platform."""

from unittest.mock import AsyncMock, call

from pysmartthings import Attribute, Capability, Command
from pysmartthings.models import HealthStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smartthings import MAIN
from homeassistant.components.water_heater import (
    ATTR_AWAY_MODE,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_OPERATION_LIST,
    ATTR_OPERATION_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_AWAY_MODE,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    STATE_ECO,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
    WaterHeaterEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
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

    snapshot_smartthings_entities(
        hass, entity_registry, snapshot, Platform.WATER_HEATER
    )


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000002_sub"])
@pytest.mark.parametrize(
    ("operation_mode", "argument"),
    [
        (STATE_ECO, "eco"),
        (STATE_HEAT_PUMP, "std"),
        (STATE_HIGH_DEMAND, "force"),
        (STATE_PERFORMANCE, "power"),
    ],
)
async def test_set_operation_mode(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    operation_mode: str,
    argument: str,
) -> None:
    """Test set operation mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: "water_heater.warmepumpe",
            ATTR_OPERATION_MODE: operation_mode,
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "3810e5ad-5351-d9f9-12ff-000001200000",
        Capability.AIR_CONDITIONER_MODE,
        Command.SET_AIR_CONDITIONER_MODE,
        MAIN,
        argument=argument,
    )


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000002_sub"])
async def test_set_operation_mode_off(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set operation mode to off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: "water_heater.warmepumpe",
            ATTR_OPERATION_MODE: STATE_OFF,
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "3810e5ad-5351-d9f9-12ff-000001200000",
        Capability.SWITCH,
        Command.OFF,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000001_sub"])
async def test_set_operation_mode_from_off(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set operation mode."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("water_heater.eco_heating_system").state == STATE_OFF

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: "water_heater.eco_heating_system",
            ATTR_OPERATION_MODE: STATE_ECO,
        },
        blocking=True,
    )
    assert devices.execute_device_command.mock_calls == [
        call(
            "1f98ebd0-ac48-d802-7f62-000001200100",
            Capability.SWITCH,
            Command.ON,
            MAIN,
        ),
        call(
            "1f98ebd0-ac48-d802-7f62-000001200100",
            Capability.AIR_CONDITIONER_MODE,
            Command.SET_AIR_CONDITIONER_MODE,
            MAIN,
            argument="eco",
        ),
    ]


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000002_sub"])
async def test_set_operation_to_off(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set operation mode to off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: "water_heater.warmepumpe",
            ATTR_OPERATION_MODE: STATE_OFF,
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "3810e5ad-5351-d9f9-12ff-000001200000",
        Capability.SWITCH,
        Command.OFF,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000002_sub"])
@pytest.mark.parametrize(
    ("service", "command"),
    [
        (SERVICE_TURN_ON, Command.ON),
        (SERVICE_TURN_OFF, Command.OFF),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    command: Command,
) -> None:
    """Test turn on and off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: "water_heater.warmepumpe",
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "3810e5ad-5351-d9f9-12ff-000001200000",
        Capability.SWITCH,
        command,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000002_sub"])
async def test_set_temperature(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set operation mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "water_heater.warmepumpe",
            ATTR_TEMPERATURE: 56,
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "3810e5ad-5351-d9f9-12ff-000001200000",
        Capability.THERMOSTAT_COOLING_SETPOINT,
        Command.SET_COOLING_SETPOINT,
        MAIN,
        argument=56,
    )


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000002_sub"])
@pytest.mark.parametrize(
    ("on", "argument"),
    [
        (True, "on"),
        (False, "off"),
    ],
)
async def test_away_mode(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    on: bool,
    argument: str,
) -> None:
    """Test set away mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_AWAY_MODE,
        {
            ATTR_ENTITY_ID: "water_heater.warmepumpe",
            ATTR_AWAY_MODE: on,
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "3810e5ad-5351-d9f9-12ff-000001200000",
        Capability.CUSTOM_OUTING_MODE,
        Command.SET_OUTING_MODE,
        MAIN,
        argument=argument,
    )


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000002_sub"])
async def test_operation_list_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("water_heater.warmepumpe").attributes[
        ATTR_OPERATION_LIST
    ] == [
        STATE_OFF,
        STATE_ECO,
        STATE_HEAT_PUMP,
        STATE_PERFORMANCE,
        STATE_HIGH_DEMAND,
    ]

    await trigger_update(
        hass,
        devices,
        "3810e5ad-5351-d9f9-12ff-000001200000",
        Capability.AIR_CONDITIONER_MODE,
        Attribute.SUPPORTED_AC_MODES,
        ["eco", "force", "power"],
    )

    assert hass.states.get("water_heater.warmepumpe").attributes[
        ATTR_OPERATION_LIST
    ] == [
        STATE_OFF,
        STATE_ECO,
        STATE_HIGH_DEMAND,
        STATE_PERFORMANCE,
    ]


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000002_sub"])
async def test_current_operation_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("water_heater.warmepumpe").state == STATE_HEAT_PUMP

    await trigger_update(
        hass,
        devices,
        "3810e5ad-5351-d9f9-12ff-000001200000",
        Capability.AIR_CONDITIONER_MODE,
        Attribute.AIR_CONDITIONER_MODE,
        "eco",
    )

    assert hass.states.get("water_heater.warmepumpe").state == STATE_ECO


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000002_sub"])
async def test_switch_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("water_heater.warmepumpe")
    assert state.state == STATE_HEAT_PUMP
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.AWAY_MODE
    )

    await trigger_update(
        hass,
        devices,
        "3810e5ad-5351-d9f9-12ff-000001200000",
        Capability.SWITCH,
        Attribute.SWITCH,
        "off",
    )

    state = hass.states.get("water_heater.warmepumpe")
    assert state.state == STATE_OFF
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.AWAY_MODE
    )


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000002_sub"])
async def test_current_temperature_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("water_heater.warmepumpe").attributes[ATTR_CURRENT_TEMPERATURE]
        == 49.6
    )

    await trigger_update(
        hass,
        devices,
        "3810e5ad-5351-d9f9-12ff-000001200000",
        Capability.TEMPERATURE_MEASUREMENT,
        Attribute.TEMPERATURE,
        50.0,
    )

    assert (
        hass.states.get("water_heater.warmepumpe").attributes[ATTR_CURRENT_TEMPERATURE]
        == 50.0
    )


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000002_sub"])
async def test_target_temperature_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("water_heater.warmepumpe").attributes[ATTR_TEMPERATURE] == 52.0
    )

    await trigger_update(
        hass,
        devices,
        "3810e5ad-5351-d9f9-12ff-000001200000",
        Capability.THERMOSTAT_COOLING_SETPOINT,
        Attribute.COOLING_SETPOINT,
        50.0,
    )

    assert (
        hass.states.get("water_heater.warmepumpe").attributes[ATTR_TEMPERATURE] == 50.0
    )


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000002_sub"])
@pytest.mark.parametrize(
    ("attribute", "old_value", "state_attribute"),
    [
        (Attribute.MINIMUM_SETPOINT, 40, ATTR_TARGET_TEMP_LOW),
        (Attribute.MAXIMUM_SETPOINT, 57, ATTR_TARGET_TEMP_HIGH),
    ],
)
async def test_target_temperature_bound_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    attribute: Attribute,
    old_value: float,
    state_attribute: str,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("water_heater.warmepumpe").attributes[state_attribute]
        == old_value
    )

    await trigger_update(
        hass,
        devices,
        "3810e5ad-5351-d9f9-12ff-000001200000",
        Capability.CUSTOM_THERMOSTAT_SETPOINT_CONTROL,
        attribute,
        50.0,
    )

    assert (
        hass.states.get("water_heater.warmepumpe").attributes[state_attribute] == 50.0
    )


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000002_sub"])
async def test_away_mode_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("water_heater.warmepumpe").attributes[ATTR_AWAY_MODE]
        == STATE_OFF
    )

    await trigger_update(
        hass,
        devices,
        "3810e5ad-5351-d9f9-12ff-000001200000",
        Capability.CUSTOM_OUTING_MODE,
        Attribute.OUTING_MODE,
        "on",
    )

    assert (
        hass.states.get("water_heater.warmepumpe").attributes[ATTR_AWAY_MODE]
        == STATE_ON
    )


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000002_sub"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("water_heater.warmepumpe").state == STATE_HEAT_PUMP

    await trigger_health_update(
        hass, devices, "3810e5ad-5351-d9f9-12ff-000001200000", HealthStatus.OFFLINE
    )

    assert hass.states.get("water_heater.warmepumpe").state == STATE_UNAVAILABLE

    await trigger_health_update(
        hass, devices, "3810e5ad-5351-d9f9-12ff-000001200000", HealthStatus.ONLINE
    )

    assert hass.states.get("water_heater.warmepumpe").state == STATE_HEAT_PUMP


@pytest.mark.parametrize("device_fixture", ["da_sac_ehs_000002_sub"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("water_heater.warmepumpe").state == STATE_UNAVAILABLE
