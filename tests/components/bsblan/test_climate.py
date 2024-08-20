"""Tests for the BSBLAN climate platform."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from bsblan import BSBLANError, State
import pytest

from homeassistant.components.bsblan.climate import (
    PRESET_ECO,
    PRESET_NONE,
    BSBLANClimate,
    HVACMode,
)
from homeassistant.components.bsblan.const import DOMAIN
from homeassistant.components.bsblan.coordinator import BSBLanUpdateCoordinator
from homeassistant.components.bsblan.models import BSBLanCoordinatorData, BSBLanData
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.1.100", "port": 80, "passkey": "passkey"},
        entry_id="test",
    )


@pytest.fixture
def mock_coordinator(hass: HomeAssistant, mock_config_entry) -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=BSBLanUpdateCoordinator)
    coordinator.config_entry = mock_config_entry
    coordinator.bsblan_config_entry = mock_config_entry
    coordinator.data = BSBLanCoordinatorData(
        state=State.from_dict(
            {
                "current_temperature": MagicMock(value="21.5"),
                "target_temperature": MagicMock(value="22.0"),
                "hvac_mode": MagicMock(value="heat"),
                "hvac_mode2": MagicMock(value="2"),
                "hvac_action": MagicMock(value="122"),
                "outside_temperature": MagicMock(value="6.1"),
                "target_temperature_high": MagicMock(value="23.0"),
                "target_temperature_low": MagicMock(value="17.0"),
                "min_temp": MagicMock(value="8.0"),
                "max_temp": MagicMock(value="20.0"),
                "room1_thermostat_mode": MagicMock(value="0"),
            }
        ),
        sensor=MagicMock(),
    )
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def mock_bsblan_data(mock_coordinator, mock_bsblan) -> MagicMock:
    """Create a mock BSBLanData instance."""
    return BSBLanData(
        coordinator=mock_coordinator,
        client=mock_bsblan,
        device=MagicMock(MAC="00:11:22:33:44:55", name="Test Device"),
        info=MagicMock(device_identification=MagicMock(value="Test Model")),
        static=MagicMock(
            min_temp=MagicMock(value="10", unit="°C"),
            max_temp=MagicMock(value="30", unit="°C"),
        ),
    )


@pytest.fixture
def climate_entity(mock_bsblan_data) -> BSBLANClimate:
    """Create a mock BSBLANClimate entity."""
    return BSBLANClimate(mock_bsblan_data)


async def test_climate_temperature_unit(climate_entity) -> None:
    """Test the temperature unit of the climate entity."""
    with patch(
        "homeassistant.components.bsblan.climate.BSBLANClimate.temperature_unit",
        new_callable=PropertyMock,
    ) as mock_temp_unit:
        mock_temp_unit.return_value = UnitOfTemperature.CELSIUS
        assert climate_entity.temperature_unit == UnitOfTemperature.CELSIUS

        climate_entity._data.static.min_temp.unit = "°F"
        mock_temp_unit.return_value = UnitOfTemperature.FAHRENHEIT
        assert climate_entity.temperature_unit == UnitOfTemperature.FAHRENHEIT

        climate_entity._data.static.min_temp.unit = "°C"
        mock_temp_unit.return_value = UnitOfTemperature.CELSIUS
        assert climate_entity.temperature_unit == UnitOfTemperature.CELSIUS


async def test_climate_current_temperature(climate_entity, mock_coordinator) -> None:
    """Test the current temperature property."""
    # Ensure the mock data is set correctly
    mock_coordinator.data.state.current_temperature.value = "21.5"

    # Force an update of the climate entity
    await climate_entity.async_update()

    assert climate_entity.current_temperature == 21.5

    mock_coordinator.data.state.current_temperature.value = "---"
    await climate_entity.async_update()
    assert climate_entity.current_temperature is None


async def test_climate_target_temperature(climate_entity, mock_coordinator) -> None:
    """Test the target temperature property."""
    mock_coordinator.data.state.target_temperature.value = "22.0"
    await climate_entity.async_update()
    assert climate_entity.target_temperature == 22.0


async def test_climate_hvac_mode(climate_entity, mock_coordinator) -> None:
    """Test the HVAC mode property."""
    mock_coordinator.data.state.hvac_mode.value = HVACMode.HEAT
    await climate_entity.async_update()
    assert climate_entity.hvac_mode == HVACMode.HEAT

    mock_coordinator.data.state.hvac_mode.value = HVACMode.AUTO
    await climate_entity.async_update()
    assert climate_entity.hvac_mode == HVACMode.AUTO

    mock_coordinator.data.state.hvac_mode.value = PRESET_ECO
    await climate_entity.async_update()
    assert climate_entity.hvac_mode == HVACMode.AUTO


async def test_climate_preset_mode(climate_entity, mock_coordinator) -> None:
    """Test the preset mode property."""
    mock_coordinator.data.state.hvac_mode.value = HVACMode.HEAT
    await climate_entity.async_update()
    assert climate_entity.preset_mode == PRESET_NONE

    mock_coordinator.data.state.hvac_mode.value = HVACMode.AUTO
    await climate_entity.async_update()
    assert climate_entity.preset_mode == PRESET_NONE

    mock_coordinator.data.state.hvac_mode.value = PRESET_ECO
    await climate_entity.async_update()
    assert climate_entity.preset_mode == PRESET_ECO


async def test_set_temperature(
    hass: HomeAssistant, climate_entity, mock_bsblan
) -> None:
    """Test setting the temperature."""
    await climate_entity.async_set_temperature(temperature=23)
    climate_entity._data.client.thermostat.assert_called_once_with(
        target_temperature=23
    )
    climate_entity.coordinator.async_request_refresh.assert_called_once()


async def test_set_hvac_mode(hass: HomeAssistant, climate_entity, mock_bsblan) -> None:
    """Test setting the HVAC mode."""
    await climate_entity.async_set_hvac_mode(HVACMode.AUTO)
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=HVACMode.AUTO)
    climate_entity.coordinator.async_request_refresh.assert_called_once()


async def test_set_preset_mode(
    hass: HomeAssistant, climate_entity, mock_bsblan
) -> None:
    """Test setting the preset mode."""
    climate_entity.coordinator.data.state.hvac_mode.value = HVACMode.AUTO

    await climate_entity.async_set_preset_mode(PRESET_ECO)
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=PRESET_ECO)
    climate_entity.coordinator.async_request_refresh.assert_called_once()

    mock_bsblan.thermostat.reset_mock()
    climate_entity.coordinator.async_request_refresh.reset_mock()

    await climate_entity.async_set_preset_mode(PRESET_NONE)
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=HVACMode.AUTO)
    climate_entity.coordinator.async_request_refresh.assert_called_once()


async def test_set_preset_mode_error(hass: HomeAssistant, climate_entity) -> None:
    """Test setting preset mode when HVAC mode is not AUTO."""
    climate_entity.coordinator.data.state.hvac_mode.value = HVACMode.HEAT

    with pytest.raises(ServiceValidationError):
        await climate_entity.async_set_preset_mode(PRESET_ECO)


async def test_set_data_error(hass: HomeAssistant, climate_entity, mock_bsblan) -> None:
    """Test error handling when setting data."""
    mock_bsblan.thermostat.side_effect = BSBLANError("Test error")

    with pytest.raises(HomeAssistantError):
        await climate_entity.async_set_temperature(temperature=23)

    climate_entity.coordinator.async_request_refresh.assert_not_called()


async def test_async_set_data(hass: HomeAssistant, climate_entity, mock_bsblan) -> None:
    """Test the async_set_data method."""
    await climate_entity.async_set_data(temperature=24, hvac_mode=HVACMode.HEAT)
    mock_bsblan.thermostat.assert_called_once_with(
        target_temperature=24, hvac_mode=HVACMode.HEAT
    )
    climate_entity.coordinator.async_request_refresh.assert_called_once()

    mock_bsblan.thermostat.reset_mock()
    climate_entity.coordinator.async_request_refresh.reset_mock()

    await climate_entity.async_set_data(preset_mode=PRESET_ECO)
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=PRESET_ECO)
    climate_entity.coordinator.async_request_refresh.assert_called_once()

    mock_bsblan.thermostat.reset_mock()
    climate_entity.coordinator.async_request_refresh.reset_mock()

    await climate_entity.async_set_data(preset_mode=PRESET_NONE)
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=HVACMode.AUTO)
    climate_entity.coordinator.async_request_refresh.assert_called_once()
