"""Config flow tests for the Telegram Bot integration."""

from unittest.mock import patch

from telegram import User
from telegram.error import InvalidToken, NetworkError

from homeassistant.components.telegram_bot.const import (
    ATTR_PARSER,
    CONF_PROXY_URL,
    PARSER_MD,
    PLATFORM_BROADCAST,
    PLATFORM_WEBHOOKS,
)
from homeassistant.const import CONF_API_KEY, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_options_flow_no_input(
    hass: HomeAssistant, mock_webhooks_config_entry: MockConfigEntry
) -> None:
    """Test options flow without user input."""
    mock_webhooks_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        mock_webhooks_config_entry.entry_id
    )
    await hass.async_block_till_done()

    assert result["step_id"] == "init"
    assert result["type"] == FlowResultType.FORM


async def test_options_flow(
    hass: HomeAssistant, mock_webhooks_config_entry: MockConfigEntry
) -> None:
    """Test options flow with user input."""
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


async def test_reconfigure_flow_broadcast(
    hass: HomeAssistant,
    mock_webhooks_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test reconfigure flow without user input."""
    mock_webhooks_config_entry.add_to_hass(hass)

    result = await mock_webhooks_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PLATFORM: PLATFORM_BROADCAST,
            CONF_PROXY_URL: "https://test",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_webhooks_config_entry.data[CONF_PLATFORM] == PLATFORM_BROADCAST


async def test_reconfigure_flow_webhooks(
    hass: HomeAssistant,
    mock_webhooks_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test reconfigure flow without user input."""
    mock_webhooks_config_entry.add_to_hass(hass)

    result = await mock_webhooks_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PLATFORM: PLATFORM_WEBHOOKS,
            CONF_PROXY_URL: "https://test",
        },
    )
    await hass.async_block_till_done()

    assert result["step_id"] == "webhooks"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None


async def test_reconfigure_flow_invalid_proxy(
    hass: HomeAssistant,
    mock_webhooks_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow without user input."""
    mock_webhooks_config_entry.add_to_hass(hass)

    result = await mock_webhooks_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.telegram_bot.config_flow.Bot.get_me",
    ) as mock_bot:
        mock_bot.side_effect = NetworkError("mock invalid proxy")

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PLATFORM: PLATFORM_BROADCAST,
                CONF_PROXY_URL: "invalid",
            },
        )
        await hass.async_block_till_done()

    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_proxy_url"


async def test_reauth_flow(
    hass: HomeAssistant, mock_webhooks_config_entry: MockConfigEntry
) -> None:
    """Test a reauthentication flow."""
    mock_webhooks_config_entry.add_to_hass(hass)

    result = await mock_webhooks_config_entry.start_reauth_flow(
        hass, data={CONF_API_KEY: "dummy"}
    )
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.telegram_bot.config_flow.Bot.get_me",
        return_value=User(123456, "Testbot", True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "new mock api key"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_webhooks_config_entry.data[CONF_API_KEY] == "new mock api key"


async def test_reauth_flow_error(
    hass: HomeAssistant, mock_webhooks_config_entry: MockConfigEntry
) -> None:
    """Test a reauthentication flow."""
    mock_webhooks_config_entry.add_to_hass(hass)

    result = await mock_webhooks_config_entry.start_reauth_flow(
        hass, data={CONF_API_KEY: "dummy"}
    )
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.telegram_bot.config_flow.Bot.get_me"
    ) as mock_bot:
        mock_bot.side_effect = InvalidToken("mock invalid token error")

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "new mock api key"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_api_key"
