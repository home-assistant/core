"""Tests for the NexBlue config flow."""

from unittest.mock import MagicMock

from nexblue_api import NexBlueAuthError, NexBlueConnectionError
from nexblue_api.models import TokenBundle
import pytest

from homeassistant.components.nexblue.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TOKEN

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_client")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the full happy-path user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "User@Example.com",
            CONF_PASSWORD: "password",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    entry = result["result"]
    assert entry.title == "NexBlue (User@Example.com)"
    assert entry.unique_id == "user@example.com"
    assert entry.data == {
        CONF_USERNAME: "User@Example.com",
        CONF_PASSWORD: "password",
        CONF_REFRESH_TOKEN: TOKEN.refresh_token,
    }


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (NexBlueAuthError, "invalid_auth"),
        (NexBlueConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_client: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test errors returned by the user flow."""
    mock_client.async_login.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


@pytest.mark.usefixtures("mock_client")
async def test_user_flow_duplicate_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an account cannot be configured twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_USERNAME: "USER@example.com",
            CONF_PASSWORD: "password",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_retries_with_corrected_credentials(
    hass: HomeAssistant,
    mock_client: MagicMock,
) -> None:
    """Test the user can correct credentials without restarting the flow."""
    mock_client.async_login.side_effect = [NexBlueAuthError, TOKEN]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "incorrect-password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "correct-password",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_rejects_login_without_refresh_token(
    hass: HomeAssistant,
    mock_client: MagicMock,
) -> None:
    """Test a login response without a refresh token is rejected."""
    mock_client.async_login.return_value = TokenBundle(
        access_token="access-token",
        refresh_token=None,
        expires_in=3600,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
