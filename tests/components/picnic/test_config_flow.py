"""Test the Picnic config flow."""
from unittest.mock import patch

from python_picnic_api.session import PicnicAuthError
import requests

from homeassistant import config_entries, setup
from homeassistant.components.picnic.const import CONF_COUNTRY_CODE, DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    auth_token = "af3wh738j3fa28l9fa23lhiufahu7l"
    auth_data = {
        "user_id": "f29-2a6-o32n",
        "address": {
            "street": "Teststreet",
            "house_number": 123,
            "house_number_ext": "b",
        },
    }
    with patch(
        "homeassistant.components.picnic.config_flow.PicnicAPI",
    ) as mock_picnic, patch(
        "homeassistant.components.picnic.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        mock_picnic().session.auth_token = auth_token
        mock_picnic().get_user.return_value = auth_data

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country_code": "NL",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Teststreet 123b"
    assert result2["data"] == {
        CONF_ACCESS_TOKEN: auth_token,
        CONF_COUNTRY_CODE: "NL",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.picnic.config_flow.PicnicHub.authenticate",
        side_effect=PicnicAuthError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country_code": "NL",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.picnic.config_flow.PicnicHub.authenticate",
        side_effect=requests.exceptions.ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country_code": "NL",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_exception(hass):
    """Test we handle random exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.picnic.config_flow.PicnicHub.authenticate",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country_code": "NL",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
