"""Test Telegram broadcast."""
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_setup(hass: HomeAssistant) -> None:
    """Test setting up Telegram broadcast."""
    assert await async_setup_component(
        hass,
        "telegram_bot",
        {
            "telegram_bot": {
                "platform": "broadcast",
                "api_key": "1234567890:ABC",
                "allowed_chat_ids": [1],
            }
        },
    )
    await hass.async_block_till_done()

    assert hass.services.has_service("telegram_bot", "send_message") is True
