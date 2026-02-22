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
    """Test async_setup_entry sets entry.runtime_data and forwards to platforms."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "homeassistant.components.inelnet.async_get_clientsession",
        ) as mock_session_cls,
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            new_callable=AsyncMock,
        ),
    ):
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session_cls.return_value = mock_session

        result = await async_setup_entry(hass, mock_config_entry)

    assert result is True
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.host == "192.168.1.67"
    assert mock_config_entry.runtime_data.channels == [1, 2]


async def test_setup_entry_raises_not_ready_on_connection_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_setup_entry raises ConfigEntryNotReady when controller is unreachable."""
    failing_resp = AsyncMock()
    failing_resp.__aenter__ = AsyncMock(side_effect=OSError("Connection refused"))
    failing_resp.__aexit__ = AsyncMock(return_value=None)
    with patch(
        "homeassistant.components.inelnet.async_get_clientsession",
    ) as mock_session_cls:
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=failing_resp)
        mock_session_cls.return_value = mock_session

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry)


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_unload_entry unloads platforms and returns True."""
    mock_config_entry.runtime_data = InelnetRuntimeData(
        host="192.168.1.67",
        channels=[1, 2],
    )
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await async_unload_entry(hass, mock_config_entry)
    assert result is True
