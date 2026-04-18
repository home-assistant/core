"""Tests for the Hisense climate platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_MEDIUM,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.hisense_connectlife.climate import HisenseClimate
from homeassistant.components.hisense_connectlife.const import StatusKey
from homeassistant.components.hisense_connectlife.models import DeviceInfo
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant

DEVICE_ID = "test_device_123"
PUID = "test_puid_123"


@pytest.fixture
def mock_device():
    """Mock a Hisense device."""
    mock_dev = MagicMock(spec=DeviceInfo)
    mock_dev.device_id = DEVICE_ID
    mock_dev.puid = PUID
    mock_dev.name = "Test AC"
    mock_dev.type_code = "009"
    mock_dev.feature_code = "19901"
    mock_dev.type_name = "Air Conditioner"
    mock_dev.feature_name = "Standard"
    mock_dev.is_online = True
    mock_dev.is_supported = MagicMock(return_value=True)
    mock_dev.status = {
        StatusKey.POWER: "1",
        StatusKey.MODE: "0",
        StatusKey.TEMPERATURE: "25",
        StatusKey.TARGET_TEMP: "24",
        StatusKey.FAN_SPEED: "0",
        StatusKey.SWING: "0",
    }

    def get_status_value(key):
        return mock_dev.status.get(key)

    mock_dev.get_status_value = get_status_value
    mock_dev.get_device_type = MagicMock(
        return_value=MagicMock(type_code="009", feature_code="19901")
    )
    return mock_dev


@pytest.fixture
def mock_coordinator(mock_device):
    """Mock a coordinator."""
    coordinator = MagicMock()
    coordinator.data = {PUID: mock_device}
    coordinator.get_device = MagicMock(return_value=mock_device)
    coordinator.async_control_device = AsyncMock()
    coordinator.api_client = MagicMock()

    mock_attr_mode = MagicMock()
    mock_attr_mode.value_map = {
        "0": "cool",
        "1": "heat",
        "2": "dry",
        "3": "fan_only",
        "4": "auto",
    }

    mock_attr_fan = MagicMock()
    mock_attr_fan.value_map = {"0": "auto", "1": "low", "2": "medium", "3": "high"}

    mock_attr_swing = MagicMock()
    mock_attr_swing.value_map = {"0": "off", "1": "vertical"}

    mock_attr_temp = MagicMock()
    mock_attr_temp.value_range = "16~30"

    mock_parser = MagicMock()
    mock_parser.attributes = {
        StatusKey.MODE: mock_attr_mode,
        StatusKey.FAN_SPEED: mock_attr_fan,
        StatusKey.SWING: mock_attr_swing,
        StatusKey.TARGET_TEMP: mock_attr_temp,
    }

    coordinator.api_client.parsers = {DEVICE_ID: mock_parser}
    coordinator.api_client.static_data = {
        DEVICE_ID: {
            "Mode_settings": "1",
            "Wind_speed_gear_selection": "9",
            "Left_and_right_damper_control": "1",
            "Upper_and_lower_damper_control": "1",
        }
    }
    return coordinator


@pytest.fixture
async def entity(hass: HomeAssistant, mock_coordinator, mock_device):
    """Create a test climate entity."""
    entity = HisenseClimate(mock_coordinator, mock_device)
    entity.hass = hass
    # 🔥 修复关键：手动设置 entity_id
    entity.entity_id = "climate.test_ac_device"
    return entity


async def test_climate_initialization(entity) -> None:
    """Test climate entity initialization."""
    assert entity.unique_id == f"{DEVICE_ID}_climate"
    assert entity.name == "Test AC Device"
    assert entity.available is True
    assert entity.temperature_unit == UnitOfTemperature.CELSIUS
    assert entity.min_temp == 16
    assert entity.max_temp == 30


async def test_current_temperature(entity) -> None:
    """Test current temperature."""
    assert entity.current_temperature == 25.0


async def test_target_temperature(entity) -> None:
    """Test target temperature."""
    assert entity.target_temperature == 24.0


async def test_hvac_mode(entity) -> None:
    """Test HVAC mode."""
    assert entity.hvac_mode == HVACMode.COOL
    entity._device.status[StatusKey.POWER] = "0"
    assert entity.hvac_mode == HVACMode.OFF


async def test_fan_mode(entity) -> None:
    """Test fan mode."""
    assert entity.fan_mode == FAN_AUTO


async def test_swing_mode(entity) -> None:
    """Test swing mode."""
    assert entity.swing_mode == SWING_OFF


async def test_supported_features(entity) -> None:
    """Test supported features."""
    features = entity.supported_features
    assert ClimateEntityFeature.TARGET_TEMPERATURE in features
    assert ClimateEntityFeature.FAN_MODE in features
    assert ClimateEntityFeature.SWING_MODE in features


async def test_async_set_temperature(entity) -> None:
    """Test setting target temperature."""
    await entity.async_set_temperature(**{ATTR_TEMPERATURE: 26})
    entity.coordinator.async_control_device.assert_awaited_once_with(
        puid=PUID, properties={StatusKey.TARGET_TEMP: "26"}
    )


async def test_async_set_hvac_mode(entity) -> None:
    """Test setting HVAC mode."""
    await entity.async_set_hvac_mode(HVACMode.HEAT)
    assert entity.coordinator.async_control_device.await_count >= 1


async def test_async_set_fan_mode(entity) -> None:
    """Test setting fan mode."""
    await entity.async_set_fan_mode(FAN_MEDIUM)
    entity.coordinator.async_control_device.assert_awaited()


async def test_async_set_swing_mode(entity) -> None:
    """Test setting swing mode."""
    await entity.async_set_swing_mode(SWING_VERTICAL)
    entity.coordinator.async_control_device.assert_awaited()


async def test_async_turn_on_off(entity) -> None:
    """Test turn on and off."""
    await entity.async_turn_on()
    entity.coordinator.async_control_device.assert_awaited_with(
        puid=PUID, properties={StatusKey.POWER: "1"}
    )

    await entity.async_turn_off()
    entity.coordinator.async_control_device.assert_awaited_with(
        puid=PUID, properties={StatusKey.POWER: "0"}
    )
