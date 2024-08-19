"""Tests for the BSBLAN climate platform."""

from unittest.mock import AsyncMock, MagicMock

from bsblan import BSBLANError, State
import pytest

from homeassistant.components.bsblan.climate import BSBLANClimate
from homeassistant.components.bsblan.const import DOMAIN
from homeassistant.components.bsblan.models import BSBLanCoordinatorData
from homeassistant.components.climate import PRESET_ECO, PRESET_NONE, HVACMode
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import MockConfigEntry


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
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
def climate_entity(hass: HomeAssistant, mock_coordinator, mock_bsblan):
    """Create a mock BSBLANClimate entity."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={"host": "test-host"})
    return BSBLANClimate(
        coordinator=mock_coordinator,
        client=mock_bsblan,
        device=MagicMock(MAC="00:11:22:33:44:55", name="Test Device"),
        info=MagicMock(device_identification=MagicMock(value="Test Model")),
        static=MagicMock(
            min_temp=MagicMock(value="10", unit="°C"),
            max_temp=MagicMock(value="30", unit="°C"),
        ),
        entry=config_entry,
    )


async def test_set_hvac_mode(hass: HomeAssistant, climate_entity) -> None:
    """Test setting HVAC mode."""
    await climate_entity.async_set_hvac_mode(HVACMode.HEAT)
    climate_entity.client.thermostat.assert_called_once_with(hvac_mode=HVACMode.HEAT)
    climate_entity.coordinator.async_request_refresh.assert_called_once()


async def test_set_preset_mode(
    hass: HomeAssistant, climate_entity, mock_coordinator
) -> None:
    """Test setting preset mode."""
    # Test setting preset mode when HVAC mode is AUTO
    mock_coordinator.data.state.hvac_mode.value = HVACMode.AUTO
    await climate_entity.async_set_preset_mode(PRESET_ECO)
    climate_entity.client.thermostat.assert_called_once_with(hvac_mode=PRESET_ECO)
    climate_entity.coordinator.async_request_refresh.assert_called_once()

    climate_entity.client.thermostat.reset_mock()
    climate_entity.coordinator.async_request_refresh.reset_mock()

    # Test setting preset mode when HVAC mode is not AUTO
    mock_coordinator.data.state.hvac_mode.value = HVACMode.HEAT
    with pytest.raises(ServiceValidationError):
        await climate_entity.async_set_preset_mode(PRESET_ECO)

    climate_entity.client.thermostat.assert_not_called()
    climate_entity.coordinator.async_request_refresh.assert_not_called()


async def test_set_temperature(hass: HomeAssistant, climate_entity) -> None:
    """Test setting temperature."""
    await climate_entity.async_set_temperature(temperature=23)
    climate_entity.client.thermostat.assert_called_once_with(target_temperature=23)
    climate_entity.coordinator.async_request_refresh.assert_called_once()


async def test_set_data_error(hass: HomeAssistant, climate_entity) -> None:
    """Test error handling when setting data."""
    climate_entity.client.thermostat.side_effect = BSBLANError("Test error")
    with pytest.raises(HomeAssistantError):
        await climate_entity.async_set_temperature(temperature=23)

    climate_entity.coordinator.async_request_refresh.assert_not_called()


async def test_update_state(
    hass: HomeAssistant, climate_entity, mock_coordinator
) -> None:
    """Test updating climate entity state."""
    mock_coordinator.data.state.current_temperature.value = "22.5"
    mock_coordinator.data.state.target_temperature.value = "23.0"
    mock_coordinator.data.state.hvac_mode.value = "auto"

    await hass.async_block_till_done()

    assert climate_entity.current_temperature == 22.5
    assert climate_entity.target_temperature == 23.0
    assert climate_entity.hvac_mode == HVACMode.AUTO


async def test_async_set_data(hass: HomeAssistant, climate_entity) -> None:
    """Test the async_set_data method."""
    await climate_entity.async_set_data(temperature=24, hvac_mode=HVACMode.COOL)
    climate_entity.client.thermostat.assert_called_once_with(
        target_temperature=24, hvac_mode=HVACMode.COOL
    )
    climate_entity.coordinator.async_request_refresh.assert_called_once()

    climate_entity.client.thermostat.reset_mock()
    climate_entity.coordinator.async_request_refresh.reset_mock()

    await climate_entity.async_set_data(preset_mode=PRESET_ECO)
    climate_entity.client.thermostat.assert_called_once_with(hvac_mode=PRESET_ECO)
    climate_entity.coordinator.async_request_refresh.assert_called_once()

    climate_entity.client.thermostat.reset_mock()
    climate_entity.coordinator.async_request_refresh.reset_mock()

    await climate_entity.async_set_data(preset_mode=PRESET_NONE)
    climate_entity.client.thermostat.assert_called_once_with(hvac_mode=HVACMode.AUTO)
    climate_entity.coordinator.async_request_refresh.assert_called_once()
