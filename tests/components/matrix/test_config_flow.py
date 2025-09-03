"""Test the Matrix config flow."""

from unittest.mock import AsyncMock, patch

from nio import LoginError, LoginResponse, WhoamiResponse

from homeassistant import config_entries
from homeassistant.components.matrix.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_USER_INPUT = {
    "homeserver": "https://matrix.example.com",
    "username": "@user:example.com",
    "password": "password",
    "verify_ssl": True,
}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch("homeassistant.components.matrix.config_flow.AsyncClient") as mock_client,
    ):
        client_instance = AsyncMock()
        mock_client.return_value = client_instance

        login_response = LoginResponse.from_dict(
            {
                "access_token": "test_token",
                "device_id": "test_device",
                "user_id": "@user:example.com",
            }
        )
        client_instance.login.return_value = login_response

        whoami_response = WhoamiResponse.from_dict(
            {
                "user_id": "@user:example.com",
            }
        )
        client_instance.whoami.return_value = whoami_response

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "@user:example.com"
    assert result2["data"] == TEST_USER_INPUT


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.matrix.config_flow.AsyncClient",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_login_error(hass: HomeAssistant) -> None:
    """Test we handle login errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch("homeassistant.components.matrix.config_flow.AsyncClient") as mock_client,
    ):
        client_instance = AsyncMock()
        mock_client.return_value = client_instance

        login_error = LoginError.from_dict(
            {
                "errcode": "M_FORBIDDEN",
                "error": "Invalid username or password",
            }
        )
        client_instance.login.return_value = login_error

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test that we abort on duplicate entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data=TEST_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch("homeassistant.components.matrix.config_flow.AsyncClient") as mock_client,
    ):
        client_instance = AsyncMock()
        mock_client.return_value = client_instance

        login_response = LoginResponse.from_dict(
            {
                "access_token": "test_token",
                "device_id": "test_device",
                "user_id": "@user:example.com",
            }
        )
        client_instance.login.return_value = login_response

        whoami_response = WhoamiResponse.from_dict(
            {
                "user_id": "@user:example.com",
            }
        )
        client_instance.whoami.return_value = whoami_response

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
