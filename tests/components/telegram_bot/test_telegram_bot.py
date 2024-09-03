"""Tests for the telegram_bot component."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Update
from telegram.error import NetworkError, RetryAfter, TelegramError, TimedOut

from homeassistant.components.telegram_bot import (
    ATTR_MESSAGE,
    ATTR_MESSAGE_THREAD_ID,
    DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.components.telegram_bot.webhooks import TELEGRAM_WEBHOOK_URL
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_capture_events
from tests.typing import ClientSessionGenerator


async def test_webhook_platform_init(hass: HomeAssistant, webhook_platform) -> None:
    """Test initialization of the webhooks platform."""
    assert hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE) is True


async def test_polling_platform_init(hass: HomeAssistant, polling_platform) -> None:
    """Test initialization of the polling platform."""
    assert hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE) is True


async def test_send_message(hass: HomeAssistant, webhook_platform) -> None:
    """Test the send_message service."""
    context = Context()
    events = async_capture_events(hass, "telegram_sent")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_MESSAGE: "test_message", ATTR_MESSAGE_THREAD_ID: "123"},
        blocking=True,
        context=context,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].context == context


async def test_send_message_thread(hass: HomeAssistant, webhook_platform) -> None:
    """Test the send_message service for threads."""
    context = Context()
    events = async_capture_events(hass, "telegram_sent")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_MESSAGE: "test_message", ATTR_MESSAGE_THREAD_ID: "123"},
        blocking=True,
        context=context,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].context == context
    assert events[0].data[ATTR_MESSAGE_THREAD_ID] == "123"


async def test_webhook_endpoint_generates_telegram_text_event(
    hass: HomeAssistant,
    webhook_platform,
    hass_client: ClientSessionGenerator,
    update_message_text,
    mock_generate_secret_token,
) -> None:
    """POST to the configured webhook endpoint and assert fired `telegram_text` event."""
    client = await hass_client()
    events = async_capture_events(hass, "telegram_text")

    response = await client.post(
        TELEGRAM_WEBHOOK_URL,
        json=update_message_text,
        headers={"X-Telegram-Bot-Api-Secret-Token": mock_generate_secret_token},
    )
    assert response.status == 200
    assert (await response.read()).decode("utf-8") == ""

    # Make sure event has fired
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["text"] == update_message_text["message"]["text"]
    assert isinstance(events[0].context, Context)


async def test_webhook_endpoint_generates_telegram_command_event(
    hass: HomeAssistant,
    webhook_platform,
    hass_client: ClientSessionGenerator,
    update_message_command,
    mock_generate_secret_token,
) -> None:
    """POST to the configured webhook endpoint and assert fired `telegram_command` event."""
    client = await hass_client()
    events = async_capture_events(hass, "telegram_command")

    response = await client.post(
        TELEGRAM_WEBHOOK_URL,
        json=update_message_command,
        headers={"X-Telegram-Bot-Api-Secret-Token": mock_generate_secret_token},
    )
    assert response.status == 200
    assert (await response.read()).decode("utf-8") == ""

    # Make sure event has fired
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["command"] == update_message_command["message"]["text"]
    assert isinstance(events[0].context, Context)


async def test_webhook_endpoint_generates_telegram_callback_event(
    hass: HomeAssistant,
    webhook_platform,
    hass_client: ClientSessionGenerator,
    update_callback_query,
    mock_generate_secret_token,
) -> None:
    """POST to the configured webhook endpoint and assert fired `telegram_callback` event."""
    client = await hass_client()
    events = async_capture_events(hass, "telegram_callback")

    response = await client.post(
        TELEGRAM_WEBHOOK_URL,
        json=update_callback_query,
        headers={"X-Telegram-Bot-Api-Secret-Token": mock_generate_secret_token},
    )
    assert response.status == 200
    assert (await response.read()).decode("utf-8") == ""

    # Make sure event has fired
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["data"] == update_callback_query["callback_query"]["data"]
    assert isinstance(events[0].context, Context)


async def test_polling_platform_message_text_update(
    hass: HomeAssistant, config_polling, update_message_text
) -> None:
    """Provide the `BaseTelegramBotEntity.update_handler` with an `Update` and assert fired `telegram_text` event."""
    events = async_capture_events(hass, "telegram_text")

    with patch(
        "homeassistant.components.telegram_bot.polling.ApplicationBuilder"
    ) as application_builder_class:
        await async_setup_component(
            hass,
            DOMAIN,
            config_polling,
        )
        await hass.async_block_till_done()
        # Set up the integration with the polling platform inside the patch context manager.
        application = (
            application_builder_class.return_value.bot.return_value.build.return_value
        )
        # Then call the callback and assert events fired.
        handler = application.add_handler.call_args[0][0]
        handle_update_callback = handler.callback

        # Create Update object using library API.
        application.bot.defaults.tzinfo = None
        update = Update.de_json(update_message_text, application.bot)

        # handle_update_callback == BaseTelegramBotEntity.update_handler
        await handle_update_callback(update, None)

        application.updater.stop = AsyncMock()
        application.stop = AsyncMock()
        application.shutdown = AsyncMock()

    # Make sure event has fired
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["text"] == update_message_text["message"]["text"]
    assert isinstance(events[0].context, Context)


@pytest.mark.parametrize(
    ("error", "log_message"),
    [
        (
            TelegramError("Telegram error"),
            'caused error: "Telegram error"',
        ),
        (NetworkError("Network error"), ""),
        (RetryAfter(42), ""),
        (TimedOut("TimedOut error"), ""),
    ],
)
async def test_polling_platform_add_error_handler(
    hass: HomeAssistant,
    config_polling: dict[str, Any],
    update_message_text: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    log_message: str,
) -> None:
    """Test polling add error handler."""
    with patch(
        "homeassistant.components.telegram_bot.polling.ApplicationBuilder"
    ) as application_builder_class:
        await async_setup_component(
            hass,
            DOMAIN,
            config_polling,
        )
        await hass.async_block_till_done()

        application = (
            application_builder_class.return_value.bot.return_value.build.return_value
        )
        application.updater.stop = AsyncMock()
        application.stop = AsyncMock()
        application.shutdown = AsyncMock()
        process_error = application.add_error_handler.call_args[0][0]
        application.bot.defaults.tzinfo = None
        update = Update.de_json(update_message_text, application.bot)

        await process_error(update, MagicMock(error=error))

        assert log_message in caplog.text


@pytest.mark.parametrize(
    ("error", "log_message"),
    [
        (
            TelegramError("Telegram error"),
            "TelegramError: Telegram error",
        ),
        (NetworkError("Network error"), ""),
        (RetryAfter(42), ""),
        (TimedOut("TimedOut error"), ""),
    ],
)
async def test_polling_platform_start_polling_error_callback(
    hass: HomeAssistant,
    config_polling: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    log_message: str,
) -> None:
    """Test polling add error handler."""
    with patch(
        "homeassistant.components.telegram_bot.polling.ApplicationBuilder"
    ) as application_builder_class:
        await async_setup_component(
            hass,
            DOMAIN,
            config_polling,
        )
        await hass.async_block_till_done()

        application = (
            application_builder_class.return_value.bot.return_value.build.return_value
        )
        application.initialize = AsyncMock()
        application.updater.start_polling = AsyncMock()
        application.start = AsyncMock()
        application.updater.stop = AsyncMock()
        application.stop = AsyncMock()
        application.shutdown = AsyncMock()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        error_callback = application.updater.start_polling.call_args.kwargs[
            "error_callback"
        ]

        error_callback(error)

        assert log_message in caplog.text


async def test_webhook_endpoint_unauthorized_update_doesnt_generate_telegram_text_event(
    hass: HomeAssistant,
    webhook_platform,
    hass_client: ClientSessionGenerator,
    unauthorized_update_message_text,
    mock_generate_secret_token,
) -> None:
    """Update with unauthorized user/chat should not trigger event."""
    client = await hass_client()
    events = async_capture_events(hass, "telegram_text")

    response = await client.post(
        TELEGRAM_WEBHOOK_URL,
        json=unauthorized_update_message_text,
        headers={"X-Telegram-Bot-Api-Secret-Token": mock_generate_secret_token},
    )
    assert response.status == 200
    assert (await response.read()).decode("utf-8") == ""

    # Make sure any events would have fired
    await hass.async_block_till_done()

    assert len(events) == 0


async def test_webhook_endpoint_without_secret_token_is_denied(
    hass: HomeAssistant,
    webhook_platform,
    hass_client: ClientSessionGenerator,
    update_message_text,
) -> None:
    """Request without a secret token header should be denied."""
    client = await hass_client()
    async_capture_events(hass, "telegram_text")

    response = await client.post(
        TELEGRAM_WEBHOOK_URL,
        json=update_message_text,
    )
    assert response.status == 401


async def test_webhook_endpoint_invalid_secret_token_is_denied(
    hass: HomeAssistant,
    webhook_platform,
    hass_client: ClientSessionGenerator,
    update_message_text,
    incorrect_secret_token,
) -> None:
    """Request with an invalid secret token header should be denied."""
    client = await hass_client()
    async_capture_events(hass, "telegram_text")

    response = await client.post(
        TELEGRAM_WEBHOOK_URL,
        json=update_message_text,
        headers={"X-Telegram-Bot-Api-Secret-Token": incorrect_secret_token},
    )
    assert response.status == 401
