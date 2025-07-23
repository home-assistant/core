"""Config flow test case for the Actron Air Neo Integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from actron_neo_api import ActronNeoAPIError, ActronNeoAuthError
import pytest

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

DOMAIN = "actronair"
ERROR_API_ERROR = "api_error"
ERROR_INVALID_AUTH = "invalid_auth"
ERROR_NO_SYSTEMS_FOUND = "no_systems_found"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.actronair.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_actron_api() -> MagicMock:
    """Mock the ActronNeoAPI class."""
    with patch(
        "custom_components.actron_neo.config_flow.ActronNeoAPI", autospec=True
    ) as mock_api:
        yield mock_api


async def test_user_flow(hass: HomeAssistant, mock_actron_api) -> None:
    """Test the user flow."""
    mock_api_instance = mock_actron_api.return_value
    mock_api_instance.get_ac_systems = AsyncMock(
        return_value={
            "_embedded": {
                "ac-system": [{"serial": "12345", "description": "Living Room"}]
            }
        }
    )
    mock_api_instance.pairing_token = "test_pairing_token"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "test_user", CONF_PASSWORD: "test_pass"}
    )

    assert result["type"] == "create_entry"
    assert result["unique_id"] == "12345"
    assert result["title"] == "example@example.com"
    assert result["data"] == {
        CONF_API_TOKEN: "abcde12345",
    }


async def test_user_flow_invalid_auth(hass: HomeAssistant, mock_actron_api) -> None:
    """Test the user flow with invalid authentication."""
    mock_api_instance = mock_actron_api.return_value
    mock_api_instance.request_pairing_token.side_effect = ActronNeoAuthError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "test_user", CONF_PASSWORD: "test_pass"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": ERROR_INVALID_AUTH}


async def test_user_flow_api_error(hass: HomeAssistant, mock_actron_api) -> None:
    """Test the user flow with an API error."""
    mock_api_instance = mock_actron_api.return_value
    mock_api_instance.request_pairing_token.side_effect = ActronNeoAPIError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "test_user", CONF_PASSWORD: "test_pass"}
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": ERROR_API_ERROR}


async def test_user_flow_no_systems_found(hass: HomeAssistant, mock_actron_api) -> None:
    """Test the user flow when no systems are found."""
    mock_api_instance = mock_actron_api.return_value
    mock_api_instance.get_ac_systems = AsyncMock(
        return_value={"_embedded": {"ac-system": []}}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "test_user", CONF_PASSWORD: "test_pass"}
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": ERROR_NO_SYSTEMS_FOUND}
