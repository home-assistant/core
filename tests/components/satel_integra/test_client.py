"""Test Satel Integra client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.satel_integra.client import SatelClient
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_connection_state_logging(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test logging an outage and subsequent recovery."""
    client = SatelClient(hass, mock_config_entry)
    await client.async_connect(MagicMock(), MagicMock(), MagicMock())

    mock_satel.connected = False
    client._on_connection_state_change()

    assert "Satel Integra device is unavailable" in caplog.text

    caplog.clear()
    mock_satel.connected = True
    client._on_connection_state_change()

    assert "Satel Integra device is back online" in caplog.text
