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
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="INELNET 192.168.1.67 (ch 1,2)",
        data={CONF_HOST: "192.168.1.67", CONF_CHANNELS: [1, 2]},
        unique_id="192.168.1.67",
    )


async def test_setup_entry_stores_runtime_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_setup_entry sets entry.runtime_data with one client per channel."""

    def _make_client(host: str, channel: int) -> MagicMock:
        client = MagicMock()
        client.ping = AsyncMock(return_value=True)
        return client

    with (
        patch(
            "homeassistant.components.inelnet.InelnetChannel",
            side_effect=_make_client,
        ) as MockChannel,
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            new_callable=AsyncMock,
        ),
    ):
        result = await async_setup_entry(hass, mock_config_entry)

    assert result is True
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.host == "192.168.1.67"
    assert mock_config_entry.runtime_data.channels == [1, 2]
    clients = mock_config_entry.runtime_data.clients
    assert len(clients) == 2
    assert clients[1] is not clients[2]
    MockChannel.assert_any_call("192.168.1.67", 1)
    MockChannel.assert_any_call("192.168.1.67", 2)


async def test_setup_entry_raises_config_entry_error_when_channels_empty(
    hass: HomeAssistant,
) -> None:
    """Test async_setup_entry raises ConfigEntryError when channels list is empty."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="INELNET empty",
        data={CONF_HOST: "192.168.1.67", CONF_CHANNELS: []},
        unique_id="192.168.1.67",
    )
    entry.add_to_hass(hass)
    with pytest.raises(ConfigEntryError, match="No channels"):
        await async_setup_entry(hass, entry)


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
