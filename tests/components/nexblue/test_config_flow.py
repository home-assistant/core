"""Tests for the NexBlue config flow."""

from unittest.mock import MagicMock

from nexblue_api import NexBlueAuthError, NexBlueConnectionError, NexBlueError
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
    assert entry.unique_id == TOKEN.account_id
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
        (NexBlueError, "unknown"),
        (Exception, "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_client: MagicMock,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test the user flow can recover after an error."""
    mock_client.async_login.side_effect = [side_effect, TOKEN]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "incorrect-password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "correct-password",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


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
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

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
    """Test the user flow can recover when a login response lacks a refresh token."""
    mock_client.async_login.side_effect = [
        TokenBundle(
            access_token="access-token",
            refresh_token=None,
            expires_in=3600,
            account_id="00000000-0000-0000-0000-000000000001",
        ),
        TOKEN,
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "password",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_rejects_login_without_account_id(
    hass: HomeAssistant,
    mock_client: MagicMock,
) -> None:
    """Test the user flow can recover when a login response lacks an account ID."""
    mock_client.async_login.side_effect = [
        TokenBundle(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=3600,
        ),
        TOKEN,
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "password",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
