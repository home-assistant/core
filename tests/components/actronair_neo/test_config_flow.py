"""Config flow test case for the Actron Air Neo Integration."""

from unittest.mock import AsyncMock, patch

from actron_neo_api import ActronNeoAPIError, ActronNeoAuthError
import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .const import DOMAIN, ERROR_API_ERROR, ERROR_INVALID_AUTH, ERROR_NO_SYSTEMS_FOUND


# Fixtures for the mock ActronNeoAPI
@pytest.fixture
def mock_actron_api():
    """Mock the ActronNeoAPI class."""
    with patch(
        "custom_components.actron_neo.config_flow.ActronNeoAPI", autospec=True
    ) as mock_api:
        yield mock_api


async def test_user_flow_single_system(hass: HomeAssistant, mock_actron_api) -> None:
    """Test the user flow with a single AC system."""
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
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "test_user", "password": "test_pass"}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Living Room"
    assert result["data"] == {
        "pairing_token": "test_pairing_token",
        "serial_number": "12345",
    }


async def test_user_flow_multiple_systems(hass: HomeAssistant, mock_actron_api) -> None:
    """Test the user flow with multiple AC systems."""
    mock_api_instance = mock_actron_api.return_value
    mock_api_instance.get_ac_systems = AsyncMock(
        return_value={
            "_embedded": {
                "ac-system": [
                    {"serial": "12345", "description": "Living Room"},
                    {"serial": "67890", "description": "Bedroom"},
                ]
            }
        }
    )
    mock_api_instance.pairing_token = "test_pairing_token"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "test_user", "password": "test_pass"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "select_system"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"selected_system": "67890"}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Bedroom"
    assert result["data"] == {
        "pairing_token": "test_pairing_token",
        "serial_number": "67890",
    }


async def test_user_flow_invalid_auth(hass: HomeAssistant, mock_actron_api) -> None:
    """Test the user flow with invalid authentication."""
    mock_api_instance = mock_actron_api.return_value
    mock_api_instance.request_pairing_token.side_effect = ActronNeoAuthError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "test_user", "password": "wrong_pass"}
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": ERROR_INVALID_AUTH}


async def test_user_flow_api_error(hass: HomeAssistant, mock_actron_api) -> None:
    """Test the user flow with an API error."""
    mock_api_instance = mock_actron_api.return_value
    mock_api_instance.request_pairing_token.side_effect = ActronNeoAPIError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "test_user", "password": "test_pass"}
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
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "test_user", "password": "test_pass"}
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": ERROR_NO_SYSTEMS_FOUND}
