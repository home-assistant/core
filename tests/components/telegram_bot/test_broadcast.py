"""Test Telegram broadcast."""

from httpx import Request as HTTPXRequest

from homeassistant.components.telegram_bot.bot import TelegramBotConfigEntry
from homeassistant.components.telegram_bot.const import DEFAULT_TIMEOUT_SECONDS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test setting up Telegram broadcast."""
    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("telegram_bot", "send_message") is True

    config_entry: TelegramBotConfigEntry = hass.config_entries.async_get_known_entry(
        mock_broadcast_config_entry.entry_id
    )
    request: HTTPXRequest = config_entry.runtime_data.bot.request
    assert request.read_timeout == DEFAULT_TIMEOUT_SECONDS
    assert request._media_write_timeout == DEFAULT_TIMEOUT_SECONDS
