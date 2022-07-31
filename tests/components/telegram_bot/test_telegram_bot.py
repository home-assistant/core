"""Tests for the telegram_bot component."""
import pytest
from telegram import Update
from telegram.ext.dispatcher import Dispatcher

from homeassistant.components.telegram_bot import DOMAIN, SERVICE_SEND_MESSAGE
from homeassistant.components.telegram_bot.webhooks import TELEGRAM_WEBHOOK_URL

from tests.common import async_capture_events


@pytest.fixture(autouse=True)
def clear_dispatcher():
    """Clear the singleton that telegram.ext.dispatcher.Dispatcher sets on itself."""
    yield
    Dispatcher._set_singleton(None)
    # This is how python-telegram-bot resets the dispatcher in their test suite
    Dispatcher._Dispatcher__singleton_semaphore.release()


async def test_webhook_platform_init(hass, webhook_platform):
    """Test initialization of the webhooks platform."""
    assert hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE) is True


async def test_polling_platform_init(hass, polling_platform):
    """Test initialization of the polling platform."""
    assert hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE) is True


async def test_webhook_endpoint_generates_telegram_text_event(
    hass, webhook_platform, hass_client, update_message_text
):
    """POST to the configured webhook endpoint and assert fired `telegram_text` event."""
    client = await hass_client()
    events = async_capture_events(hass, "telegram_text")

    response = await client.post(TELEGRAM_WEBHOOK_URL, json=update_message_text)
    assert response.status == 200
    assert (await response.read()).decode("utf-8") == ""

    # Make sure event has fired
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["text"] == update_message_text["message"]["text"]


async def test_webhook_endpoint_generates_telegram_command_event(
    hass, webhook_platform, hass_client, update_message_command
):
    """POST to the configured webhook endpoint and assert fired `telegram_command` event."""
    client = await hass_client()
    events = async_capture_events(hass, "telegram_command")

    response = await client.post(TELEGRAM_WEBHOOK_URL, json=update_message_command)
    assert response.status == 200
    assert (await response.read()).decode("utf-8") == ""

    # Make sure event has fired
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["command"] == update_message_command["message"]["text"]


async def test_webhook_endpoint_generates_telegram_callback_event(
    hass, webhook_platform, hass_client, update_callback_query
):
    """POST to the configured webhook endpoint and assert fired `telegram_callback` event."""
    client = await hass_client()
    events = async_capture_events(hass, "telegram_callback")

    response = await client.post(TELEGRAM_WEBHOOK_URL, json=update_callback_query)
    assert response.status == 200
    assert (await response.read()).decode("utf-8") == ""

    # Make sure event has fired
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["data"] == update_callback_query["callback_query"]["data"]


async def test_polling_platform_message_text_update(
    hass, polling_platform, update_message_text
):
    """Provide the `PollBot`s `Dispatcher` with an `Update` and assert fired `telegram_text` event."""
    events = async_capture_events(hass, "telegram_text")

    def telegram_dispatcher_callback():
        dispatcher = Dispatcher.get_instance()
        update = Update.de_json(update_message_text, dispatcher.bot)
        dispatcher.process_update(update)

    # python-telegram-bots `Updater` uses threading, so we need to schedule its callback in a sync context.
    await hass.async_add_executor_job(telegram_dispatcher_callback)

    # Make sure event has fired
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["text"] == update_message_text["message"]["text"]


async def test_webhook_endpoint_unauthorized_update_doesnt_generate_telegram_text_event(
    hass, webhook_platform, hass_client, unauthorized_update_message_text
):
    """Update with unauthorized user/chat should not trigger event."""
    client = await hass_client()
    events = async_capture_events(hass, "telegram_text")

    response = await client.post(
        TELEGRAM_WEBHOOK_URL, json=unauthorized_update_message_text
    )
    assert response.status == 200
    assert (await response.read()).decode("utf-8") == ""

    # Make sure any events would have fired
    await hass.async_block_till_done()

    assert len(events) == 0
