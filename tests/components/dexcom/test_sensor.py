"""The sensor tests for the Dexcom platform."""

from unittest.mock import MagicMock

from pydexcom import GlucoseReading
from pydexcom.errors import (
    AccountError,
    AccountErrorEnum,
    ServerError,
    ServerErrorEnum,
    SessionError,
    SessionErrorEnum,
)
import pytest

from homeassistant.components.dexcom.sensor import TRENDS
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import TEST_USERNAME, init_integration

from tests.common import MockConfigEntry


async def test_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dexcom: MagicMock,
    mock_glucose_reading: GlucoseReading,
) -> None:
    """Test we get sensor data."""
    mock_dexcom.get_current_glucose_reading.return_value = mock_glucose_reading

    await init_integration(hass, mock_config_entry)

    glucose_value = hass.states.get(f"sensor.{TEST_USERNAME}_glucose_value")
    assert glucose_value is not None
    assert glucose_value.state == str(mock_glucose_reading.mg_dl)

    glucose_trend = hass.states.get(f"sensor.{TEST_USERNAME}_glucose_trend")
    assert glucose_trend is not None
    assert glucose_trend.state == TRENDS.get(mock_glucose_reading.trend)


async def test_sensor_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dexcom: MagicMock,
) -> None:
    """Test we get sensor data."""
    mock_dexcom.get_current_glucose_reading.return_value = None

    await init_integration(hass, mock_config_entry)

    glucose_value = hass.states.get(f"sensor.{TEST_USERNAME}_glucose_value")
    assert glucose_value is not None
    assert glucose_value.state == STATE_UNKNOWN

    glucose_trend = hass.states.get(f"sensor.{TEST_USERNAME}_glucose_trend")
    assert glucose_trend is not None
    assert glucose_trend.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "error",
    [
        SessionError(SessionErrorEnum.INVALID),
        ServerError(ServerErrorEnum.UNEXPECTED),
        Exception,
    ],
)
async def test_sensor_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dexcom: MagicMock,
    error: Exception,
) -> None:
    """Test we get sensor data."""
    mock_dexcom.get_current_glucose_reading.side_effect = error

    await init_integration(hass, mock_config_entry)

    glucose_value = hass.states.get(f"sensor.{TEST_USERNAME}_glucose_value")
    assert glucose_value is None

    glucose_trend = hass.states.get(f"sensor.{TEST_USERNAME}_glucose_trend")
    assert glucose_trend is None


async def test_sensor_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dexcom: MagicMock,
) -> None:
    """Test we get sensor data."""
    mock_dexcom.get_current_glucose_reading.side_effect = AccountError(
        AccountErrorEnum.FAILED_AUTHENTICATION
    )

    await init_integration(hass, mock_config_entry)

    glucose_value = hass.states.get(f"sensor.{TEST_USERNAME}_glucose_value")
    assert glucose_value is None

    glucose_trend = hass.states.get(f"sensor.{TEST_USERNAME}_glucose_trend")
    assert glucose_trend is None
