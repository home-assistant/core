"""Tests for the AnyList config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from aioanylist import AuthenticationError, TransportError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.any_list.const import (
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

PASSWORD = "secret-password"


@pytest.fixture(name="mock_setup_entry")
def mock_setup_entry_fixture() -> Generator[AsyncMock]:
    """Mock runtime setup during config flow tests."""
    with patch(
        "homeassistant.components.any_list.async_setup_entry", return_value=None
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
        "homeassistant.components.any_list.config_flow.uuid.uuid4",
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
