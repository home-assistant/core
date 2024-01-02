"""Test the edilkamin config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.edilkamin.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

username = "user@email.com"
password = "password"
token = "the-token"


class NotAuthorizedException(Exception):
    """Cannot be imported as it's created dynamically within pycognito."""


def patch_sign_in(return_value=None, side_effect=None):
    """Patch the edilkamin.sign_in() function."""
    return patch(
        "homeassistant.components.edilkamin.config_flow.edilkamin.sign_in",
        return_value=return_value,
        side_effect=side_effect,
    )


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    with patch(
        "homeassistant.components.edilkamin.config_flow.EdilkaminHub.authenticate",
        return_value=token,
    ), patch(
        "homeassistant.components.edilkamin.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": username,
                "password": password,
            },
        )
        await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == username
    assert result2["data"] == {
        "username": username,
        "password": password,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch_sign_in(side_effect=NotAuthorizedException):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": username,
                "password": password,
            },
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_token_none(hass: HomeAssistant) -> None:
    """Test we handle token=None."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch_sign_in():
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": username,
                "password": password,
            },
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch_sign_in(side_effect=Exception):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": username,
                "password": password,
            },
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
