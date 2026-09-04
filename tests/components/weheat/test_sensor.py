"""Tests for the weheat sensor platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from weheat.abstractions.discovery import HeatPumpDiscovery

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_weheat_discover: AsyncMock,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(("has_dhw", "nr_of_entities"), [(False, 25), (True, 32)])
async def test_create_entities(
    hass: HomeAssistant,
    mock_weheat_discover: AsyncMock,
    mock_weheat_heat_pump: AsyncMock,
    mock_heat_pump_info: HeatPumpDiscovery.HeatPumpInfo,
    mock_config_entry: MockConfigEntry,
    has_dhw: bool,
    nr_of_entities: int,
) -> None:
    """Test creating entities."""
    mock_heat_pump_info.has_dhw = has_dhw
    mock_weheat_discover.return_value = [mock_heat_pump_info]

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == nr_of_entities


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        pytest.param(55, "55", id="a_target_it_aims_for"),
        # DHW control off reports a target of zero, which is no target at all
        pytest.param(0, STATE_UNKNOWN, id="dhw_control_off"),
    ],
)
@pytest.mark.usefixtures("mock_weheat_discover")
async def test_dhw_target_temperature(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
    target: int,
    expected: str,
) -> None:
    """Test the DHW target is only reported when the heat pump has one."""
    mock_weheat_heat_pump.dhw_target_temperature = target

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_model_dhw_target_temperature").state == expected


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_an_unknown_dhw_control_method_keeps_the_sensor(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a control method this library cannot name still gets a sensor.

    The heat pump keeps reporting the raw method, so the sensor has to survive
    the backend introducing one, ready to name it once the library knows it.
    """
    mock_weheat_heat_pump.dhw_control_method = None
    mock_weheat_heat_pump.dhw_control_method_code = 99

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("sensor.test_model_dhw_control_method").state == STATE_UNKNOWN
    )
