"""Tests for INELNET Blinds integration setup and unload."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.inelnet import (
    InelnetRuntimeData,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.inelnet.const import CONF_CHANNELS, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="INELNET 192.168.1.67 (ch 1,2)",
        data={CONF_HOST: "192.168.1.67", CONF_CHANNELS: [1, 2]},
        unique_id="192.168.1.67-1,2",
    )


async def test_setup_entry_stores_runtime_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_setup_entry sets entry.runtime_data with clients and forwards to platforms."""
    with (
        patch(
            "homeassistant.components.inelnet.InelnetChannel",
        ) as MockChannel,
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            new_callable=AsyncMock,
        ),
    ):
        mock_client = MagicMock()
        mock_client.ping = AsyncMock(return_value=True)
        MockChannel.return_value = mock_client

        result = await async_setup_entry(hass, mock_config_entry)

    assert result is True
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.host == "192.168.1.67"
    assert mock_config_entry.runtime_data.channels == [1, 2]
    assert mock_config_entry.runtime_data.clients == {
        1: mock_client,
        2: mock_client,
    }


async def test_setup_entry_raises_not_ready_when_ping_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_setup_entry raises ConfigEntryNotReady when controller ping fails."""
    with patch(
        "homeassistant.components.inelnet.InelnetChannel",
    ) as MockChannel:
        mock_client = MagicMock()
        mock_client.ping = AsyncMock(return_value=False)
        MockChannel.return_value = mock_client

        with pytest.raises(ConfigEntryNotReady, match="did not respond"):
            await async_setup_entry(hass, mock_config_entry)


async def test_setup_entry_raises_not_ready_on_connection_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_setup_entry raises ConfigEntryNotReady when ping raises."""
    with patch(
        "homeassistant.components.inelnet.InelnetChannel",
    ) as MockChannel:
        mock_client = MagicMock()
        mock_client.ping = AsyncMock(side_effect=OSError("Connection refused"))
        MockChannel.return_value = mock_client

        with pytest.raises(ConfigEntryNotReady, match="Cannot connect"):
            await async_setup_entry(hass, mock_config_entry)


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_unload_entry unloads platforms and returns True."""
    mock_config_entry.runtime_data = InelnetRuntimeData(
        host="192.168.1.67",
        channels=[1, 2],
        clients={1: MagicMock(), 2: MagicMock()},
    )
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await async_unload_entry(hass, mock_config_entry)
    assert result is True
