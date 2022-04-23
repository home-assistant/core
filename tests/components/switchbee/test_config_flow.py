"""Test the SwitchBee Smart Home config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.switchbee.config_flow import SwitchBeeError
from homeassistant.components.switchbee.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_ABORT, RESULT_TYPE_FORM

from .test_data import (
    MOCK_FAILED_TO_LOGIN_MSG,
    MOCK_GET_CONFIGURATION,
    MOCK_INVALID_TOKEN_MGS,
)

from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("switchbee.SwitchBeeAPI.login", return_value=None), patch(
        "homeassistant.components.switchbee.async_setup_entry",
        return_value=True,
    ), patch(
        "switchbee.SwitchBeeAPI.get_configuration", return_value=MOCK_GET_CONFIGURATION
    ):

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "switchbee.SwitchBeeAPI.login",
        side_effect=SwitchBeeError(MOCK_FAILED_TO_LOGIN_MSG),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "switchbee.SwitchBeeAPI.login",
        side_effect=SwitchBeeError(MOCK_INVALID_TOKEN_MGS),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass):
    """Test we handle an unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "switchbee.SwitchBeeAPI.login",
        side_effect=Exception,
    ):
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert form_result["type"] == RESULT_TYPE_FORM
    assert form_result["errors"] == {"base": "unknown"}


async def test_form_entry_exists(hass):
    """Test we handle an already existing entry."""
    MockConfigEntry(
        unique_id="XX-XX-XX-XX-XX-XX",
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
        },
        title="test-username",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("switchbee.SwitchBeeAPI.login", return_value=None), patch(
        "homeassistant.components.switchbee.async_setup_entry",
        return_value=True,
    ), patch(
        "switchbee.SwitchBeeAPI.get_configuration", return_value=MOCK_GET_CONFIGURATION
    ):
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert form_result["type"] == RESULT_TYPE_ABORT
    assert form_result["reason"] == "already_configured"
