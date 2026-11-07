"""Test the OpenWeatherMap weather entity."""

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.openweathermap.const import (
    DOMAIN,
    OWM_MODE_FREE_CURRENT,
    OWM_MODE_FREE_FORECAST,
    OWM_MODE_V30,
    OWM_MODE_V40,
)
from homeassistant.components.openweathermap.services import SERVICE_GET_MINUTE_FORECAST
from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_platform

ENTITY_ID = "weather.openweathermap"


@pytest.mark.parametrize("mode", [OWM_MODE_V30, OWM_MODE_V40], indirect=True)
@pytest.mark.usefixtures("owm_client_mock")
async def test_get_minute_forecast(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the get_minute_forecast Service call."""

    await setup_platform(hass, mock_config_entry, [Platform.WEATHER])
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
@pytest.mark.usefixtures("owm_client_mock")
async def test_get_minute_forecast_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test minute forecasting is unavailable for the free API."""

    await setup_platform(hass, mock_config_entry, [Platform.WEATHER])
    with pytest.raises(
        ServiceValidationError,
        match="Minute forecast is available only when"
        r" OpenWeatherMap mode is set to v3\.0 or v4\.0",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MINUTE_FORECAST,
            {"entity_id": ENTITY_ID},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    "mode",
    [OWM_MODE_V30, OWM_MODE_V40, OWM_MODE_FREE_CURRENT, OWM_MODE_FREE_FORECAST],
    indirect=True,
)
@pytest.mark.usefixtures("owm_client_mock")
async def test_weather_states(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test weather states are collected from library correctly."""

    await setup_platform(hass, mock_config_entry, [Platform.WEATHER])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("mode", [OWM_MODE_V30, OWM_MODE_V40], indirect=True)
@pytest.mark.parametrize("forecast_type", ["daily", "hourly"])
@pytest.mark.usefixtures("owm_client_mock")
async def test_weather_forecast(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    forecast_type: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test One Call forecasts are exposed through the weather action."""
    await setup_platform(hass, mock_config_entry, [Platform.WEATHER])
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": ENTITY_ID, "type": forecast_type},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
