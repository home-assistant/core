"""Test the Google Weather config flow."""

from unittest.mock import AsyncMock

from google_weather_api import GoogleWeatherApiAuthError, GoogleWeatherApiError
import pytest

from homeassistant import config_entries
from homeassistant.components.google_weather.const import (
    CONF_REFERRER,
    DOMAIN,
    SECTION_API_KEY_OPTIONS,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, get_schema_suggested_value


def _assert_create_entry_result(
    result: dict, expected_referrer: str | None = None
) -> None:
    """Assert that the result is a create entry result."""
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Google Weather"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
        CONF_REFERRER: expected_referrer,
    }
    assert len(result["subentries"]) == 1
    subentry = result["subentries"][0]
    assert subentry["subentry_type"] == "location"
    assert subentry["title"] == "test-name"
    assert subentry["data"] == {
        CONF_LATITUDE: 10.1,
        CONF_LONGITUDE: 20.1,
    }


async def test_create_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test creating a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

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

    mock_google_weather_api.async_get_current_conditions.assert_called_once_with(
        latitude=10.1, longitude=20.1
    )

    _assert_create_entry_result(result)
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_with_referrer(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test we get the form and optional referrer is specified."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "test-name",
            CONF_API_KEY: "test-api-key",
            SECTION_API_KEY_OPTIONS: {
                CONF_REFERRER: "test-referrer",
            },
            CONF_LOCATION: {
                CONF_LATITUDE: 10.1,
                CONF_LONGITUDE: 20.1,
            },
        },
    )

    mock_google_weather_api.async_get_current_conditions.assert_called_once_with(
        latitude=10.1, longitude=20.1
    )

    _assert_create_entry_result(result, expected_referrer="test-referrer")
    assert len(mock_setup_entry.mock_calls) == 1


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
    mock_google_weather_api: AsyncMock,
    api_exception,
    expected_error,
) -> None:
    """Test we handle exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_google_weather_api.async_get_current_conditions.side_effect = api_exception
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
    # On error, the form should have the previous user input
    data_schema = result["data_schema"].schema
    assert get_schema_suggested_value(data_schema, CONF_NAME) == "test-name"
    assert get_schema_suggested_value(data_schema, CONF_API_KEY) == "test-api-key"
    assert get_schema_suggested_value(data_schema, CONF_LOCATION) == {
        CONF_LATITUDE: 10.1,
        CONF_LONGITUDE: 20.1,
    }

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    mock_google_weather_api.async_get_current_conditions.side_effect = None
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

    _assert_create_entry_result(result)
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_api_key_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test user input for config_entry with API key that already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_google_weather_api.async_get_current_conditions.call_count == 0


async def test_form_location_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test user input for a location that already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "test-name",
            CONF_API_KEY: "another-api-key",
            CONF_LOCATION: {
                CONF_LATITUDE: 10.1001,
                CONF_LONGITUDE: 20.0999,
            },
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_google_weather_api.async_get_current_conditions.call_count == 0


async def test_form_not_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test user input for config_entry different than the existing one."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "new-test-name",
            CONF_API_KEY: "new-test-api-key",
            CONF_LOCATION: {
                CONF_LATITUDE: 10.1002,
                CONF_LONGITUDE: 20.0998,
            },
        },
    )

    mock_google_weather_api.async_get_current_conditions.assert_called_once_with(
        latitude=10.1002, longitude=20.0998
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Google Weather"
    assert result["data"] == {
        CONF_API_KEY: "new-test-api-key",
        CONF_REFERRER: None,
    }
    assert len(result["subentries"]) == 1
    subentry = result["subentries"][0]
    assert subentry["subentry_type"] == "location"
    assert subentry["title"] == "new-test-name"
    assert subentry["data"] == {
        CONF_LATITUDE: 10.1002,
        CONF_LONGITUDE: 20.0998,
    }
    assert len(mock_setup_entry.mock_calls) == 2


async def test_subentry_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test creating a location subentry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # After initial setup for 1 subentry, each API is called once
    assert mock_google_weather_api.async_get_current_conditions.call_count == 1
    assert mock_google_weather_api.async_get_daily_forecast.call_count == 1
    assert mock_google_weather_api.async_get_hourly_forecast.call_count == 1

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "location"

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Work",
            CONF_LOCATION: {
                CONF_LATITUDE: 30.1,
                CONF_LONGITUDE: 40.1,
            },
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Work"
    assert result2["data"] == {
        CONF_LATITUDE: 30.1,
        CONF_LONGITUDE: 40.1,
    }

    # Initial setup: 1 of each API call
    # Subentry flow validation: 1 current conditions call
    # Reload with 2 subentries: 2 of each API call
    assert mock_google_weather_api.async_get_current_conditions.call_count == 1 + 1 + 2
    assert mock_google_weather_api.async_get_daily_forecast.call_count == 1 + 2
    assert mock_google_weather_api.async_get_hourly_forecast.call_count == 1 + 2

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert len(entry.subentries) == 2


async def test_subentry_flow_location_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test user input for a location that already exists."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "location"

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Work",
            CONF_LOCATION: {
                CONF_LATITUDE: 10.1,
                CONF_LONGITUDE: 20.1,
            },
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert len(entry.subentries) == 1


async def test_reauth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "new-api-key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"
    assert mock_config_entry.data.get(CONF_REFERRER) is None
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("api_exception", "expected_error", "expected_placeholders"),
    [
        (
            GoogleWeatherApiAuthError("Invalid API key"),
            "cannot_connect",
            {
                "api_key_url": "https://developers.google.com/maps/documentation/weather/get-api-key",
                "restricting_api_keys_url": "https://developers.google.com/maps/api-security-best-practices#restricting-api-keys",
                "error_message": "Invalid API key",
                "name": "Google Weather",
            },
        ),
        (
            ValueError(),
            "unknown",
            {
                "api_key_url": "https://developers.google.com/maps/documentation/weather/get-api-key",
                "restricting_api_keys_url": "https://developers.google.com/maps/api-security-best-practices#restricting-api-keys",
                "name": "Google Weather",
            },
        ),
    ],
)
async def test_reauth_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
    api_exception: Exception,
    expected_error: str,
    expected_placeholders: dict[str, str],
) -> None:
    """Test reauth flow with exceptions."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM

    mock_google_weather_api.async_get_current_conditions.side_effect = api_exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "invalid-api-key",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    assert result["description_placeholders"] == expected_placeholders

    mock_google_weather_api.async_get_current_conditions.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "valid-api-key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_same_api_key_different_referrer(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test reauth flow with same API key but different referrer."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test-api-key",
            SECTION_API_KEY_OPTIONS: {
                CONF_REFERRER: "new-referrer",
            },
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "test-api-key"
    assert mock_config_entry.data.get(CONF_REFERRER) == "new-referrer"


async def test_reconfigure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "new-api-key",
            SECTION_API_KEY_OPTIONS: {
                CONF_REFERRER: "new-referrer",
            },
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"
    assert mock_config_entry.data.get(CONF_REFERRER) == "new-referrer"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("api_exception", "expected_error", "expected_placeholders"),
    [
        (
            GoogleWeatherApiAuthError("Invalid API key"),
            "cannot_connect",
            {
                "api_key_url": "https://developers.google.com/maps/documentation/weather/get-api-key",
                "restricting_api_keys_url": "https://developers.google.com/maps/api-security-best-practices#restricting-api-keys",
                "error_message": "Invalid API key",
            },
        ),
        (
            ValueError(),
            "unknown",
            {
                "api_key_url": "https://developers.google.com/maps/documentation/weather/get-api-key",
                "restricting_api_keys_url": "https://developers.google.com/maps/api-security-best-practices#restricting-api-keys",
            },
        ),
    ],
)
async def test_reconfigure_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
    api_exception: Exception,
    expected_error: str,
    expected_placeholders: dict[str, str],
) -> None:
    """Test reconfigure flow with exceptions."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    mock_google_weather_api.async_get_current_conditions.side_effect = api_exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "invalid-api-key",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    assert result["description_placeholders"] == expected_placeholders

    mock_google_weather_api.async_get_current_conditions.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "valid-api-key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reconfigure_no_subentries(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test reconfigure flow when there are no subentries."""
    mock_config_entry = MockConfigEntry(
        title="Google Weather",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "test-api-key",
        },
    )
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "new-api-key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_subentry_reconfigure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test reconfiguring a location subentry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    subentry = next(iter(mock_config_entry.subentries.values()))
    result = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "location"

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "New Work",
            CONF_LOCATION: {
                CONF_LATITUDE: 30.1,
                CONF_LONGITUDE: 40.1,
            },
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"

    # Reload the entry to see changes
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    updated_subentry = entry.subentries[subentry.subentry_id]

    assert updated_subentry.title == "New Work"
    assert updated_subentry.data == {
        CONF_LATITUDE: 30.1,
        CONF_LONGITUDE: 40.1,
    }


async def test_subentry_flow_entry_not_loaded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test creating a location subentry when the parent entry is not loaded."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "location"),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"
