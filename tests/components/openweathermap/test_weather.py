"""Test the OpenWeatherMap weather entity."""

from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.openweathermap.const import (
    DOMAIN,
    OWM_MODE_FREE_CURRENT,
    OWM_MODE_FREE_FORECAST,
    OWM_MODE_V30,
    OWM_MODES,
)
from homeassistant.components.openweathermap.weather import SERVICE_GET_MINUTE_FORECAST
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "weather.openweathermap"


@pytest.mark.parametrize("mode", [OWM_MODE_V30], indirect=True)
async def test_get_minute_forecast(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    owm_client_mock: MagicMock,
    mode: str,
) -> None:
    """Test the get_minute_forecast Service call."""

    await setup_platform(hass, mock_config_entry, owm_client_mock, [Platform.WEATHER])
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MINUTE_FORECAST,
        {"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert result == snapshot(name="mock_service_response")


@pytest.mark.parametrize(
    "mode", [OWM_MODE_FREE_CURRENT, OWM_MODE_FREE_FORECAST], indirect=True
)
async def test_get_minute_forecast_unavailable(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    owm_client_mock: MagicMock,
    mode: str,
) -> None:
    """Test that Minute forecasting fails when mode is not v3.0."""

    await setup_platform(hass, mock_config_entry, owm_client_mock, [Platform.WEATHER])
    with pytest.raises(
        ServiceValidationError,
        match="Minute forecast is available only when OpenWeatherMap mode is set to v3.0",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MINUTE_FORECAST,
            {"entity_id": ENTITY_ID},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("mode", OWM_MODES, indirect=True)
async def test_weather_states(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    owm_client_mock: MagicMock,
) -> None:
    """Test weather states are correctly collected from library with different modes and mocked function responses."""

    await setup_platform(hass, mock_config_entry, owm_client_mock, [Platform.WEATHER])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
