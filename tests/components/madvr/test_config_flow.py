"""Tests for the MadVR config flow."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.madvr.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_CONFIG, MOCK_MAC

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
async def avoid_wait() -> AsyncGenerator[None, None]:
    """Mock sleep."""
    with patch("homeassistant.components.madvr.config_flow.RETRY_INTERVAL", 0):
        yield


async def test_full_flow(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_CONFIG[CONF_HOST], CONF_PORT: MOCK_CONFIG[CONF_PORT]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: MOCK_CONFIG[CONF_HOST],
        CONF_PORT: MOCK_CONFIG[CONF_PORT],
    }
    assert result["result"].unique_id == MOCK_MAC
    mock_madvr_client.open_connection.assert_called_once()
    mock_madvr_client.async_add_tasks.assert_called_once()
    mock_madvr_client.async_cancel_tasks.assert_called_once()


async def test_flow_errors(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test error handling in config flow."""
    mock_madvr_client.open_connection.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_CONFIG[CONF_HOST], CONF_PORT: MOCK_CONFIG[CONF_PORT]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_madvr_client.open_connection.side_effect = None
    mock_madvr_client.connected = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_CONFIG[CONF_HOST], CONF_PORT: MOCK_CONFIG[CONF_PORT]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_madvr_client.connected = True
    mock_madvr_client.mac_address = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_CONFIG[CONF_HOST], CONF_PORT: MOCK_CONFIG[CONF_PORT]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_mac"}

    # ensure an error is recoverable
    mock_madvr_client.mac_address = MOCK_MAC
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_CONFIG[CONF_HOST], CONF_PORT: MOCK_CONFIG[CONF_PORT]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_HOST: MOCK_CONFIG[CONF_HOST],
        CONF_PORT: MOCK_CONFIG[CONF_PORT],
    }

    # Verify method calls
    assert mock_madvr_client.open_connection.call_count == 4
    assert mock_madvr_client.async_add_tasks.call_count == 2
    # the first call will not call this due to timeout as expected
    assert mock_madvr_client.async_cancel_tasks.call_count == 2


async def test_duplicate(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate config entries."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_CONFIG[CONF_HOST], CONF_PORT: MOCK_CONFIG[CONF_PORT]},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
