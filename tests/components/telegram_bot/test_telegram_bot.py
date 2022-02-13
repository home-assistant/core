"""Tests for the telegram_bot component."""
from unittest.mock import Mock

from telegram import Update

from homeassistant.components.telegram_bot import DOMAIN, SERVICE_SEND_MESSAGE
from homeassistant.components.telegram_bot.webhooks import TELEGRAM_WEBHOOK_URL


async def test_webhook_platform_init(hass, webhook_platform):
    assert hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE) is True


async def test_polling_platform_init(hass, polling_platform):
    assert hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE) is True


async def test_webhook_endpoint_generates_event(
    hass, webhook_platform, hass_client, update_message_text
):
    client = await hass_client()

    listener = Mock()
    hass.bus.async_listen_once("telegram_text", listener)

    response = await client.post(TELEGRAM_WEBHOOK_URL, json=update_message_text)
    assert response.status == 200
    assert (await response.read()).decode("utf-8") == ""

    # Make sure event has fired
    await hass.async_block_till_done()

    listener.assert_called_once()


async def test_pollbot_update_generates_event(hass, pollbot, update_message_text):
    listener = Mock()
    hass.bus.async_listen_once("telegram_text", listener)

    update = Update.de_json(update_message_text, pollbot.bot)
    pollbot.dispatcher.process_update(update)

    # Make sure event has fired
    await hass.async_block_till_done()

    listener.assert_called_once()


async def test_message_text(hass, pushbot, update_message_text):
    listener = Mock()
    hass.bus.async_listen_once("telegram_text", listener)

    update = Update.de_json(update_message_text, pushbot.bot)
    pushbot.dispatcher.process_update(update)

    # Make sure event has fired
    await hass.async_block_till_done()

    listener.assert_called_once()
    event = listener.call_args[0][0]
    assert event.data["text"] == update_message_text["message"]["text"]


async def test_message_command(hass, pushbot, update_message_command):
    listener = Mock()
    hass.bus.async_listen_once("telegram_command", listener)

    update = Update.de_json(update_message_command, pushbot.bot)
    pushbot.dispatcher.process_update(update)

    # Make sure event has fired
    await hass.async_block_till_done()

    listener.assert_called_once()
    event = listener.call_args[0][0]
    assert event.data["command"] == update_message_command["message"]["text"]


async def test_callback_query(hass, pushbot, update_callback_query):
    listener = Mock()
    hass.bus.async_listen_once("telegram_callback", listener)

    update = Update.de_json(update_callback_query, pushbot.bot)
    pushbot.dispatcher.process_update(update)

    # Make sure event has fired
    await hass.async_block_till_done()

    listener.assert_called_once()
    event = listener.call_args[0][0]
    assert event.data["data"] == update_callback_query["callback_query"]["data"]
