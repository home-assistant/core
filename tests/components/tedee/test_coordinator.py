"""Tests for tedee lock."""
import time
from unittest.mock import MagicMock

from pytedee_async.exception import TedeeDataUpdateException, TedeeWebhookException
import pytest

from homeassistant.components.tedee.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_coordinator(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog,
) -> None:
    """Test coordinator."""
    mock_tedee.sync.side_effect = TedeeDataUpdateException("")
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    coordinator._last_data_update -= 301
    await coordinator.async_request_refresh()
    assert coordinator._stale_data is True
    assert "Data hasn't been updated" in caplog.text

    coordinator._last_data_update = time.time()
    await coordinator._async_update_data()
    assert coordinator._stale_data is False
    assert "receiving updated data again" in caplog.text

    mock_tedee.locks_dict = {}
    await coordinator._async_update_data()
    assert "No locks found in your account" in caplog.text


async def test_coordinator_callback(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog,
) -> None:
    """Testing the callback."""
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]

    data = {"type": "device-connection-changed", "data": {"isConnected": 1}}

    coordinator._initialized = True
    coordinator.webhook_received(data)
    mock_tedee.parse_webhook_message.assert_called_once_with(data)

    coordinator._initialized = False
    coordinator.webhook_received(data)

    mock_tedee.parse_webhook_message.side_effect = TedeeWebhookException(
        "Weird data received"
    )
    coordinator.webhook_received(data)
    assert "Weird data received" in caplog.text
