"""Test the Control4 config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.control4.const import DOMAIN

from tests.async_mock import patch, AsyncMock
import datetime
from pyControl4.error_handling import Unauthorized


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "pyControl4.account.C4Account.getAccountControllers",
        return_value={
            "controllerCommonName": "control4_model_00AA00AA00AA",
            "href": "https://apis.control4.com/account/v3/rest/accounts/000000",
            "name": "Name",
        },
    ), patch(
        "pyControl4.account.C4Account.getDirectorBearerToken",
        return_value={
            "token": "token",
            "token_expiration": datetime.datetime(2020, 7, 15, 13, 50, 15, 26940),
        },
    ), patch(
        "pyControl4.director.C4Director.getAllItemInfo", return_value={},
    ), patch(
        "homeassistant.components.control4.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.control4.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "control4_model_00AA00AA00AA"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "username": "test-username",
        "password": "test-password",
        "controller_unique_id": "control4_model_00AA00AA00AA",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyControl4.account.C4Account.getAccountControllers", side_effect=Unauthorized,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
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
        "homeassistant.components.control4.config_flow.Control4Validator.authenticate",
        return_value=True,
    ), patch(
        "pyControl4.director.C4Director.getAllItemInfo", side_effect=Unauthorized,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
