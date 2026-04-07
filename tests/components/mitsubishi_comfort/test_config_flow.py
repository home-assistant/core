"""Tests for the Mitsubishi Comfort config flow."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.mitsubishi_comfort.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_USERNAME = "test@test.com"
MOCK_PASSWORD = "testpass"


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry and async_unload_entry."""
    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.async_setup_entry",
            return_value=True,
        ) as mock,
        patch(
            "homeassistant.components.mitsubishi_comfort.async_unload_entry",
            return_value=True,
        ),
    ):
        yield mock


async def test_user_step_success(
    hass: HomeAssistant,
    mock_cloud_account: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test successful config flow shows form then creates entry."""
    # First call with no input shows form
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit credentials creates entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Mitsubishi Comfort ({MOCK_USERNAME})"
    assert result["data"] == {
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
    }
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "login_return", "discover_return", "expected_error"),
    [
        (None, False, None, "invalid_auth"),
        (None, True, {}, "cannot_connect"),
        (OSError("Connection refused"), None, None, "cannot_connect"),
        (RuntimeError("Unexpected"), None, None, "unknown"),
    ],
    ids=["invalid_auth", "no_devices", "os_error", "unknown_error"],
)
async def test_user_step_errors(
    hass: HomeAssistant,
    mock_cloud_account: AsyncMock,
    side_effect: Exception | None,
    login_return: bool | None,
    discover_return: dict | None,
    expected_error: str,
) -> None:
    """Test config flow error handling."""
    if side_effect:
        mock_cloud_account.login.side_effect = side_effect
    else:
        mock_cloud_account.login.return_value = login_return
        if discover_return is not None:
            mock_cloud_account.discover_devices.return_value = discover_return

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_user_step_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
) -> None:
    """Test that duplicate config is rejected."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
