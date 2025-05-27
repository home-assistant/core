"""Config flow tests for the Telegram Bot integration."""

from homeassistant.components.telegram_bot.const import ATTR_PARSER, PARSER_MD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_options_flow(
    hass: HomeAssistant, mock_webhooks_config_entry: MockConfigEntry
) -> None:
    """Test options flow without user input."""

    mock_webhooks_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        mock_webhooks_config_entry.entry_id,
        data={
            ATTR_PARSER: PARSER_MD,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][ATTR_PARSER] == PARSER_MD
