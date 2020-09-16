"""Tests for the Econet component."""
from pyeconet.errors import InvalidCredentialsError

from homeassistant.components.econet import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_ABORT, RESULT_TYPE_FORM

from tests.async_mock import AsyncMock, patch


@patch("homeassistant.components.econet.async_setup", return_value=True)
@patch("homeassistant.components.econet.async_setup_entry", return_value=True)
@patch("homeassistant.components.econet.common.EcoNetApiInterface")
async def test_auth_fail(
    econetapi_mock, async_setup_entry_mock, async_setup_mock, hass: HomeAssistant
) -> None:
    """Test authorization failures."""
    econetapi_mock.login = AsyncMock()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    econetapi_mock.login.side_effect = InvalidCredentialsError()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_EMAIL: "admin@localhost.com",
            CONF_PASSWORD: "password0",
        },
    )
    assert result
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {
        "base": "invalid_auth",
    }

    econetapi_mock.login.side_effect = Exception("Connection error.")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_EMAIL: "admin@localhost.com",
            CONF_PASSWORD: "password0",
        },
    )
    assert result
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {
        "base": "cannot_connect",
    }


@patch("homeassistant.components.econet.async_setup", return_value=True)
@patch("homeassistant.components.econet.async_setup_entry", return_value=True)
@patch("homeassistant.components.econet.common.EcoNetApiInterface")
async def test_import_fail(
    econetapi_mock, async_setup_entry_mock, async_setup_mock, hass: HomeAssistant
) -> None:
    """Test authorization failures."""
    econetapi_mock.login = AsyncMock(side_effect=InvalidCredentialsError())
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_EMAIL: "admin@localhost.com",
            CONF_PASSWORD: "password0",
        },
    )
    assert result
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "invalid_auth"
