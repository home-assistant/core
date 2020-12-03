"""Tests for the Abode config flow."""
from abodepy.exceptions import AbodeAuthenticationException
from abodepy.helpers.errors import MFA_CODE_REQUIRED

from homeassistant import data_entry_flow
from homeassistant.components.abode import config_flow
from homeassistant.components.abode.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    HTTP_BAD_REQUEST,
    HTTP_INTERNAL_SERVER_ERROR,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry

CONF_POLLING = "polling"


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.AbodeFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_one_config_allowed(hass):
    """Test that only one Abode configuration is allowed."""
    flow = config_flow.AbodeFlowHandler()
    flow.hass = hass

    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    ).add_to_hass(hass)

    step_user_result = await flow.async_step_user()

    assert step_user_result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert step_user_result["reason"] == "single_instance_allowed"

    conf = {
        CONF_USERNAME: "user@email.com",
        CONF_PASSWORD: "password",
        CONF_POLLING: False,
    }

    import_config_result = await flow.async_step_import(conf)

    assert import_config_result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert import_config_result["reason"] == "single_instance_allowed"


async def test_invalid_credentials(hass):
    """Test that invalid credentials throws an error."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    flow = config_flow.AbodeFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.abode.config_flow.Abode",
        side_effect=AbodeAuthenticationException((HTTP_BAD_REQUEST, "auth error")),
    ):
        result = await flow.async_step_user(user_input=conf)
        assert result["errors"] == {"base": "invalid_auth"}


async def test_connection_error(hass):
    """Test other than invalid credentials throws an error."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    flow = config_flow.AbodeFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.abode.config_flow.Abode",
        side_effect=AbodeAuthenticationException(
            (HTTP_INTERNAL_SERVER_ERROR, "connection error")
        ),
    ):
        result = await flow.async_step_user(user_input=conf)
        assert result["errors"] == {"base": "cannot_connect"}


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {
        CONF_USERNAME: "user@email.com",
        CONF_PASSWORD: "password",
        CONF_POLLING: False,
    }

    with patch("homeassistant.components.abode.config_flow.Abode"), patch(
        "abodepy.UTILS"
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user@email.com"
        assert result["data"] == {
            CONF_USERNAME: "user@email.com",
            CONF_PASSWORD: "password",
            CONF_POLLING: False,
        }


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    with patch("homeassistant.components.abode.config_flow.Abode"), patch(
        "abodepy.UTILS"
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user@email.com"
        assert result["data"] == {
            CONF_USERNAME: "user@email.com",
            CONF_PASSWORD: "password",
            CONF_POLLING: False,
        }


async def test_step_mfa(hass):
    """Test that the MFA step works."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    with patch(
        "homeassistant.components.abode.config_flow.Abode",
        side_effect=AbodeAuthenticationException(MFA_CODE_REQUIRED),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "mfa"

    with patch(
        "homeassistant.components.abode.config_flow.Abode",
        side_effect=AbodeAuthenticationException((HTTP_BAD_REQUEST, "invalid mfa")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"mfa_code": "123456"}
        )

        assert result["errors"] == {"base": "invalid_mfa_code"}

    with patch("homeassistant.components.abode.config_flow.Abode"), patch(
        "abodepy.UTILS"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"mfa_code": "123456"}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user@email.com"
        assert result["data"] == {
            CONF_USERNAME: "user@email.com",
            CONF_PASSWORD: "password",
            CONF_POLLING: False,
        }


async def test_step_reauth(hass):
    """Test the reauth flow."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@email.com",
        data=conf,
    ).add_to_hass(hass)

    with patch("homeassistant.components.abode.config_flow.Abode"), patch(
        "abodepy.UTILS"
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth"},
            data=conf,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth_confirm"

        with patch("homeassistant.config_entries.ConfigEntries.async_reload"):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=conf,
            )

            assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
            assert result["reason"] == "reauth_successful"

        assert len(hass.config_entries.async_entries()) == 1
