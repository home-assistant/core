"""Tests for the Qube Heat Pump water heater platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    STATE_HEAT_PUMP,
    STATE_PERFORMANCE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

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
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 55},
        blocking=True,
    )

    mock_qube_client.write_setpoint.assert_awaited_once_with("setpoint_dhw", 55)


async def test_set_temperature_failure(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test set temperature raises HomeAssistantError on failure."""
    await setup_integration(hass, mock_config_entry)

    mock_qube_client.write_setpoint = AsyncMock(return_value=False)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 55},
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
        SERVICE_SET_OPERATION_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPERATION_MODE: operation_mode},
        blocking=True,
    )

    mock_qube_client.write_switch.assert_awaited_once_with(
        "tapw_timeprogram_bms_forced", expected_boost
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


@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        (ConnectionError("Connection lost"), None),
        (None, None),
    ],
)
async def test_water_heater_unavailable_on_coordinator_error(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception | None,
    return_value: None,
) -> None:
    """Test water heater becomes unavailable when coordinator fails."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    mock_qube_client.get_all_data = AsyncMock(
        side_effect=side_effect, return_value=return_value
    )

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
