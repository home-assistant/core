"""Test the Ridwell config flow."""
from unittest.mock import AsyncMock, patch

from aioridwell.errors import InvalidCredentialsError, RidwellError
import pytest

from homeassistant import config_entries
from homeassistant.components.ridwell.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="client")
def client_fixture():
    """Define a fixture for an aioridwell client."""
    return AsyncMock(return_value=None)


@pytest.fixture(name="client_login")
def client_login_fixture(client):
    """Define a fixture for patching the aioridwell coroutine to get a client."""
    with patch(
        "homeassistant.components.ridwell.config_flow.async_get_client"
    ) as mock_client:
        mock_client.side_effect = client
        yield mock_client


async def test_duplicate_error(hass: HomeAssistant):
    """Test that errors are shown when duplicate entries are added."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@email.com",
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_show_form_user(hass: HomeAssistant) -> None:
    """Test showing the form to input credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None


async def test_step_reauth(hass: HomeAssistant, client_login) -> None:
    """Test a full reauth flow."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@email.com",
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.ridwell.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_REAUTH},
            data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1


async def test_step_user(hass: HomeAssistant, client_login) -> None:
    """Test that the full user step succeeds."""
    with patch(
        "homeassistant.components.ridwell.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY


@pytest.mark.parametrize(
    "client,error",
    [
        (AsyncMock(side_effect=InvalidCredentialsError), "invalid_auth"),
        (AsyncMock(side_effect=RidwellError), "unknown"),
    ],
)
async def test_step_user_invalid_credentials(
    hass: HomeAssistant, client_login, error
) -> None:
    """Test that invalid credentials are handled correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"]["base"] == error
