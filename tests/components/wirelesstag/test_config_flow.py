"""Test the August config flow."""
from unittest.mock import patch

from wirelesstagpy.exceptions import (
    WirelessTagsConnectionError,
    WirelessTagsWrongCredentials,
)

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.wirelesstag import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_form(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.wirelesstag.WirelessTagPlatform.load_tags",
        return_value={},
    ), patch(
        "homeassistant.components.wirelesstag.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "email@email.com",
                CONF_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "WirelessTags"
    assert result2["data"] == {
        CONF_USERNAME: "email@email.com",
        CONF_PASSWORD: "password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wirelesstag.WirelessTagPlatform.load_tags",
        side_effect=WirelessTagsWrongCredentials,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "email@email.com",
                CONF_PASSWORD: "password",
            },
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_unexpected_exception(hass):
    """Test we handle an unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wirelesstag.WirelessTagPlatform.load_tags",
        side_effect=ValueError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "email@email.com",
                CONF_PASSWORD: "password",
            },
        )

    assert result2["errors"] == {"base": "unknown"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wirelesstag.WirelessTagPlatform.load_tags",
        side_effect=WirelessTagsConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "email@email.com",
                CONF_PASSWORD: "wrong-password",
            },
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_import_flow(hass) -> None:
    """Test successful import flow."""
    test_data = {CONF_USERNAME: "email@email.com", CONF_PASSWORD: "wrong-password"}
    with patch(
        "homeassistant.components.wirelesstag.WirelessTagPlatform.load_tags",
        return_value={},
    ), patch(
        "homeassistant.components.wirelesstag.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=test_data,
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "WirelessTags"
    assert result["data"] == test_data
    assert len(mock_setup_entry.mock_calls) == 1
