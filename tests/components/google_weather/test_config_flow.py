"""Test the Google Weather config flow."""

from unittest.mock import AsyncMock, patch

from google_weather_api import GoogleWeatherApiError
import pytest

from homeassistant import config_entries
from homeassistant.components.google_weather.const import CONF_REFERRER, DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.google_weather.config_flow.GoogleWeatherApi.async_get_current_conditions",
    ) as mock_get_current_conditions:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test-name",
                CONF_API_KEY: "test-api-key",
                CONF_LOCATION: {
                    CONF_LATITUDE: 10.1,
                    CONF_LONGITUDE: 20.1,
                },
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
        CONF_REFERRER: None,
        CONF_LATITUDE: 10.1,
        CONF_LONGITUDE: 20.1,
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_get_current_conditions.call_count == 1


async def test_form_with_referrer(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form and optional referrer is specified."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.google_weather.config_flow.GoogleWeatherApi.async_get_current_conditions",
    ) as mock_get_current_conditions:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test-name",
                CONF_API_KEY: "test-api-key",
                CONF_REFERRER: "test-referrer",
                CONF_LOCATION: {
                    CONF_LATITUDE: 10.1,
                    CONF_LONGITUDE: 20.1,
                },
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
        CONF_REFERRER: "test-referrer",
        CONF_LATITUDE: 10.1,
        CONF_LONGITUDE: 20.1,
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_get_current_conditions.call_count == 1


@pytest.mark.parametrize(
    ("api_exception", "expected_error"),
    [
        (GoogleWeatherApiError(), "cannot_connect"),
        (ValueError(), "unknown"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    api_exception,
    expected_error,
) -> None:
    """Test we handle exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.google_weather.config_flow.GoogleWeatherApi.async_get_current_conditions",
        side_effect=api_exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test-name",
                CONF_API_KEY: "test-api-key",
                CONF_LOCATION: {
                    CONF_LATITUDE: 10.1,
                    CONF_LONGITUDE: 20.1,
                },
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch(
        "homeassistant.components.google_weather.config_flow.GoogleWeatherApi.async_get_current_conditions",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test-name",
                CONF_API_KEY: "test-api-key",
                CONF_LOCATION: {
                    CONF_LATITUDE: 10.1,
                    CONF_LONGITUDE: 20.1,
                },
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
        CONF_REFERRER: None,
        CONF_LATITUDE: 10.1,
        CONF_LONGITUDE: 20.1,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user input for config_entry that already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.google_weather.config_flow.GoogleWeatherApi.async_get_current_conditions",
    ) as mock_get_current_conditions:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test-name",
                CONF_API_KEY: "test-api-key",
                CONF_LOCATION: {
                    CONF_LATITUDE: mock_config_entry.data[CONF_LATITUDE],
                    CONF_LONGITUDE: mock_config_entry.data[CONF_LONGITUDE],
                },
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_get_current_conditions.call_count == 0


async def test_form_not_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user input for config_entry different than the existing one."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.google_weather.config_flow.GoogleWeatherApi.async_get_current_conditions",
    ) as mock_get_current_conditions:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test-name",
                CONF_API_KEY: "test-api-key",
                CONF_LOCATION: {
                    CONF_LATITUDE: 10.2,
                    CONF_LONGITUDE: 20.2,
                },
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
        CONF_REFERRER: None,
        CONF_LATITUDE: 10.2,
        CONF_LONGITUDE: 20.2,
    }
    assert len(mock_setup_entry.mock_calls) == 2
    assert mock_get_current_conditions.call_count == 1
