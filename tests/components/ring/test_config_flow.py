"""Test the Ring config flow."""
from unittest.mock import Mock, patch

from ring_doorbell import AuthenticationError, Requires2FAError

from homeassistant import config_entries
from homeassistant.components.ring import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import MOCK_USER_DATA

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.ring.config_flow.Auth",
        return_value=Mock(
            fetch_token=Mock(return_value={"access_token": "mock-token"})
        ),
    ), patch(
        "homeassistant.components.ring.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "hello@home-assistant.io", "password": "test-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "hello@home-assistant.io"
    assert result2["data"] == {
        "username": "hello@home-assistant.io",
        CONF_ACCESS_TOKEN: {"access_token": "mock-token"},
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ring.config_flow.Auth.fetch_token",
        side_effect=AuthenticationError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "hello@home-assistant.io", "password": "test-password"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth(hass: HomeAssistant) -> None:
    """Test starting a reauthentication flow."""
    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config.entry_id},
        data=mock_config.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.ring.config_flow.Auth.fetch_token",
        side_effect=Requires2FAError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "other_fake_user",
                CONF_PASSWORD: "other_fake_password",
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "2fa"
    with patch(
        "homeassistant.components.ring.config_flow.Auth.fetch_token",
        return_value="foobar",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"2fa": "123456"},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config.data[CONF_USERNAME] == "other_fake_user"
    assert mock_config.data[CONF_ACCESS_TOKEN] == "foobar"
