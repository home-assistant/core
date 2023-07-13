"""Test the Blue Current config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.blue_current import DOMAIN
from homeassistant.components.blue_current.config_flow import (
    AlreadyConnected,
    InvalidApiToken,
    RequestLimitReached,
    WebsocketError,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test if the form is created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["errors"] == {}


async def test_user(hass: HomeAssistant) -> None:
    """Test if the api token is set."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["errors"] == {}

    with patch("bluecurrent_api.Client.validate_api_token", return_value=True), patch(
        "bluecurrent_api.Client.get_email", return_value="test@email.com"
    ), patch(
        "homeassistant.components.blue_current.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_token": "123",
            },
        )
        await hass.async_block_till_done()

    assert result2["title"] == "123"
    assert result2["data"] == {"api_token": "123"}


async def test_form_invalid_token(hass: HomeAssistant) -> None:
    """Test if an invalid api token is handled."""
    with patch(
        "bluecurrent_api.Client.validate_api_token",
        side_effect=InvalidApiToken,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"api_token": "123"},
        )
        assert result["errors"] == {"base": "invalid_token"}


async def test_form_limit_reached(hass: HomeAssistant) -> None:
    """Test if an limit reached error is handled."""
    with patch(
        "bluecurrent_api.Client.validate_api_token",
        side_effect=RequestLimitReached,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"api_token": "123"},
        )
        assert result["errors"] == {"base": "limit_reached"}


async def test_form_already_connected(hass: HomeAssistant) -> None:
    """Test if an already connected error is handled."""
    with patch(
        "bluecurrent_api.Client.validate_api_token",
        side_effect=AlreadyConnected,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"api_token": "123"},
        )
        assert result["errors"] == {"base": "already_connected"}


async def test_form_exception(hass: HomeAssistant) -> None:
    """Test if an exception is handled."""
    with patch(
        "bluecurrent_api.Client.validate_api_token",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"api_token": "123"},
        )
        assert result["errors"] == {"base": "unknown"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test if a connection error is handled."""

    with patch(
        "bluecurrent_api.Client.validate_api_token",
        side_effect=WebsocketError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"api_token": "123"},
        )
        assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_reauth(hass: HomeAssistant) -> None:
    """Test reauth step."""
    with patch(
        "bluecurrent_api.Client.validate_api_token",
        return_value=True,
    ), patch("bluecurrent_api.Client.get_email", return_value="test@email.com"):
        entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="uuid",
            unique_id="test@email.com",
            data={"api_token": "123"},
        )
        entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                CONF_SOURCE: SOURCE_REAUTH,
                "entry_id": entry.entry_id,
                "unique_id": entry.unique_id,
            },
            data={"api_token": "abc"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"api_token": "1234567890"},
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert entry.data.copy() == {"api_token": "1234567890"}
