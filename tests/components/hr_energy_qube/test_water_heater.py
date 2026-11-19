"""Tests for the Qube Heat Pump water heater platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.water_heater import (
    DOMAIN as WATER_HEATER_DOMAIN,
    STATE_HEAT_PUMP,
    STATE_PERFORMANCE,
    WaterHeaterService,
    WaterHeaterServiceArgument,
)
from homeassistant.const import STATE_UNKNOWN, Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

ENTITY_ID = "water_heater.qube_heat_pump_domestic_hot_water"


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all water heater entities via snapshot."""
    with patch(
        "homeassistant.components.hr_energy_qube.PLATFORMS",
        [Platform.WATER_HEATER],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_temperature(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the target DHW temperature."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WaterHeaterService.SET_TEMPERATURE,
        {TargetKey.ENTITY_ID: ENTITY_ID, WaterHeaterServiceArgument.TEMPERATURE: 55},
        blocking=True,
    )

    mock_qube_client.write_setpoint.assert_awaited_once_with("setpoint_dhw", 55)


@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        (ConnectionError, None),
        (None, False),
    ],
)
async def test_set_temperature_failure(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception] | None,
    return_value: bool | None,
) -> None:
    """Test set temperature raises HomeAssistantError on failure."""
    await setup_integration(hass, mock_config_entry)

    mock_qube_client.write_setpoint = AsyncMock(
        side_effect=side_effect, return_value=return_value
    )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.SET_TEMPERATURE,
            {
                TargetKey.ENTITY_ID: ENTITY_ID,
                WaterHeaterServiceArgument.TEMPERATURE: 55,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    ("operation_mode", "expected_boost"),
    [
        (STATE_PERFORMANCE, True),
        (STATE_HEAT_PUMP, False),
    ],
)
async def test_set_operation_mode(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    operation_mode: str,
    expected_boost: bool,
) -> None:
    """Test setting the operation mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WaterHeaterService.SET_OPERATION_MODE,
        {
            TargetKey.ENTITY_ID: ENTITY_ID,
            WaterHeaterServiceArgument.OPERATION_MODE: operation_mode,
        },
        blocking=True,
    )

    mock_qube_client.write_switch.assert_awaited_once_with(
        "tapw_timeprogram_bms_forced", expected_boost
    )


@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        (ConnectionError, None),
        (None, False),
    ],
)
async def test_set_operation_mode_failure(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception] | None,
    return_value: bool | None,
) -> None:
    """Test set operation mode raises HomeAssistantError on failure."""
    await setup_integration(hass, mock_config_entry)

    mock_qube_client.write_switch = AsyncMock(
        side_effect=side_effect, return_value=return_value
    )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.SET_OPERATION_MODE,
            {
                TargetKey.ENTITY_ID: ENTITY_ID,
                WaterHeaterServiceArgument.OPERATION_MODE: STATE_PERFORMANCE,
            },
            blocking=True,
        )


async def test_current_operation_boost(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test current operation reflects boost mode."""
    mock_qube_client.read_all_switches.return_value["tapw_timeprogram_bms_forced"] = (
        True
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["operation_mode"] == STATE_PERFORMANCE


async def test_current_operation_unknown(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test current operation is unknown when the boost coil cannot be read."""
    mock_qube_client.read_all_switches.return_value["tapw_timeprogram_bms_forced"] = (
        None
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
