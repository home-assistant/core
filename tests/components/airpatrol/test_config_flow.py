"""Test the AirPatrol config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.airpatrol.api import AirPatrolAuthenticationError
from homeassistant.components.airpatrol.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.airpatrol.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_USER_INPUT = {
    CONF_EMAIL: "test@example.com",
    CONF_PASSWORD: "test_password",
}

MOCK_AUTH_RESPONSE = {
    "status": "ok",
    "entities": {
        "users": {
            "list": [
                {
                    "appId": "test_unique_id",
                }
            ]
        }
    },
    "misc": {"accessToken": "test_access_token"},
}


@pytest.fixture
def mock_api():
    """Mock AirPatrol API."""
    api = MagicMock()
    api.get_unique_id.return_value = "test_user_id"
    api.get_access_token.return_value = "test_access_token"
    return api


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    return MockConfigEntry(
        domain="airpatrol",
        data={
            "email": "test@example.com",
            "password": "test_password",
            "access_token": "test_access_token",
        },
        unique_id="test_user_id",
    )


async def test_user_flow_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test form submission
    with patch(
        "homeassistant.components.airpatrol.config_flow.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()

        # Mock the static authenticate method
        with patch(
            "homeassistant.components.airpatrol.config_flow.AirPatrolAPI.authenticate"
        ) as mock_auth:
            mock_api = MagicMock()
            mock_api.get_access_token.return_value = "test_access_token"
            mock_api.get_unique_id.return_value = "test_user_id"
            mock_auth.return_value = mock_api

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=TEST_USER_INPUT
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["title"] == "airpatrol"
            assert result["data"] == {
                **TEST_USER_INPUT,
                "access_token": "test_access_token",
            }
            assert result["result"].unique_id == "test_user_id"


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow with invalid authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.airpatrol.config_flow.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()

        # Mock the static authenticate method to raise an exception
        with patch(
            "homeassistant.components.airpatrol.config_flow.AirPatrolAPI.authenticate"
        ) as mock_auth:
            mock_auth.side_effect = AirPatrolAuthenticationError(
                "Authentication failed"
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=TEST_USER_INPUT
            )

            assert result["type"] == FlowResultType.FORM
            assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.airpatrol.config_flow.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()

        # Mock the static authenticate method to raise an exception
        with patch(
            "homeassistant.components.airpatrol.config_flow.AirPatrolAPI.authenticate"
        ) as mock_auth:
            mock_auth.side_effect = Exception("Connection failed")

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=TEST_USER_INPUT
            )

            assert result["type"] == FlowResultType.FORM
            assert result["errors"] == {"base": "unknown"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow when already configured."""
    # Create an existing config entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_USER_INPUT,
        unique_id="test_unique_id",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.airpatrol.config_flow.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()

        # Mock the static authenticate method
        with patch(
            "homeassistant.components.airpatrol.config_flow.AirPatrolAPI.authenticate"
        ) as mock_auth:
            mock_api = MagicMock()
            mock_api.get_unique_id.return_value = "test_unique_id"
            mock_auth.return_value = mock_api

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=TEST_USER_INPUT
            )

            assert result["type"] == FlowResultType.ABORT
            assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow with CannotConnect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with patch(
        "homeassistant.components.airpatrol.config_flow.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()
        with patch(
            "homeassistant.components.airpatrol.config_flow.AirPatrolAPI.authenticate"
        ) as mock_auth:
            mock_auth.side_effect = CannotConnect("fail")
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=TEST_USER_INPUT
            )
            assert result["type"] == "form"
            assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_user_flow_invalid_auth_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow with InvalidAuth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with patch(
        "homeassistant.components.airpatrol.config_flow.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()
        with patch(
            "homeassistant.components.airpatrol.config_flow.AirPatrolAPI.authenticate"
        ) as mock_auth:
            mock_auth.side_effect = InvalidAuth("fail")
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=TEST_USER_INPUT
            )
            assert result["type"] == "form"
            assert result["errors"] == {"base": "invalid_auth"}
