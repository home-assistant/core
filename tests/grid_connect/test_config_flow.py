"""Tests for the Grid Connect config flow."""

import asyncio
import sys
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.grid_connect.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.grid_connect.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# Enforce selector policy at import time for this module (Windows)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Allow localhost sockets for asyncio self-pipe early for this module
pytestmark = [
    pytest.mark.enable_socket,
    pytest.mark.socket_allow_hosts(["127.0.0.1", "::1", "localhost"]),
]

# Event loop policy is provided by the session-scoped fixture in tests/grid_connect/conftest.py

@pytest.fixture
def mock_setup_entry():
    """Mock setting up an entry."""
    with patch(
        "homeassistant.components.grid_connect.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.mark.asyncio
async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test manual path creates an entry with device details."""

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {}

    # Choose manual path
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"action": "manual"}
    )
    assert result is not None
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "manual"

    # Provide manual device details
    device = {
        "device_id": "dev-1",
        "device_name": "Test GC Device",
        "device_address": "AA:BB:CC:DD:EE:FF",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], device
    )

    # Validate entry creation
    assert result is not None
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == device["device_name"]
    assert result.get("data") == device


@pytest.mark.skip(reason="Outdated: flow no longer uses username/password/host schema")
async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None

    with patch(
        "homeassistant.components.grid_connect.api.GridConnectAPI.authenticate",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
    assert result is not None
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.grid_connect.api.GridConnectAPI.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result is not None
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Grid Connect"
    assert result.get("data") == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.skip(reason="Outdated: flow no longer uses username/password/host schema")
async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None

    with patch(
        "homeassistant.components.grid_connect.api.GridConnectAPI.authenticate",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
    assert result is not None
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.grid_connect.api.GridConnectAPI.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result is not None
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Grid Connect"
    assert result.get("data") == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.skip(reason="Outdated: flow no longer uses username/password/host schema")
async def test_successful_config_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result.get("type") == "form"
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "test", "password": "test", "host": "1.1.1.1"}
    )

    assert result.get("type") == "create_entry"
    assert result.get("title") == "Grid Connect"
    assert result.get("data") == {
        "username": "test",
        "password": "test",
        "host": "1.1.1.1",
    }


@pytest.mark.skip(reason="Outdated: flow no longer uses username/password/host schema")
async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test handling of invalid authentication."""
    with patch(
        "homeassistant.components.grid_connect.api.GridConnectAPI.authenticate",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "wrong", "password": "wrong", "host": "1.1.1.1"},
        )

        assert result.get("type") == "form"
        assert result.get("errors") == {"base": "invalid_auth"}
