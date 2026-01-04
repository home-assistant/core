"""Test Telegram broadcast."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant, mock_broadcast_config_entry: MockConfigEntry
) -> None:
    """Test setting up Telegram broadcast."""
    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("telegram_bot", "send_message") is True
