"""Test the Snapcast module."""

import socket
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.snapcast.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_CONNECTION = {CONF_HOST: "127.0.0.1", CONF_PORT: 1705}


async def test_full_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_server: AsyncMock
) -> None:
    """Test the full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONNECTION,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Snapcast"
    assert result["data"] == {CONF_HOST: "127.0.0.1", CONF_PORT: 1705}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (socket.gaierror, "invalid_host"),
        (ConnectionRefusedError, "cannot_connect"),
    ],
)
async def test_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_server: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we get the form and handle errors and successful connection."""

    mock_server.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONNECTION,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_server.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONNECTION,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test config flow abort if device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONNECTION,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
