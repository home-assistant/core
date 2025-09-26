"""Define tests for the AccuWeather config flow."""

from unittest.mock import AsyncMock

from accuweather import ApiError, InvalidApiKeyError, RequestsExceededError
import pytest

from homeassistant.components.accuweather.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import init_integration

from tests.common import MockConfigEntry

VALID_CONFIG = {
    CONF_NAME: "abcd",
    CONF_API_KEY: "32-character-string-1234567890qw",
    CONF_LATITUDE: 55.55,
    CONF_LONGITUDE: 122.12,
}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_invalid_api_key(
    hass: HomeAssistant, mock_accuweather_client: AsyncMock
) -> None:
    """Test that errors are shown when API key is invalid."""
    mock_accuweather_client.async_get_location.side_effect = InvalidApiKeyError(
        "Invalid API key"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=VALID_CONFIG,
    )

    assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}


async def test_api_error(
    hass: HomeAssistant, mock_accuweather_client: AsyncMock
) -> None:
    """Test API error."""
    mock_accuweather_client.async_get_location.side_effect = ApiError(
        "Invalid response from AccuWeather API"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=VALID_CONFIG,
    )

    assert result["errors"] == {"base": "cannot_connect"}


async def test_requests_exceeded_error(
    hass: HomeAssistant, mock_accuweather_client: AsyncMock
) -> None:
    """Test requests exceeded error."""
    mock_accuweather_client.async_get_location.side_effect = RequestsExceededError(
        "The allowed number of requests has been exceeded"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=VALID_CONFIG,
    )

    assert result["errors"] == {CONF_API_KEY: "requests_exceeded"}


async def test_integration_already_exists(
    hass: HomeAssistant, mock_accuweather_client: AsyncMock
) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456",
        data=VALID_CONFIG,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=VALID_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_create_entry(
    hass: HomeAssistant, mock_accuweather_client: AsyncMock
) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=VALID_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "abcd"
    assert result["data"][CONF_NAME] == "abcd"
    assert result["data"][CONF_LATITUDE] == 55.55
    assert result["data"][CONF_LONGITUDE] == 122.12
    assert result["data"][CONF_API_KEY] == "32-character-string-1234567890qw"


async def test_reauth_successful(
    hass: HomeAssistant, mock_accuweather_client: AsyncMock
) -> None:
    """Test starting a reauthentication flow."""
    mock_config_entry = await init_integration(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (ApiError("API Error"), "cannot_connect"),
        (InvalidApiKeyError("Invalid API Key"), "invalid_api_key"),
        (TimeoutError, "cannot_connect"),
        (RequestsExceededError("Requests Exceeded"), "requests_exceeded"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    exc: Exception,
    base_error: str,
    mock_accuweather_client: AsyncMock,
) -> None:
    """Test reauthentication flow with errors."""
    mock_config_entry = await init_integration(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_accuweather_client.async_get_location.side_effect = exc
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )

    assert result["errors"] == {"base": base_error}

    mock_accuweather_client.async_get_location.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"
