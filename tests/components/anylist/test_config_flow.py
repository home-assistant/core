"""Tests for the AnyList config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from aioanylist import AuthenticationError, AuthTokens, TransportError
import pytest

from homeassistant import config_entries
from homeassistant.components.anylist.const import (
    CONF_REFRESH_TOKEN,
    CONF_USER_LOCALE,
    DOMAIN,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    ACCESS_TOKEN,
    CLIENT_ID,
    EMAIL,
    REFRESH_TOKEN,
    USER_ID,
    USER_LOCALE,
)

from tests.common import MockConfigEntry

PASSWORD = "secret-password"


@pytest.fixture(name="mock_setup_entry")
def mock_setup_entry_fixture() -> Generator[AsyncMock]:
    """Mock runtime setup during config flow tests."""
    with patch(
        "homeassistant.components.anylist.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_anylist_client: MagicMock,
) -> None:
    """Test a successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.anylist.config_flow.uuid.uuid4",
        return_value=uuid.UUID(hex=CLIENT_ID),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["result"].unique_id == USER_ID
    assert result["data"] == {
        CONF_EMAIL: EMAIL,
        CONF_CLIENT_ID: CLIENT_ID,
        CONF_ACCESS_TOKEN: ACCESS_TOKEN,
        CONF_REFRESH_TOKEN: REFRESH_TOKEN,
        CONF_USER_LOCALE: USER_LOCALE,
    }
    assert CONF_PASSWORD not in result["data"]
    mock_anylist_client.sign_in.assert_awaited_once_with(EMAIL, PASSWORD)
    mock_anylist_client.close.assert_awaited_once()
    assert mock_setup_entry.call_count == 1


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        (AuthenticationError(), "invalid_auth"),
        (TransportError(), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (ValueError(), "unknown"),
    ],
)
async def test_user_flow_errors_and_recovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_anylist_client: MagicMock,
    error: Exception,
    expected_error: str,
) -> None:
    """Test config flow errors and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_anylist_client.sign_in.side_effect = error

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_anylist_client.sign_in.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USER_ID
    assert mock_setup_entry.call_count == 1


async def test_duplicate_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test that the same AnyList account cannot be configured twice."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_anylist_client: MagicMock,
) -> None:
    """Test reauthenticating an AnyList account."""
    mock_config_entry.add_to_hass(hass)
    mock_anylist_client.sign_in.return_value = AuthTokens(
        user_id=USER_ID,
        access_token="new-access-token",
        refresh_token="new-refresh-token",
        user_locale="de-DE",
    )

    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    [flow] = hass.config_entries.flow.async_progress()
    assert flow["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_EMAIL: EMAIL,
        CONF_CLIENT_ID: CLIENT_ID,
        CONF_ACCESS_TOKEN: "new-access-token",
        CONF_REFRESH_TOKEN: "new-refresh-token",
        CONF_USER_LOCALE: "de-DE",
    }
    mock_anylist_client.sign_in.assert_awaited_once_with(EMAIL, "new-password")
    assert mock_setup_entry.call_count == 1


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        (AuthenticationError(), "invalid_auth"),
        (TransportError(), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (ValueError(), "unknown"),
    ],
)
async def test_reauth_errors_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_anylist_client: MagicMock,
    error: Exception,
    expected_error: str,
) -> None:
    """Test reauthentication errors and recovery."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    [flow] = hass.config_entries.flow.async_progress()

    mock_anylist_client.sign_in.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {CONF_PASSWORD: "bad-password"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_anylist_client.sign_in.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {CONF_PASSWORD: "good-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_setup_entry.call_count == 1


async def test_reauth_different_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test reauthentication rejects a different AnyList account."""
    mock_config_entry.add_to_hass(hass)
    mock_anylist_client.sign_in.return_value = AuthTokens(
        user_id="different-user",
        access_token="other-access",
        refresh_token="other-refresh",
    )

    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    [flow] = hass.config_entries.flow.async_progress()
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {CONF_PASSWORD: "password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
