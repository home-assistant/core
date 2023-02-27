"""Tests for the Abode config flow."""
from http import HTTPStatus
from unittest.mock import patch

from jaraco.abode.exceptions import (
    AuthenticationException as AbodeAuthenticationException,
)
from jaraco.abode.helpers.errors import MFA_CODE_REQUIRED
import pytest
from requests.exceptions import ConnectTimeout

from homeassistant.components.abode.const import CONF_POLLING, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_one_config_allowed(hass: HomeAssistant) -> None:
    """Test that only one Abode configuration is allowed."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    ).add_to_hass(hass)

    step_user_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert step_user_result["type"] == FlowResultType.ABORT
    assert step_user_result["reason"] == "single_instance_allowed"


async def test_invalid_credentials(hass: HomeAssistant) -> None:
    """Test that invalid credentials throws an error."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.abode.config_flow.Abode",
        side_effect=AbodeAuthenticationException(
            (HTTPStatus.BAD_REQUEST, "auth error")
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=conf
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "invalid_auth"}


async def test_connection_auth_error(hass: HomeAssistant) -> None:
    """Test other than invalid credentials throws an error."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.abode.config_flow.Abode",
        side_effect=AbodeAuthenticationException(
            (HTTPStatus.INTERNAL_SERVER_ERROR, "connection error")
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=conf
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test login throws an error if connection times out."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.abode.config_flow.Abode",
        side_effect=ConnectTimeout,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=conf
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_step_user(hass: HomeAssistant) -> None:
    """Test that the user step works."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("homeassistant.components.abode.config_flow.Abode"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=conf
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "user@email.com"
        assert result["data"] == {
            CONF_USERNAME: "user@email.com",
            CONF_PASSWORD: "password",
            CONF_POLLING: False,
        }


async def test_step_mfa(hass: HomeAssistant) -> None:
    """Test that the MFA step works."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.abode.config_flow.Abode",
        side_effect=AbodeAuthenticationException(MFA_CODE_REQUIRED),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=conf
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "mfa"

    with patch(
        "homeassistant.components.abode.config_flow.Abode",
        side_effect=AbodeAuthenticationException(
            (HTTPStatus.BAD_REQUEST, "invalid mfa")
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"mfa_code": "123456"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "mfa"
        assert result["errors"] == {"base": "invalid_mfa_code"}

    with patch("homeassistant.components.abode.config_flow.Abode"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"mfa_code": "123456"}
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "user@email.com"
        assert result["data"] == {
            CONF_USERNAME: "user@email.com",
            CONF_PASSWORD: "password",
            CONF_POLLING: False,
        }


async def test_step_reauth(hass: HomeAssistant) -> None:
    """Test the reauth flow."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@email.com",
        data=conf,
    ).add_to_hass(hass)

    with patch("homeassistant.components.abode.config_flow.Abode"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH},
            data=conf,
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        with patch(
            "homeassistant.config_entries.ConfigEntries.async_reload"
        ) as mock_reload:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=conf,
            )

            assert result["type"] == FlowResultType.ABORT
            assert result["reason"] == "reauth_successful"

        assert len(hass.config_entries.async_entries()) == 1
        mock_reload.assert_called_once()
