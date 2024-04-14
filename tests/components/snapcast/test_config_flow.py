"""Test the Snapcast module."""

import socket
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries, setup
from homeassistant.components.snapcast.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_CONNECTION = {CONF_HOST: "snapserver.test", CONF_PORT: 1705}

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "mock_create_server")


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_create_server: AsyncMock
) -> None:
    """Test we get the form and handle errors and successful connection."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    # test invalid host error
    with patch("snapcast.control.create_server", side_effect=socket.gaierror):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_host"}

    # test connection error
    with patch("snapcast.control.create_server", side_effect=ConnectionRefusedError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    # test success
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_CONNECTION
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Snapcast"
    assert result["data"] == {CONF_HOST: "snapserver.test", CONF_PORT: 1705}
    assert len(mock_create_server.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_create_server: AsyncMock
) -> None:
    """Test config flow abort if device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONNECTION,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    with patch("snapcast.control.create_server", side_effect=socket.gaierror):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_CONNECTION,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
