"""Tests for the BSBLAN climate component."""

from unittest.mock import AsyncMock, MagicMock

from bsblan import BSBLANError, State
import pytest

from homeassistant.components.bsblan.climate import BSBLANClimate
from homeassistant.components.bsblan.coordinator import BSBLanCoordinatorData
from homeassistant.components.climate import PRESET_ECO, PRESET_NONE, HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


class MockStateValue:
    """Mock class for a BSBLan State value."""

    def __init__(self, value) -> None:
        """Initialize the mock class."""
        self.value = value


@pytest.fixture
def mock_state() -> MagicMock:
    """Create a mock BSBLan State object."""
    state = MagicMock(spec=State)
    state.current_temperature = MockStateValue("22.5")
    state.target_temperature = MockStateValue("21.0")
    state.hvac_mode = MockStateValue("heat")
    return state


@pytest.fixture
def coordinator_mock(mock_state) -> MagicMock:
    """Create a mock BSBLan coordinator."""
    coordinator = AsyncMock()
    coordinator.data = BSBLanCoordinatorData(state=mock_state())
    return coordinator


@pytest.fixture
def mock_bsblan_data(coordinator_mock) -> MagicMock:
    """Create a mock BSBLanData object."""

    # Create a mock BSBLanData object
    class MockBSBLanData:
        coordinator = coordinator_mock
        device = AsyncMock()
        device.MAC = "00:11:22:33:44:55"
        info = AsyncMock()
        static = AsyncMock()
        static.min_temp.value = "10.0"
        static.max_temp.value = "30.0"
        static.min_temp.unit = "&deg;C"

    return MockBSBLanData()


@pytest.fixture
def climate(mock_bsblan_data) -> BSBLANClimate:
    """Create a BSBLANClimate object."""
    return BSBLANClimate(mock_bsblan_data)


async def test_current_temperature_missing(climate, coordinator_mock) -> None:
    """Test the current temperature property when the value is missing."""
    coordinator_mock.data.state.current_temperature.value = "---"
    assert climate.current_temperature is None


async def test_current_temperature_valid(climate, coordinator_mock) -> None:
    """Test the current temperature property when the value is valid."""
    coordinator_mock.data.state.current_temperature.value = "22.5"
    assert climate.current_temperature == 22.5


async def test_target_temperature(climate, coordinator_mock) -> None:
    """Test the target temperature property."""
    coordinator_mock.data.state.target_temperature.value = "21.0"
    assert climate.target_temperature == 21.0


async def test_hvac_mode(climate, coordinator_mock) -> None:
    """Test the hvac mode property."""
    coordinator_mock.data.state.hvac_mode.value = HVACMode.HEAT
    assert climate.hvac_mode == HVACMode.HEAT

    coordinator_mock.data.state.hvac_mode.value = PRESET_ECO
    assert climate.hvac_mode == HVACMode.AUTO


async def test_preset_mode(climate, coordinator_mock) -> None:
    """Test the preset mode property."""
    coordinator_mock.data.state.hvac_mode.value = HVACMode.AUTO
    assert climate.preset_mode == PRESET_NONE

    coordinator_mock.data.state.hvac_mode.value = PRESET_ECO
    assert climate.preset_mode == PRESET_ECO


async def test_async_set_hvac_mode(climate) -> None:
    """Test setting the hvac mode."""
    climate.async_set_data = AsyncMock()
    await climate.async_set_hvac_mode(HVACMode.HEAT)
    climate.async_set_data.assert_called_once_with(hvac_mode=HVACMode.HEAT)


async def test_async_set_preset_mode_auto(climate, coordinator_mock) -> None:
    """Test setting the preset mode when the hvac mode is auto."""
    climate.async_set_data = AsyncMock()
    coordinator_mock.data.state.hvac_mode.value = HVACMode.AUTO
    await climate.async_set_preset_mode(PRESET_ECO)
    climate.async_set_data.assert_called_once_with(preset_mode=PRESET_ECO)


async def test_async_set_preset_mode_not_auto(climate, coordinator_mock) -> None:
    """Test setting the preset mode when the hvac mode is not auto."""
    climate.async_set_data = AsyncMock()
    coordinator_mock.data.state.hvac_mode.value = HVACMode.HEAT
    with pytest.raises(ServiceValidationError):
        await climate.async_set_preset_mode(PRESET_ECO)


async def test_async_set_temperature(climate) -> None:
    """Test setting the temperature."""
    climate.async_set_data = AsyncMock()
    await climate.async_set_temperature(temperature=22.0)
    climate.async_set_data.assert_called_once_with(temperature=22.0)


async def test_async_set_data_temperature(climate) -> None:
    """Test setting the temperature."""
    climate.coordinator.client.thermostat = AsyncMock()
    climate.coordinator.async_request_refresh = AsyncMock()
    await climate.async_set_data(temperature=22.0)
    climate.coordinator.client.thermostat.assert_called_once_with(
        target_temperature=22.0
    )
    climate.coordinator.async_request_refresh.assert_called_once()


async def test_async_set_data_hvac_mode(climate) -> None:
    """Test setting the hvac mode."""
    climate.coordinator.client.thermostat = AsyncMock()
    climate.coordinator.async_request_refresh = AsyncMock()
    await climate.async_set_data(hvac_mode=HVACMode.HEAT)
    climate.coordinator.client.thermostat.assert_called_once_with(
        hvac_mode=HVACMode.HEAT
    )
    climate.coordinator.async_request_refresh.assert_called_once()


async def test_async_set_data_preset_mode(climate) -> None:
    """Test setting the preset mode."""
    climate.coordinator.client.thermostat = AsyncMock()
    climate.coordinator.async_request_refresh = AsyncMock()
    await climate.async_set_data(preset_mode=PRESET_ECO)
    climate.coordinator.client.thermostat.assert_called_once_with(hvac_mode=PRESET_ECO)
    climate.coordinator.async_request_refresh.assert_called_once()


async def test_async_set_data_preset_mode_none(climate) -> None:
    """Test setting the preset mode to none."""
    climate.coordinator.client.thermostat = AsyncMock()
    climate.coordinator.async_request_refresh = AsyncMock()
    await climate.async_set_data(preset_mode=PRESET_NONE)
    climate.coordinator.client.thermostat.assert_called_once_with(
        hvac_mode=HVACMode.AUTO
    )
    climate.coordinator.async_request_refresh.assert_called_once()


async def test_async_set_data_error(climate) -> None:
    """Test setting the data with an error."""
    climate.coordinator.client.thermostat = AsyncMock(side_effect=BSBLANError)
    with pytest.raises(HomeAssistantError):
        await climate.async_set_data(temperature=22.0)


async def test_temperature_unit(climate, mock_bsblan_data) -> None:
    """Test the temperature unit property."""
    assert climate.temperature_unit == UnitOfTemperature.CELSIUS

    mock_bsblan_data.static.min_temp.unit = "F"
    climate = BSBLANClimate(mock_bsblan_data)
    assert climate.temperature_unit == UnitOfTemperature.FAHRENHEIT
