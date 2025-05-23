"""Test the Telegram config flow."""

from unittest.mock import patch

from homeassistant.components import notify
from homeassistant.components.telegram.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component


async def test_async_step_user(hass: HomeAssistant) -> None:
    """Test config flow."""

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

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
