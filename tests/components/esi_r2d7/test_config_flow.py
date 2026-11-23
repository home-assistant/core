"""Tests for the ESI R2D7 config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from serialx import SerialException

from homeassistant.components.esi_r2d7.const import (
    CONF_FIRST_CHANNEL,
    CONF_LAST_CHANNEL,
    CONF_SYSTEM,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady

from . import MOCK_DEVICE
from .conftest import MockConnection

USER_INPUT = {
    CONF_DEVICE: MOCK_DEVICE,
    CONF_SYSTEM: 2.0,
    CONF_FIRST_CHANNEL: 1.0,
    CONF_LAST_CHANNEL: 8.0,
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config-entry creation tests from setting up the integration."""
    with patch(
        "homeassistant.components.esi_r2d7.async_setup_entry", return_value=None
    ) as setup_entry:
        yield setup_entry


async def test_user_form_creates_entry(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a successful flow opens and closes the port, then creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ESI R2D7 system 2"
    assert result["data"] == {
        CONF_DEVICE: MOCK_DEVICE,
        CONF_SYSTEM: 2,
        CONF_FIRST_CHANNEL: 1,
        CONF_LAST_CHANNEL: 8,
    }
    mock_connection.connect.assert_awaited_once()
    mock_connection.disconnect.assert_awaited_once()
    mock_connection.open_blind.assert_not_awaited()
    mock_setup_entry.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ValueError("Invalid port"), "cannot_connect"),
        (OSError("No such device"), "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (SerialException("Proxy unavailable"), "cannot_connect"),
        (ConfigEntryNotReady("ESPHome not ready"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_form_error(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test the user step reports errors and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_connection.connect.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_connection.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_invalid_channel_range(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a first channel above the last channel is refused."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**USER_INPUT, CONF_FIRST_CHANNEL: 9.0, CONF_LAST_CHANNEL: 8.0},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_channel_range"}
    mock_connection.connect.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_duplicate_port_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockConnection,
) -> None:
    """Test we abort if the same port is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_connection.connect.assert_not_awaited()
