"""Tests for the telegram_bot component."""

import base64
from datetime import datetime
import io
from typing import Any
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from telegram import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import (
    InvalidToken,
    NetworkError,
    RetryAfter,
    TelegramError,
    TimedOut,
)

from homeassistant.components.telegram_bot import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    async_setup_entry,
)
from homeassistant.components.telegram_bot.const import (
    ATTR_AUTHENTICATION,
    ATTR_CALLBACK_QUERY_ID,
    ATTR_CAPTION,
    ATTR_CHAT_ACTION,
    ATTR_CHAT_ID,
    ATTR_DISABLE_NOTIF,
    ATTR_DISABLE_WEB_PREV,
    ATTR_FILE,
    ATTR_KEYBOARD,
    ATTR_KEYBOARD_INLINE,
    ATTR_MESSAGE,
    ATTR_MESSAGE_TAG,
    ATTR_MESSAGE_THREAD_ID,
    ATTR_MESSAGEID,
    ATTR_OPTIONS,
    ATTR_PARSER,
    ATTR_PASSWORD,
    ATTR_QUESTION,
    ATTR_REPLY_TO_MSGID,
    ATTR_SHOW_ALERT,
    ATTR_STICKER_ID,
    ATTR_TARGET,
    ATTR_TIMEOUT,
    ATTR_URL,
    ATTR_USERNAME,
    ATTR_VERIFY_SSL,
    CHAT_ACTION_TYPING,
    CONF_CONFIG_ENTRY_ID,
    DOMAIN,
    PARSER_PLAIN_TEXT,
    PLATFORM_BROADCAST,
    SECTION_ADVANCED_SETTINGS,
    SERVICE_ANSWER_CALLBACK_QUERY,
    SERVICE_DELETE_MESSAGE,
    SERVICE_EDIT_CAPTION,
    SERVICE_EDIT_MESSAGE,
    SERVICE_EDIT_REPLYMARKUP,
    SERVICE_LEAVE_CHAT,
    SERVICE_SEND_ANIMATION,
    SERVICE_SEND_CHAT_ACTION,
    SERVICE_SEND_DOCUMENT,
    SERVICE_SEND_LOCATION,
    SERVICE_SEND_MESSAGE,
    SERVICE_SEND_PHOTO,
    SERVICE_SEND_POLL,
    SERVICE_SEND_STICKER,
    SERVICE_SEND_VIDEO,
    SERVICE_SEND_VOICE,
)
from homeassistant.components.telegram_bot.webhooks import TELEGRAM_WEBHOOK_URL
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_PLATFORM,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_BEARER_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import json as json_util
from homeassistant.util.file import write_utf8_file

from tests.common import MockConfigEntry, async_capture_events, async_load_fixture
from tests.typing import ClientSessionGenerator


async def test_webhook_platform_init(hass: HomeAssistant, webhook_platform) -> None:
    """Test initialization of the webhooks platform."""
    assert hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE) is True


async def test_polling_platform_init(hass: HomeAssistant, polling_platform) -> None:
    """Test initialization of the polling platform."""
    assert hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE) is True


@pytest.mark.parametrize(
    ("service", "input"),
    [
        (
            SERVICE_SEND_MESSAGE,
            {ATTR_MESSAGE: "test_message", ATTR_MESSAGE_THREAD_ID: "123"},
        ),
        (
            SERVICE_SEND_MESSAGE,
            {
                ATTR_KEYBOARD: ["/command1, /command2", "/command3"],
                ATTR_MESSAGE: "test_message",
                ATTR_PARSER: ParseMode.HTML,
                ATTR_TIMEOUT: 15,
                ATTR_DISABLE_NOTIF: True,
                ATTR_DISABLE_WEB_PREV: True,
                ATTR_MESSAGE_TAG: "mock_tag",
                ATTR_REPLY_TO_MSGID: 12345,
            },
        ),
        (
            SERVICE_SEND_MESSAGE,
            {
                ATTR_KEYBOARD: [],
                ATTR_MESSAGE: "test_message",
            },
        ),
        (
            SERVICE_SEND_STICKER,
            {
                ATTR_STICKER_ID: "1",
                ATTR_MESSAGE_THREAD_ID: "123",
            },
        ),
        (
            SERVICE_SEND_POLL,
            {
                ATTR_QUESTION: "Question",
                ATTR_OPTIONS: ["Yes", "No"],
            },
        ),
        (
            SERVICE_SEND_LOCATION,
            {
                ATTR_MESSAGE: "test_message",
                ATTR_MESSAGE_THREAD_ID: "123",
                ATTR_LONGITUDE: "1.123",
                ATTR_LATITUDE: "1.123",
            },
        ),
    ],
)
async def test_send_message(
    hass: HomeAssistant, webhook_platform, service: str, input: dict[str]
) -> None:
    """Test the send_message service. Tests any service that does not require files to be sent."""
    context = Context()
    events = async_capture_events(hass, "telegram_sent")

    response = await hass.services.async_call(
        DOMAIN,
        service,
        input,
        blocking=True,
        context=context,
        return_response=True,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].context == context

    config_entry = hass.config_entries.async_entry_for_domain_unique_id(
        DOMAIN, "1234567890:ABC"
    )
    assert events[0].data["bot"]["config_entry_id"] == config_entry.entry_id
    assert events[0].data["bot"]["id"] == 123456
    assert events[0].data["bot"]["first_name"] == "Testbot"
    assert events[0].data["bot"]["last_name"] == "mock last name"
    assert events[0].data["bot"]["username"] == "mock username"

    assert len(response["chats"]) == 1
    assert (response["chats"][0]["message_id"]) == 12345


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        (
            {
                ATTR_MESSAGE: "test_message",
                ATTR_PARSER: PARSER_PLAIN_TEXT,
                ATTR_KEYBOARD_INLINE: "command1:/cmd1,/cmd2,mock_link:https://mock_link",
            },
            InlineKeyboardMarkup(
                # 1 row with 3 buttons
                [
                    [
                        InlineKeyboardButton(callback_data="/cmd1", text="command1"),
                        InlineKeyboardButton(callback_data="/cmd2", text="CMD2"),
                        InlineKeyboardButton(url="https://mock_link", text="mock_link"),
                    ]
                ]
            ),
        ),
        (
            {
                ATTR_MESSAGE: "test_message",
                ATTR_PARSER: PARSER_PLAIN_TEXT,
                ATTR_KEYBOARD_INLINE: [
                    [["command1", "/cmd1"]],
                    [["mock_link", "https://mock_link"]],
                ],
            },
            InlineKeyboardMarkup(
                # 2 rows each with 1 button
                [
                    [InlineKeyboardButton(callback_data="/cmd1", text="command1")],
                    [InlineKeyboardButton(url="https://mock_link", text="mock_link")],
                ]
            ),
        ),
    ],
)
async def test_send_message_with_inline_keyboard(
    hass: HomeAssistant,
    webhook_platform,
    input: dict[str, Any],
    expected: InlineKeyboardMarkup,
) -> None:
    """Test the send_message service.

    Tests any service that does not require files to be sent.
    """
    context = Context()
    events = async_capture_events(hass, "telegram_sent")

    with patch(
        "homeassistant.components.telegram_bot.bot.Bot.send_message",
        AsyncMock(
            return_value=Message(
                message_id=12345,
                date=datetime.now(),
                chat=Chat(id=123456, type=ChatType.PRIVATE),
            )
        ),
    ) as mock_send_message:
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            input,
            blocking=True,
            context=context,
            return_response=True,
        )
        await hass.async_block_till_done()

        mock_send_message.assert_called_once_with(
            12345678,
            "test_message",
            parse_mode=None,
            disable_web_page_preview=None,
            disable_notification=False,
            reply_to_message_id=None,
            reply_markup=expected,
            read_timeout=None,
            message_thread_id=None,
        )

    assert len(events) == 1
    assert events[0].context == context

    assert len(response["chats"]) == 1
    assert (response["chats"][0]["message_id"]) == 12345


@patch(
    "builtins.open",
    mock_open(
        read_data=base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAApgAAAKYB3X3/OAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAANCSURBVEiJtZZPbBtFFMZ/M7ubXdtdb1xSFyeilBapySVU8h8OoFaooFSqiihIVIpQBKci6KEg9Q6H9kovIHoCIVQJJCKE1ENFjnAgcaSGC6rEnxBwA04Tx43t2FnvDAfjkNibxgHxnWb2e/u992bee7tCa00YFsffekFY+nUzFtjW0LrvjRXrCDIAaPLlW0nHL0SsZtVoaF98mLrx3pdhOqLtYPHChahZcYYO7KvPFxvRl5XPp1sN3adWiD1ZAqD6XYK1b/dvE5IWryTt2udLFedwc1+9kLp+vbbpoDh+6TklxBeAi9TL0taeWpdmZzQDry0AcO+jQ12RyohqqoYoo8RDwJrU+qXkjWtfi8Xxt58BdQuwQs9qC/afLwCw8tnQbqYAPsgxE1S6F3EAIXux2oQFKm0ihMsOF71dHYx+f3NND68ghCu1YIoePPQN1pGRABkJ6Bus96CutRZMydTl+TvuiRW1m3n0eDl0vRPcEysqdXn+jsQPsrHMquGeXEaY4Yk4wxWcY5V/9scqOMOVUFthatyTy8QyqwZ+kDURKoMWxNKr2EeqVKcTNOajqKoBgOE28U4tdQl5p5bwCw7BWquaZSzAPlwjlithJtp3pTImSqQRrb2Z8PHGigD4RZuNX6JYj6wj7O4TFLbCO/Mn/m8R+h6rYSUb3ekokRY6f/YukArN979jcW+V/S8g0eT/N3VN3kTqWbQ428m9/8k0P/1aIhF36PccEl6EhOcAUCrXKZXXWS3XKd2vc/TRBG9O5ELC17MmWubD2nKhUKZa26Ba2+D3P+4/MNCFwg59oWVeYhkzgN/JDR8deKBoD7Y+ljEjGZ0sosXVTvbc6RHirr2reNy1OXd6pJsQ+gqjk8VWFYmHrwBzW/n+uMPFiRwHB2I7ih8ciHFxIkd/3Omk5tCDV1t+2nNu5sxxpDFNx+huNhVT3/zMDz8usXC3ddaHBj1GHj/As08fwTS7Kt1HBTmyN29vdwAw+/wbwLVOJ3uAD1wi/dUH7Qei66PfyuRj4Ik9is+hglfbkbfR3cnZm7chlUWLdwmprtCohX4HUtlOcQjLYCu+fzGJH2QRKvP3UNz8bWk1qMxjGTOMThZ3kvgLI5AzFfo379UAAAAASUVORK5CYII="
        )
    ),
    create=True,
)
def _read_file_as_bytesio_mock(file_path):
    """Convert file to BytesIO for testing."""
    _file = None

    with open(file_path, encoding="utf8") as file_handler:
        _file = io.BytesIO(file_handler.read())

    _file.name = "dummy"
    _file.seek(0)

    return _file


async def test_send_chat_action(
    hass: HomeAssistant,
    webhook_platform,
    mock_broadcast_config_entry: MockConfigEntry,
) -> None:
    """Test the send_chat_action service."""
    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.telegram_bot.bot.Bot.send_chat_action",
        AsyncMock(return_value=True),
    ) as mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_CHAT_ACTION,
            {
                CONF_CONFIG_ENTRY_ID: mock_broadcast_config_entry.entry_id,
                ATTR_TARGET: [123456],
                ATTR_CHAT_ACTION: CHAT_ACTION_TYPING,
            },
            blocking=True,
            return_response=True,
        )

    await hass.async_block_till_done()
    mock.assert_called_once()
    mock.assert_called_with(chat_id=123456, action=CHAT_ACTION_TYPING)


@pytest.mark.parametrize(
    "service",
    [
        SERVICE_SEND_PHOTO,
        SERVICE_SEND_ANIMATION,
        SERVICE_SEND_VIDEO,
        SERVICE_SEND_VOICE,
        SERVICE_SEND_DOCUMENT,
    ],
)
async def test_send_file(hass: HomeAssistant, webhook_platform, service: str) -> None:
    """Test the send_file service (photo, animation, video, document...)."""
    context = Context()
    events = async_capture_events(hass, "telegram_sent")

    hass.config.allowlist_external_dirs.add("/media/")

    # Mock the file handler read with our base64 encoded dummy file
    with patch(
        "homeassistant.components.telegram_bot.bot._read_file_as_bytesio",
        _read_file_as_bytesio_mock,
    ):
        response = await hass.services.async_call(
            DOMAIN,
            service,
            {
                ATTR_FILE: "/media/dummy",
                ATTR_MESSAGE_THREAD_ID: "123",
            },
            blocking=True,
            context=context,
            return_response=True,
        )
        await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].context == context

    assert len(response["chats"]) == 1
    assert (response["chats"][0]["message_id"]) == 12345


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
    assert events[0].data[ATTR_MESSAGE_THREAD_ID] == 123


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
        f"{TELEGRAM_WEBHOOK_URL}_123456",
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
        f"{TELEGRAM_WEBHOOK_URL}_123456",
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
        f"{TELEGRAM_WEBHOOK_URL}_123456",
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


@pytest.mark.parametrize(
    ("attachment_type"),
    [
        ("photo"),
        ("document"),
    ],
)
async def test_webhook_endpoint_generates_telegram_attachment_event(
    hass: HomeAssistant,
    webhook_platform,
    hass_client: ClientSessionGenerator,
    mock_generate_secret_token: str,
    attachment_type: str,
) -> None:
    """POST to the configured webhook endpoint and assert fired `telegram_attachment` event for photo and document."""
    client = await hass_client()
    events = async_capture_events(hass, "telegram_attachment")
    update_message_attachment = await async_load_fixture(
        hass, f"update_message_attachment_{attachment_type}.json", DOMAIN
    )

    response = await client.post(
        f"{TELEGRAM_WEBHOOK_URL}_123456",
        data=update_message_attachment,
        headers={
            "X-Telegram-Bot-Api-Secret-Token": mock_generate_secret_token,
            "Content-Type": "application/json",
        },
    )
    assert response.status == 200
    assert (await response.read()).decode("utf-8") == ""

    # Make sure event has fired
    await hass.async_block_till_done()

    assert len(events) == 1
    loaded = json_util.json_loads(update_message_attachment)
    if attachment_type == "photo":
        expected_file_id = loaded["message"]["photo"][-1]["file_id"]
    else:
        expected_file_id = loaded["message"][attachment_type]["file_id"]

    assert events[0].data["file_id"] == expected_file_id
    assert isinstance(events[0].context, Context)


async def test_polling_platform_message_text_update(
    hass: HomeAssistant,
    config_polling,
    update_message_text,
    mock_external_calls: None,
) -> None:
    """Provide the `BaseTelegramBot.update_handler` with an `Update` and assert fired `telegram_text` event."""
    events = async_capture_events(hass, "telegram_text")

    with patch(
        "homeassistant.components.telegram_bot.polling.ApplicationBuilder"
    ) as application_builder_class:
        # Set up the integration with the polling platform inside the patch context manager.
        application = (
            application_builder_class.return_value.bot.return_value.build.return_value
        )
        application.updater.start_polling = AsyncMock()
        application.updater.stop = AsyncMock()
        application.initialize = AsyncMock()
        application.start = AsyncMock()
        application.stop = AsyncMock()
        application.shutdown = AsyncMock()

        await async_setup_component(
            hass,
            DOMAIN,
            config_polling,
        )
        await hass.async_block_till_done()

        # Then call the callback and assert events fired.
        handler = application.add_handler.call_args[0][0]
        handle_update_callback = handler.callback

        # Create Update object using library API.
        application.bot.defaults.tzinfo = None
        update = Update.de_json(update_message_text, application.bot)

        # handle_update_callback == BaseTelegramBot.update_handler
        await handle_update_callback(update, None)

    # Make sure event has fired
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["text"] == update_message_text["message"]["text"]

    config_entry = hass.config_entries.async_entry_for_domain_unique_id(
        DOMAIN, "1234567890:ABC"
    )
    assert events[0].data["bot"]["config_entry_id"] == config_entry.entry_id
    assert events[0].data["bot"]["id"] == 123456
    assert events[0].data["bot"]["first_name"] == "Testbot"
    assert events[0].data["bot"]["last_name"] == "mock last name"
    assert events[0].data["bot"]["username"] == "mock username"

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
    mock_external_calls: None,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    log_message: str,
) -> None:
    """Test polling add error handler."""
    with patch(
        "homeassistant.components.telegram_bot.polling.ApplicationBuilder"
    ) as application_builder_class:
        application = (
            application_builder_class.return_value.bot.return_value.build.return_value
        )
        application.updater.stop = AsyncMock()
        application.initialize = AsyncMock()
        application.updater.start_polling = AsyncMock()
        application.start = AsyncMock()
        application.stop = AsyncMock()
        application.shutdown = AsyncMock()
        application.bot.defaults.tzinfo = None

        await async_setup_component(
            hass,
            DOMAIN,
            config_polling,
        )
        await hass.async_block_till_done()

        update = Update.de_json(update_message_text, application.bot)
        process_error = application.add_error_handler.call_args[0][0]
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
    mock_external_calls: None,
    error: Exception,
    log_message: str,
) -> None:
    """Test polling add error handler."""
    with patch(
        "homeassistant.components.telegram_bot.polling.ApplicationBuilder"
    ) as application_builder_class:
        application = (
            application_builder_class.return_value.bot.return_value.build.return_value
        )
        application.initialize = AsyncMock()
        application.updater.start_polling = AsyncMock()
        application.start = AsyncMock()
        application.updater.stop = AsyncMock()
        application.stop = AsyncMock()
        application.shutdown = AsyncMock()

        await async_setup_component(
            hass,
            DOMAIN,
            config_polling,
        )

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
        f"{TELEGRAM_WEBHOOK_URL}_123456",
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
        f"{TELEGRAM_WEBHOOK_URL}_123456",
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
        f"{TELEGRAM_WEBHOOK_URL}_123456",
        json=update_message_text,
        headers={"X-Telegram-Bot-Api-Secret-Token": incorrect_secret_token},
    )
    assert response.status == 401


async def test_multiple_config_entries_error(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    polling_platform,
    mock_external_calls: None,
) -> None:
    """Test multiple config entries error."""

    # setup the second entry (polling_platform is first entry)
    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_MESSAGE: "mock message",
            },
            blocking=True,
            return_response=True,
        )

    await hass.async_block_till_done()
    assert err.value.translation_key == "multiple_config_entry"


async def test_send_message_with_config_entry(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test send message using config entry."""
    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    # test: send message to invalid chat id

    with pytest.raises(HomeAssistantError) as err:
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                CONF_CONFIG_ENTRY_ID: mock_broadcast_config_entry.entry_id,
                ATTR_MESSAGE: "mock message",
                ATTR_TARGET: [123456, 1],
            },
            blocking=True,
            return_response=True,
        )
    await hass.async_block_till_done()

    assert err.value.translation_key == "failed_chat_ids"
    assert err.value.translation_placeholders["chat_ids"] == "1"
    assert err.value.translation_placeholders["bot_name"] == "Mock Title"

    # test: send message to valid chat id

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            CONF_CONFIG_ENTRY_ID: mock_broadcast_config_entry.entry_id,
            ATTR_MESSAGE: "mock message",
            ATTR_TARGET: 123456,
        },
        blocking=True,
        return_response=True,
    )

    assert response["chats"][0]["message_id"] == 12345


async def test_send_message_no_chat_id_error(
    hass: HomeAssistant,
    mock_external_calls: None,
) -> None:
    """Test send message using config entry with no whitelisted chat id."""
    data = {
        CONF_PLATFORM: PLATFORM_BROADCAST,
        CONF_API_KEY: "mock api key",
        SECTION_ADVANCED_SETTINGS: {},
    }

    with patch("homeassistant.components.telegram_bot.config_flow.Bot.get_me"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=data,
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                CONF_CONFIG_ENTRY_ID: result["result"].entry_id,
                ATTR_MESSAGE: "mock message",
            },
            blocking=True,
            return_response=True,
        )

    assert err.value.translation_key == "missing_allowed_chat_ids"
    assert err.value.translation_placeholders["bot_name"] == "Testbot mock last name"


async def test_send_message_config_entry_error(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test send message config entry error."""
    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                CONF_CONFIG_ENTRY_ID: mock_broadcast_config_entry.entry_id,
                ATTR_MESSAGE: "mock message",
            },
            blocking=True,
            return_response=True,
        )

    await hass.async_block_till_done()
    assert err.value.translation_key == "missing_config_entry"


async def test_delete_message(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test delete message."""
    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    # test: delete message with invalid chat id

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_MESSAGE,
            {ATTR_CHAT_ID: 1, ATTR_MESSAGEID: "last"},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert err.value.translation_key == "invalid_chat_ids"
    assert err.value.translation_placeholders["chat_ids"] == "1"
    assert err.value.translation_placeholders["bot_name"] == "Mock Title"

    # test: delete message with valid chat id

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_MESSAGE: "mock message"},
        blocking=True,
        return_response=True,
    )
    assert response["chats"][0]["message_id"] == 12345

    with patch(
        "homeassistant.components.telegram_bot.bot.Bot.delete_message",
        AsyncMock(return_value=True),
    ) as mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_MESSAGE,
            {ATTR_CHAT_ID: 123456, ATTR_MESSAGEID: "last"},
            blocking=True,
        )

    await hass.async_block_till_done()
    mock.assert_called_once()


async def test_edit_message(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test edit message."""
    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.telegram_bot.bot.Bot.edit_message_text",
        AsyncMock(return_value=True),
    ) as mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_EDIT_MESSAGE,
            {ATTR_MESSAGE: "mock message", ATTR_CHAT_ID: 123456, ATTR_MESSAGEID: 12345},
            blocking=True,
        )

    await hass.async_block_till_done()
    mock.assert_called_once()

    with patch(
        "homeassistant.components.telegram_bot.bot.Bot.edit_message_caption",
        AsyncMock(return_value=True),
    ) as mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_EDIT_CAPTION,
            {ATTR_CAPTION: "mock caption", ATTR_CHAT_ID: 123456, ATTR_MESSAGEID: 12345},
            blocking=True,
        )

    await hass.async_block_till_done()
    mock.assert_called_once()

    with patch(
        "homeassistant.components.telegram_bot.bot.Bot.edit_message_reply_markup",
        AsyncMock(return_value=True),
    ) as mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_EDIT_REPLYMARKUP,
            {ATTR_KEYBOARD_INLINE: [], ATTR_CHAT_ID: 123456, ATTR_MESSAGEID: 12345},
            blocking=True,
        )

    await hass.async_block_till_done()
    mock.assert_called_once()


async def test_async_setup_entry_failed(
    hass: HomeAssistant, mock_broadcast_config_entry: MockConfigEntry
) -> None:
    """Test setup entry failed."""
    mock_broadcast_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.telegram_bot.Bot.get_me",
    ) as mock_bot:
        mock_bot.side_effect = InvalidToken("mock invalid token error")

        with pytest.raises(ConfigEntryAuthFailed) as err:
            await async_setup_entry(hass, mock_broadcast_config_entry)

    await hass.async_block_till_done()
    assert err.value.args[0] == "Invalid API token for Telegram Bot."


async def test_answer_callback_query(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test answer callback query."""
    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.telegram_bot.bot.Bot.answer_callback_query"
    ) as mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ANSWER_CALLBACK_QUERY,
            {
                ATTR_MESSAGE: "mock message",
                ATTR_CALLBACK_QUERY_ID: 123456,
                ATTR_SHOW_ALERT: True,
            },
            blocking=True,
        )

    await hass.async_block_till_done()
    mock.assert_called_once()
    mock.assert_called_with(
        123456,
        text="mock message",
        show_alert=True,
        read_timeout=None,
    )


async def test_leave_chat(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test answer callback query."""
    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.telegram_bot.bot.Bot.leave_chat",
        AsyncMock(return_value=True),
    ) as mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_LEAVE_CHAT,
            {
                ATTR_CHAT_ID: 123456,
            },
            blocking=True,
        )

    await hass.async_block_till_done()
    mock.assert_called_once()
    mock.assert_called_with(
        123456,
    )


async def test_send_video(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test answer callback query."""
    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    # test: invalid file path

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_VIDEO,
            {
                ATTR_FILE: "/mock/file",
            },
            blocking=True,
        )

    await hass.async_block_till_done()
    assert (
        err.value.args[0]
        == "File path has not been configured in allowlist_external_dirs."
    )

    # test: missing username input

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_VIDEO,
            {
                ATTR_URL: "https://mock",
                ATTR_AUTHENTICATION: HTTP_DIGEST_AUTHENTICATION,
                ATTR_PASSWORD: "mock password",
            },
            blocking=True,
        )

    await hass.async_block_till_done()
    assert err.value.args[0] == "Username is required."

    # test: missing password input

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_VIDEO,
            {
                ATTR_URL: "https://mock",
                ATTR_AUTHENTICATION: HTTP_BEARER_AUTHENTICATION,
            },
            blocking=True,
        )

    await hass.async_block_till_done()
    assert err.value.args[0] == "Password is required."

    # test: 404 error

    with patch(
        "homeassistant.components.telegram_bot.bot.httpx.AsyncClient.get"
    ) as mock_get:
        mock_get.return_value = AsyncMock(status_code=404, text="Success")

        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SEND_VIDEO,
                {
                    ATTR_URL: "https://mock",
                    ATTR_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
                    ATTR_USERNAME: "mock username",
                    ATTR_PASSWORD: "mock password",
                },
                blocking=True,
            )

    await hass.async_block_till_done()
    assert mock_get.call_count > 0
    assert err.value.args[0] == "Failed to load URL: 404"

    # test: invalid url

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_VIDEO,
            {
                ATTR_URL: "invalid url",
                ATTR_VERIFY_SSL: True,
                ATTR_AUTHENTICATION: HTTP_BEARER_AUTHENTICATION,
                ATTR_PASSWORD: "mock password",
            },
            blocking=True,
        )

    await hass.async_block_till_done()
    assert mock_get.call_count > 0
    assert (
        err.value.args[0]
        == "Failed to load URL: Request URL is missing an 'http://' or 'https://' protocol."
    )

    # test: no url/file input

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_VIDEO,
            {},
            blocking=True,
        )

    await hass.async_block_till_done()
    assert err.value.args[0] == "URL or File is required."

    # test: load file error (e.g. not found, permissions error)

    hass.config.allowlist_external_dirs.add("/tmp/")  # noqa: S108

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_VIDEO,
            {
                ATTR_FILE: "/tmp/not-exists",  # noqa: S108
            },
            blocking=True,
        )

    await hass.async_block_till_done()
    assert (
        err.value.args[0]
        == "Failed to load file: [Errno 2] No such file or directory: '/tmp/not-exists'"
    )

    # test: success with file
    write_utf8_file("/tmp/mock", "mock file contents")  # noqa: S108

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_VIDEO,
        {
            ATTR_FILE: "/tmp/mock",  # noqa: S108
        },
        blocking=True,
        return_response=True,
    )

    await hass.async_block_till_done()
    assert response["chats"][0]["message_id"] == 12345

    # test: success with url

    with patch(
        "homeassistant.components.telegram_bot.bot.httpx.AsyncClient.get"
    ) as mock_get:
        mock_get.return_value = AsyncMock(status_code=200, content=b"mock content")

        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_VIDEO,
            {
                ATTR_URL: "https://mock",
                ATTR_AUTHENTICATION: HTTP_DIGEST_AUTHENTICATION,
                ATTR_USERNAME: "mock username",
                ATTR_PASSWORD: "mock password",
            },
            blocking=True,
            return_response=True,
        )

    await hass.async_block_till_done()
    assert mock_get.call_count > 0
    assert response["chats"][0]["message_id"] == 12345


async def test_set_message_reaction(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test set message reaction."""
    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.telegram_bot.bot.Bot.set_message_reaction",
        AsyncMock(return_value=True),
    ) as mock:
        await hass.services.async_call(
            DOMAIN,
            "set_message_reaction",
            {
                ATTR_CHAT_ID: 123456,
                ATTR_MESSAGEID: 54321,
                "reaction": "👍",
                "is_big": True,
            },
            blocking=True,
        )

    await hass.async_block_till_done()
    mock.assert_called_once_with(
        123456,
        54321,
        reaction="👍",
        is_big=True,
        read_timeout=None,
    )
