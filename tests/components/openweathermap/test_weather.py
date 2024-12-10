"""Test the OpenWeatherMap weather entity."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.openweathermap.const import (
    DEFAULT_LANGUAGE,
    DOMAIN,
    OWM_MODE_V25,
    OWM_MODE_V30,
)
from homeassistant.components.openweathermap.weather import SERVICE_GET_MINUTE_FORECAST
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .const import MINUTE_FORECAST

from tests.common import MockConfigEntry, load_fixture

ENTITY_ID = "weather.openweathermap"


@pytest.fixture(autouse=True)
def mock_config_entry():
    """Create a mock OpenWeatherMap config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "test_api_key",
            CONF_LATITUDE: 12.34,
            CONF_LONGITUDE: 56.78,
            CONF_NAME: "OpenWeatherMap",
        },
        options={CONF_MODE: OWM_MODE_V30, CONF_LANGUAGE: DEFAULT_LANGUAGE},
        version=5,
    )


@pytest.mark.asyncio
@patch(
    "pyopenweathermap.http_client.HttpClient.request",
    new_callable=AsyncMock,
    return_value=json.loads(load_fixture("openweathermap.json", "openweathermap")),
)
async def test_minute_forecast(
    mock_api_response, hass: HomeAssistant, mock_config_entry
) -> None:
    """Test the OpenWeatherMapWeather Minute forecast."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data

    assert mock_config_entry.state == ConfigEntryState.LOADED

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry is not None

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MINUTE_FORECAST,
        {"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert result == MINUTE_FORECAST

    # Test exception when mode is not OWM_MODE_V30
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, CONF_MODE: OWM_MODE_V25},
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Expect a ServiceValidationError when mode is not OWM_MODE_V30
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MINUTE_FORECAST,
            {"entity_id": ENTITY_ID},
            blocking=True,
            return_response=True,
        )

    # Cleanup
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
