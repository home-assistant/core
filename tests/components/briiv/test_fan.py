"""Test the Briiv fan platform."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.briiv.const import PRESET_MODE_BOOST
from homeassistant.components.briiv.fan import BriivFan
from homeassistant.components.fan import FanEntityFeature, NotValidPresetModeError
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_api():
    """Mock Briiv API."""
    api = AsyncMock()
    api.set_power = AsyncMock()
    api.set_fan_speed = AsyncMock()
    api.set_boost = AsyncMock()
    api.remove_callback = AsyncMock()
    return api


async def test_fan_initialization(mock_api) -> None:
    """Test fan entity initialization."""
    fan = BriivFan(mock_api, "TEST123")

    assert fan.unique_id == "TEST123_fan"
    assert fan.name is None  # Uses device name
    assert fan.supported_features == (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    assert fan.preset_modes == [PRESET_MODE_BOOST]
    assert not fan.is_on
    assert fan.percentage is None
    assert fan.preset_mode is None


async def test_fan_turn_on(hass: HomeAssistant, mock_api) -> None:
    """Test turning on the fan."""
    fan = BriivFan(mock_api, "TEST123")

    await fan.async_turn_on()

    mock_api.set_power.assert_called_once_with(True)
    mock_api.set_fan_speed.assert_called_once_with(25)  # Default speed
    assert fan.is_on
    assert fan.percentage == 25


async def test_fan_turn_on_with_speed(hass: HomeAssistant, mock_api) -> None:
    """Test turning on the fan with specific speed."""
    fan = BriivFan(mock_api, "TEST123")

    await fan.async_turn_on(percentage=75)

    mock_api.set_power.assert_called_once_with(True)
    mock_api.set_fan_speed.assert_called_once_with(75)
    assert fan.is_on
    assert fan.percentage == 75


async def test_fan_turn_on_with_boost(hass: HomeAssistant, mock_api) -> None:
    """Test turning on the fan in boost mode."""
    fan = BriivFan(mock_api, "TEST123")

    await fan.async_turn_on(preset_mode=PRESET_MODE_BOOST)

    mock_api.set_power.assert_called_once_with(True)
    mock_api.set_boost.assert_called_once_with(True)
    assert fan.is_on
    assert fan.percentage == 100
    assert fan.preset_mode == PRESET_MODE_BOOST


async def test_fan_turn_off(hass: HomeAssistant, mock_api) -> None:
    """Test turning off the fan."""
    fan = BriivFan(mock_api, "TEST123")
    fan._attr_is_on = True
    fan._attr_percentage = 75

    await fan.async_turn_off()

    mock_api.set_power.assert_called_once_with(False)
    assert not fan.is_on
    assert fan.percentage == 0


async def test_fan_set_percentage(hass: HomeAssistant, mock_api) -> None:
    """Test setting fan percentage."""
    fan = BriivFan(mock_api, "TEST123")

    await fan.async_set_percentage(50)

    mock_api.set_power.assert_called_once_with(True)
    mock_api.set_fan_speed.assert_called_once_with(50)
    assert fan.is_on
    assert fan.percentage == 50


async def test_fan_set_percentage_with_boost_active(
    hass: HomeAssistant, mock_api
) -> None:
    """Test setting percentage while boost is active."""
    fan = BriivFan(mock_api, "TEST123")
    fan._attr_preset_mode = PRESET_MODE_BOOST

    await fan.async_set_percentage(50)

    mock_api.set_boost.assert_called_once_with(False)
    mock_api.set_fan_speed.assert_called_once_with(50)
    assert fan.preset_mode is None
    assert fan.percentage == 50


async def test_fan_set_preset_mode(hass: HomeAssistant, mock_api) -> None:
    """Test setting fan preset mode."""
    fan = BriivFan(mock_api, "TEST123")

    await fan.async_set_preset_mode(PRESET_MODE_BOOST)

    mock_api.set_power.assert_called_once_with(True)
    mock_api.set_boost.assert_called_once_with(True)
    assert fan.preset_mode == PRESET_MODE_BOOST
    assert fan.percentage == 100
    assert fan.is_on


async def test_fan_invalid_preset_mode(hass: HomeAssistant, mock_api) -> None:
    """Test setting invalid preset mode."""
    fan = BriivFan(mock_api, "TEST123")

    with pytest.raises(NotValidPresetModeError):
        await fan.async_set_preset_mode("invalid_mode")


async def test_fan_update_callback(hass: HomeAssistant, mock_api) -> None:
    """Test update callback handling."""
    fan = BriivFan(mock_api, "TEST123")

    # Test power update
    await fan._handle_update({"power": 1})
    assert fan.is_on

    # Test fan speed update
    await fan._handle_update({"fan_speed": 75})
    assert fan.percentage == 75

    # Test boost mode update
    await fan._handle_update({"boost": 1})
    assert fan.preset_mode == PRESET_MODE_BOOST
    assert fan.percentage == 100

    # Test turning off
    await fan._handle_update({"power": 0})
    assert not fan.is_on
    assert fan.percentage == 0


async def test_fan_remove_callback(hass: HomeAssistant, mock_api) -> None:
    """Test callback removal when entity is removed."""
    fan = BriivFan(mock_api, "TEST123")

    await fan.async_will_remove_from_hass()
    mock_api.remove_callback.assert_called_once_with(fan._handle_update)
