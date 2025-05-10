"""Fixtures for Telegram integration tests."""

from unittest.mock import patch

from homeassistant.components import notify
from homeassistant.components.telegram.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def setup_dependencies(hass: HomeAssistant) -> None:
    """Set up the dependencies for the Telegram component."""
    with patch("homeassistant.components.telegram_bot.async_setup", return_value=True):
        assert await async_setup_component(
            hass,
            notify.DOMAIN,
            {
                notify.DOMAIN: [
                    {
                        "name": DOMAIN,
                        "platform": DOMAIN,
                        "chat_id": 1,
                    },
                ]
            },
        )
        await hass.async_block_till_done()
