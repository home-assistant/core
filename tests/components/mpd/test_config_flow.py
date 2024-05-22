"""Tests for the Music Player Daemon config flow."""

from socket import gaierror
from unittest.mock import AsyncMock

import mpd
import pytest

from homeassistant.components.mpd.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mpd_client: AsyncMock,
) -> None:
    """Test the happy flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.1", CONF_PORT: 6600, CONF_PASSWORD: "test123"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Music Player Daemon"
    assert result["data"] == {
        CONF_HOST: "192.168.0.1",
        CONF_PORT: 6600,
        CONF_PASSWORD: "test123",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (TimeoutError, "cannot_connect"),
        (gaierror, "cannot_connect"),
        (mpd.ConnectionError, "cannot_connect"),
        (OSError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mpd_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle errors correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    mock_mpd_client.password.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.1", CONF_PORT: 6600, CONF_PASSWORD: "test123"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_mpd_client.password.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.1", CONF_PORT: 6600, CONF_PASSWORD: "test123"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_existing_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if an entry already exists."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.1", CONF_PORT: 6600, CONF_PASSWORD: "test123"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_full_import_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mpd_client: AsyncMock,
) -> None:
    """Test the happy flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 6600,
            CONF_PASSWORD: "test123",
            CONF_NAME: "My PC",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My PC"
    assert result["data"] == {
        CONF_HOST: "192.168.0.1",
        CONF_PORT: 6600,
        CONF_PASSWORD: "test123",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (TimeoutError, "cannot_connect"),
        (gaierror, "cannot_connect"),
        (mpd.ConnectionError, "cannot_connect"),
        (OSError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_import_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mpd_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle errors correctly."""
    mock_mpd_client.password.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 6600,
            CONF_PASSWORD: "test123",
            CONF_NAME: "My PC",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error


async def test_existing_entry_import(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if an entry already exists."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 6600,
            CONF_PASSWORD: "test123",
            CONF_NAME: "My PC",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
