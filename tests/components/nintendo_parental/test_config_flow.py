"""Test the Nintendo Switch Parental Controls config flow."""

from unittest.mock import MagicMock

from homeassistant import config_entries
from homeassistant.components.nintendo_parental.const import CONF_SESSION_TOKEN, DOMAIN
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

mock_config_entry = MockConfigEntry(
    domain=DOMAIN,
    data={CONF_SESSION_TOKEN: "valid_token"},
    unique_id="aabbccddee112233",
)


async def test_full_flow(
    hass: HomeAssistant, mock_authenticator_client: MagicMock
) -> None:
    """Test a full and successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "link" in result["description_placeholders"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "aaaabbbbcccc"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "aabbccddee112233"
    assert result["data"][CONF_SESSION_TOKEN] == "valid_token"
    assert result["result"].unique_id == "aabbccddee112233"


async def test_already_configured(
    hass: HomeAssistant, mock_authenticator_client: MagicMock
) -> None:
    """Ensure only one instance of an account can be configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "link" in result["description_placeholders"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "aaaabbbbcccc"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_api_token(
    hass: HomeAssistant, mock_request_handler, mock_authenticator_client: MagicMock
) -> None:
    """Test to ensure an error is shown if the API token is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "link" in result["description_placeholders"]

    mock_request_handler.return_value = {
        "status": 400,
        "text": "ERROR",
        "json": {},
        "headers": {"Content-Type": "application/json"},
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "aaaabbbbcccc"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    # clear the error and test retry
    mock_request_handler.return_value = {
        "status": 200,
        "text": "OK",
        "json": {
            "session_token": "valid_token",
            "expires_in": 3500,
            "id": "aabbccddee112233",
            "name": "Home Assistant Tester",
        },
        "headers": {"Content-Type": "application/json"},
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "aaaabbbbcccc"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "aabbccddee112233"
    assert result["data"][CONF_SESSION_TOKEN] == "valid_token"
    assert result["result"].unique_id == "aabbccddee112233"


async def test_general_error(
    hass: HomeAssistant, mock_request_handler, mock_authenticator_client: MagicMock
) -> None:
    """Test catching of general Exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "link" in result["description_placeholders"]

    # produce some bogus data in the request handler that cannot be processed
    mock_request_handler.return_value = 0x01

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "aaaabbbbcccc"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}

    # clear the error and test retry
    mock_request_handler.return_value = {
        "status": 200,
        "text": "OK",
        "json": {
            "session_token": "valid_token",
            "expires_in": 3500,
            "id": "aabbccddee112233",
            "name": "Home Assistant Tester",
        },
        "headers": {"Content-Type": "application/json"},
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "aaaabbbbcccc"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "aabbccddee112233"
    assert result["data"][CONF_SESSION_TOKEN] == "valid_token"
    assert result["result"].unique_id == "aabbccddee112233"
