"""Tests for the Econet component."""

from unittest.mock import patch

from pyeconet.api import EcoNetApiInterface
from pyeconet.errors import InvalidCredentialsError, PyeconetError
import pytest

from homeassistant.components.econet.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_bad_credentials(hass: HomeAssistant) -> None:
    """Test when provided credentials are rejected."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "pyeconet.EcoNetApiInterface.login",
            side_effect=InvalidCredentialsError(),
        ) as mock_login,
        patch("homeassistant.components.econet.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_EMAIL: "admin@localhost.com",
                CONF_PASSWORD: "password0",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {
            "base": "invalid_auth",
        }

        mock_login.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_EMAIL: "admin@localhost.com",
                CONF_PASSWORD: "password0",
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_generic_error_from_library(hass: HomeAssistant) -> None:
    """Test when connection fails."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "pyeconet.EcoNetApiInterface.login",
            side_effect=PyeconetError(),
        ) as mock_login,
        patch("homeassistant.components.econet.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_EMAIL: "admin@localhost.com",
                CONF_PASSWORD: "password0",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {
            "base": "cannot_connect",
        }

        mock_login.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_EMAIL: "admin@localhost.com",
                CONF_PASSWORD: "password0",
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_auth_worked(hass: HomeAssistant) -> None:
    """Test when provided credentials are accepted."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "pyeconet.EcoNetApiInterface.login",
            return_value=EcoNetApiInterface,
        ),
        patch("homeassistant.components.econet.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_EMAIL: "admin@localhost.com",
                CONF_PASSWORD: "password0",
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            CONF_EMAIL: "admin@localhost.com",
            CONF_PASSWORD: "password0",
        }
        assert result["result"].unique_id == "admin@localhost.com"


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test when provided credentials are already configured."""
    config = {
        CONF_EMAIL: "admin@localhost.com",
        CONF_PASSWORD: "password0",
    }
    MockConfigEntry(
        domain=DOMAIN, data=config, unique_id="admin@localhost.com"
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "pyeconet.EcoNetApiInterface.login",
            return_value=EcoNetApiInterface,
        ),
        patch("homeassistant.components.econet.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_EMAIL: "admin@localhost.com",
                CONF_PASSWORD: "password0",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauth flow updates the password."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "admin@localhost.com", CONF_PASSWORD: "password0"},
        unique_id="admin@localhost.com",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "pyeconet.EcoNetApiInterface.login",
            return_value=EcoNetApiInterface,
        ) as mock_login,
        patch("homeassistant.components.econet.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "new_password"}
        )
        await hass.async_block_till_done()

    mock_login.assert_called_once_with("admin@localhost.com", "new_password")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {
        CONF_EMAIL: "admin@localhost.com",
        CONF_PASSWORD: "new_password",
    }


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(InvalidCredentialsError(), "invalid_auth", id="invalid_auth"),
        pytest.param(PyeconetError(), "cannot_connect", id="cannot_connect"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant, side_effect: Exception, error: str
) -> None:
    """Test reauth flow handles errors and can recover."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "admin@localhost.com", CONF_PASSWORD: "password0"},
        unique_id="admin@localhost.com",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with (
        patch(
            "pyeconet.EcoNetApiInterface.login", side_effect=side_effect
        ) as mock_login,
        patch("homeassistant.components.econet.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "wrong_password"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": error}

        mock_login.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "new_password"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new_password"
