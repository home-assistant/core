"""Test the Snapcast module."""

import socket
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries, setup
from homeassistant.components.snapcast.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

TEST_CONNECTION = {CONF_HOST: "snapserver.test", CONF_PORT: 1705}

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "mock_create_server")


async def test_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_create_server: AsyncMock
) -> None:
    """Test successful connection."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_CONNECTION
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert (
        result["title"] == f"{TEST_CONNECTION[CONF_HOST]}:{TEST_CONNECTION[CONF_PORT]}"
    )
    assert result["data"] == TEST_CONNECTION
    assert len(mock_create_server.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_unknown_error(hass: HomeAssistant) -> None:
    """Test what happens when there is no server to connect."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    with patch("snapcast.control.create_server", side_effect=socket.gaierror):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test what happens when there is no server to connect."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    with patch("snapcast.control.create_server", side_effect=ConnectionRefusedError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_import(hass: HomeAssistant, mock_create_server: AsyncMock) -> None:
    """Test successful import."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=TEST_CONNECTION,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert (
        result["title"] == f"{TEST_CONNECTION[CONF_HOST]}:{TEST_CONNECTION[CONF_PORT]}"
    )
    assert result["data"] == TEST_CONNECTION
    assert len(mock_create_server.mock_calls) == 1
