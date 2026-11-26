"""Define tests for the AccuWeather config flow."""

from unittest.mock import AsyncMock

from accuweather.exceptions import ApiError, InvalidApiKeyError, RequestsExceededError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.accuweather.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import init_integration

VALID_CONFIG = {
    CONF_API_KEY: "32-character-string-1234567890qw",
    CONF_LOCATION: {
        CONF_LATITUDE: 55.55,
        CONF_LONGITUDE: 122.12,
    },
}

UPDATE_API_KEY_FLOWS = [
    ("start_reauth_flow", "reauth_confirm", "reauth_successful"),
    ("start_reconfigure_flow", "reconfigure", "reconfigure_successful"),
]


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.parametrize(
    ("exc", "errors"),
    [
        (ApiError("API Error"), {"base": "cannot_connect"}),
        (TimeoutError, {"base": "cannot_connect"}),
        (InvalidApiKeyError("Invalid API Key"), {CONF_API_KEY: "invalid_api_key"}),
        (
            RequestsExceededError("Requests Exceeded"),
            {CONF_API_KEY: "requests_exceeded"},
        ),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    exc: Exception,
    errors: dict[str, str],
    mock_accuweather_client: AsyncMock,
) -> None:
    """Test the user step recovers from errors and creates an entry."""
    mock_accuweather_client.async_get_location.side_effect = exc

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CONFIG
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors

    mock_accuweather_client.async_get_location.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test location"
    assert result["data"] == {
        CONF_API_KEY: "32-character-string-1234567890qw",
        CONF_LATITUDE: 55.55,
        CONF_LONGITUDE: 122.12,
    }
    assert result["result"].unique_id == "0123456"


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
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_create_entry(
    hass: HomeAssistant, mock_accuweather_client: AsyncMock
) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test location"
    assert result["data"][CONF_LATITUDE] == 55.55
    assert result["data"][CONF_LONGITUDE] == 122.12
    assert result["data"][CONF_API_KEY] == "32-character-string-1234567890qw"
    assert result["result"].unique_id == "0123456"


@pytest.mark.parametrize(
    ("start_flow", "step_id", "abort_reason"), UPDATE_API_KEY_FLOWS
)
@pytest.mark.usefixtures("mock_accuweather_client")
async def test_update_api_key_successful(
    hass: HomeAssistant, start_flow: str, step_id: str, abort_reason: str
) -> None:
    """Test updating the API key with the reauth and reconfigure flows."""
    mock_config_entry = await init_integration(hass)

    result = await getattr(mock_config_entry, start_flow)(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new_api_key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == abort_reason
    assert mock_config_entry.data == {
        CONF_API_KEY: "new_api_key",
        CONF_LATITUDE: 55.55,
        CONF_LONGITUDE: 122.12,
    }
    assert mock_config_entry.unique_id == "0123456"


@pytest.mark.parametrize(
    ("start_flow", "step_id", "abort_reason"), UPDATE_API_KEY_FLOWS
)
@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (ApiError("API Error"), "cannot_connect"),
        (InvalidApiKeyError("Invalid API Key"), "invalid_api_key"),
        (TimeoutError, "cannot_connect"),
        (RequestsExceededError("Requests Exceeded"), "requests_exceeded"),
    ],
)
async def test_update_api_key_errors(
    hass: HomeAssistant,
    mock_accuweather_client: AsyncMock,
    start_flow: str,
    step_id: str,
    abort_reason: str,
    exc: Exception,
    base_error: str,
) -> None:
    """Test the reauth and reconfigure flows recover from errors."""
    mock_config_entry = await init_integration(hass)

    result = await getattr(mock_config_entry, start_flow)(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id

    mock_accuweather_client.async_get_location.side_effect = exc
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new_api_key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id
    assert result["errors"] == {"base": base_error}
    assert mock_config_entry.data[CONF_API_KEY] == "32-character-string-1234567890qw"

    mock_accuweather_client.async_get_location.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new_api_key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == abort_reason
    assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"
