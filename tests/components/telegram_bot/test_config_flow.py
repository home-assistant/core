"""Config flow tests for the Telegram Bot integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from telegram import User
from telegram.error import BadRequest, InvalidToken, NetworkError

from homeassistant.components.telegram_bot.bot import TelegramNotificationService
from homeassistant.components.telegram_bot.config_flow import DESCRIPTION_PLACEHOLDERS
from homeassistant.components.telegram_bot.const import (
    ATTR_PARSER,
    CONF_API_ENDPOINT,
    CONF_CHAT_ID,
    CONF_PROXY_URL,
    CONF_TRUSTED_NETWORKS,
    DEFAULT_API_ENDPOINT,
    DOMAIN,
    PARSER_MD,
    PARSER_PLAIN_TEXT,
    PLATFORM_BROADCAST,
    PLATFORM_WEBHOOKS,
    SECTION_ADVANCED_SETTINGS,
    SUBENTRY_TYPE_ALLOWED_CHAT_IDS,
)
from homeassistant.components.telegram_bot.webhooks import TELEGRAM_WEBHOOK_URL
from homeassistant.config_entries import SOURCE_USER, ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_PLATFORM, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, pytest
from tests.typing import ClientSessionGenerator


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.telegram_bot.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_options_flow(
    hass: HomeAssistant, mock_webhooks_config_entry: MockConfigEntry
) -> None:
    """Test options flow."""

    mock_webhooks_config_entry.add_to_hass(hass)

    # test: no input

    result = await hass.config_entries.options.async_init(
        mock_webhooks_config_entry.entry_id
    )
    await hass.async_block_till_done()

    assert result["step_id"] == "init"
    assert result["type"] is FlowResultType.FORM

    # test: valid input

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            ATTR_PARSER: PARSER_PLAIN_TEXT,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][ATTR_PARSER] == PARSER_PLAIN_TEXT


async def test_reconfigure_flow_broadcast(
    hass: HomeAssistant,
    mock_webhooks_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test reconfigure flow for broadcast bot."""
    mock_webhooks_config_entry.add_to_hass(hass)

    result = await mock_webhooks_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    # test: invalid proxy url

    with patch(
        "homeassistant.components.telegram_bot.config_flow.Bot.get_me",
    ) as mock_bot:
        mock_bot.side_effect = NetworkError("mock invalid proxy")

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PLATFORM: PLATFORM_BROADCAST,
                SECTION_ADVANCED_SETTINGS: {
                    CONF_PROXY_URL: "invalid",
                },
            },
        )
        await hass.async_block_till_done()

    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_proxy_url"

    # test: valid

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PLATFORM: PLATFORM_BROADCAST,
            SECTION_ADVANCED_SETTINGS: {
                CONF_PROXY_URL: "https://test",
            },
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_webhooks_config_entry.data[CONF_PLATFORM] == PLATFORM_BROADCAST
    assert mock_webhooks_config_entry.data[CONF_PROXY_URL] == "https://test"

    service: TelegramNotificationService = mock_webhooks_config_entry.runtime_data
    assert (
        service.bot._request[0]._client_kwargs["proxy"].url == "https://test"
    )  # get updates request
    assert (
        service.bot._request[1]._client_kwargs["proxy"].url == "https://test"
    )  # all other requests


async def test_reconfigure_flow_webhooks(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test reconfigure flow for webhook."""
    mock_broadcast_config_entry.add_to_hass(hass)

    result = await mock_broadcast_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PLATFORM: PLATFORM_WEBHOOKS,
            SECTION_ADVANCED_SETTINGS: {
                CONF_API_ENDPOINT: DEFAULT_API_ENDPOINT,
                CONF_PROXY_URL: "https://test",
            },
        },
    )
    await hass.async_block_till_done()

    assert result["step_id"] == "webhooks"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    # test: invalid url

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "http://test",
            CONF_TRUSTED_NETWORKS: "149.154.160.0/20,91.108.4.0/22",
        },
    )

    assert result["step_id"] == "webhooks"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_url"

    # test: HA external url not configured

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRUSTED_NETWORKS: "149.154.160.0/20,91.108.4.0/22"},
    )

    assert result["step_id"] == "webhooks"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "no_url_available"

    # test: invalid trusted networks

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://reconfigure",
            CONF_TRUSTED_NETWORKS: "invalid trusted networks",
        },
    )

    assert result["step_id"] == "webhooks"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_trusted_networks"

    # test: valid input

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://reconfigure",
            CONF_TRUSTED_NETWORKS: "149.154.160.0/20",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_broadcast_config_entry.data[CONF_URL] == "https://reconfigure"
    assert mock_broadcast_config_entry.data[CONF_API_ENDPOINT] == DEFAULT_API_ENDPOINT
    assert mock_broadcast_config_entry.data[CONF_TRUSTED_NETWORKS] == [
        "149.154.160.0/20"
    ]


@pytest.mark.parametrize(
    ("side_effect", "expected_error", "expected_description_placeholders"),
    [
        # test case 1: logout fails with network error, then succeeds
        pytest.param(
            [NetworkError("mock network error"), True],
            "telegram_error",
            {**DESCRIPTION_PLACEHOLDERS, "error_message": "mock network error"},
        ),
        # test case 2: logout fails with unsuccessful response, then succeeds
        pytest.param(
            [False, True],
            "bot_logout_failed",
            DESCRIPTION_PLACEHOLDERS,
        ),
    ],
)
async def test_reconfigure_flow_logout_failed(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
    side_effect: list,
    expected_error: str,
    expected_description_placeholders: dict[str, str],
) -> None:
    """Test reconfigure flow for with change in API endpoint and logout failed."""

    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_broadcast_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.telegram_bot.bot.Bot.log_out",
        AsyncMock(side_effect=side_effect),
    ):
        # first logout attempt fails

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PLATFORM: PLATFORM_BROADCAST,
                SECTION_ADVANCED_SETTINGS: {
                    CONF_API_ENDPOINT: "http://mock1",
                },
            },
        )
        await hass.async_block_till_done()

        assert result["step_id"] == "reconfigure"
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": expected_error}
        assert result["description_placeholders"] == expected_description_placeholders

        # second logout attempt success

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PLATFORM: PLATFORM_BROADCAST,
                SECTION_ADVANCED_SETTINGS: {
                    CONF_API_ENDPOINT: "http://mock2",
                },
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_broadcast_config_entry.data[CONF_API_ENDPOINT] == "http://mock2"


async def test_create_entry(
    hass: HomeAssistant,
    mock_register_webhook: None,
    mock_external_calls: None,
    mock_generate_secret_token: str,
) -> None:
    """Test user flow."""

    # test: no input

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    # test: invalid proxy url

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PLATFORM: PLATFORM_WEBHOOKS,
            CONF_API_KEY: "mock api key",
            SECTION_ADVANCED_SETTINGS: {
                CONF_PROXY_URL: "invalid",
            },
        },
    )
    await hass.async_block_till_done()

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_proxy_url"
    assert result["description_placeholders"]["error_field"] == "proxy url"

    # test: telegram error

    with patch(
        "homeassistant.components.telegram_bot.bot.Bot.get_me",
        side_effect=NetworkError("mock network error"),
    ) as mock_get_me:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PLATFORM: PLATFORM_WEBHOOKS,
                CONF_API_KEY: "mock api key",
                SECTION_ADVANCED_SETTINGS: {
                    CONF_PROXY_URL: "https://proxy",
                },
            },
        )
        await hass.async_block_till_done()

    mock_get_me.assert_called_once()
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "telegram_error"
    assert result["description_placeholders"]["error_message"] == "mock network error"

    # test: valid input, to continue with webhooks step

    with patch(
        "homeassistant.components.telegram_bot.config_flow.Bot.get_me",
        return_value=User(123456, "Testbot", True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PLATFORM: PLATFORM_WEBHOOKS,
                CONF_API_KEY: "mock api key",
                SECTION_ADVANCED_SETTINGS: {
                    CONF_PROXY_URL: "https://proxy",
                },
            },
        )
        await hass.async_block_till_done()

    assert result["step_id"] == "webhooks"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    # test: valid input for webhooks

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://test",
            CONF_TRUSTED_NETWORKS: "149.154.160.0/20",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Testbot mock last name"
    assert result["data"][CONF_PLATFORM] == PLATFORM_WEBHOOKS
    assert result["data"][CONF_API_KEY] == "mock api key"
    assert result["data"][CONF_PROXY_URL] == "https://proxy"
    assert result["data"][CONF_URL] == "https://test"
    assert result["data"][CONF_TRUSTED_NETWORKS] == ["149.154.160.0/20"]


@pytest.mark.parametrize(
    ("api_endpoint", "webhook_url"),
    [
        (
            DEFAULT_API_ENDPOINT,
            "https://mock_webhook",
        ),
        (
            "http://mock_api_endpoint",
            "https://mock_webhook",
        ),
        (
            "http://mock_api_endpoint",
            "http://mock_webhook",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_create_webhook_entry(
    hass: HomeAssistant, api_endpoint: str, webhook_url: str
) -> None:
    """Test user flow that creates a webhook bot."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.telegram_bot.config_flow.Bot.get_me",
        return_value=User(123456, "Testbot", True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PLATFORM: PLATFORM_WEBHOOKS,
                CONF_API_KEY: "mock api key",
                SECTION_ADVANCED_SETTINGS: {
                    CONF_API_ENDPOINT: api_endpoint,
                },
            },
        )
        await hass.async_block_till_done()

    assert result["step_id"] == "webhooks"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: webhook_url,
            CONF_TRUSTED_NETWORKS: "149.154.160.0/20",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Testbot"
    assert result["data"][CONF_PLATFORM] == PLATFORM_WEBHOOKS
    assert result["data"][CONF_API_KEY] == "mock api key"
    assert result["data"][CONF_API_ENDPOINT] == api_endpoint
    assert result["data"][CONF_URL] == webhook_url
    assert result["data"][CONF_TRUSTED_NETWORKS] == ["149.154.160.0/20"]


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

    # test: reauth invalid api key

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

    # test: valid

    with (
        patch(
            "homeassistant.components.telegram_bot.config_flow.Bot.get_me",
            return_value=User(123456, "Testbot", True),
        ),
        patch(
            "homeassistant.components.telegram_bot.webhooks.PushBot",
        ) as mock_pushbot,
    ):
        mock_pushbot.return_value.start_application = AsyncMock()
        mock_pushbot.return_value.register_webhook = AsyncMock()
        mock_pushbot.return_value.shutdown = AsyncMock()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "new mock api key"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_webhooks_config_entry.data[CONF_API_KEY] == "new mock api key"


async def test_subentry_flow(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test subentry flow."""
    mock_broadcast_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_broadcast_config_entry.entry_id, SUBENTRY_TYPE_ALLOWED_CHAT_IDS),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"] == {
        **DESCRIPTION_PLACEHOLDERS,
        "bot_username": "@mock_bot",
        "bot_url": "https://t.me/mock_bot",
        "most_recent_chat": "mock first_name (123456)",
    }

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_CHAT_ID: 987654321},
    )
    await hass.async_block_till_done()

    subentry_id = list(mock_broadcast_config_entry.subentries)[-1]
    subentry: ConfigSubentry = mock_broadcast_config_entry.subentries[subentry_id]

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert subentry.subentry_type == SUBENTRY_TYPE_ALLOWED_CHAT_IDS
    assert subentry.title == "mock title"
    assert subentry.unique_id == "987654321"
    assert subentry.data == {CONF_CHAT_ID: 987654321}


async def test_subentry_flow_config_not_ready(
    hass: HomeAssistant, mock_broadcast_config_entry: MockConfigEntry
) -> None:
    """Test subentry flow where config entry is not loaded."""
    mock_broadcast_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_broadcast_config_entry.entry_id, SUBENTRY_TYPE_ALLOWED_CHAT_IDS),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"
    assert result["description_placeholders"] == {"telegram_bot": "Mock Title"}


async def test_subentry_flow_chat_error(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test subentry flow."""
    mock_broadcast_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_broadcast_config_entry.entry_id, SUBENTRY_TYPE_ALLOWED_CHAT_IDS),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # test: network error

    with patch("homeassistant.components.telegram_bot.bot.Bot.get_chat") as mock_bot:
        mock_bot.side_effect = NetworkError("mock network error")

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={CONF_CHAT_ID: 1234567890},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "telegram_error"
    assert result["description_placeholders"]["error_message"] == "mock network error"

    # test: chat not found

    with patch("homeassistant.components.telegram_bot.bot.Bot.get_chat") as mock_bot:
        mock_bot.side_effect = BadRequest("mock chat not found")

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={CONF_CHAT_ID: 1234567890},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "chat_not_found"

    # test: chat id already configured

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={CONF_CHAT_ID: 123456},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_subentry_flow_webhook_with_update(
    hass: HomeAssistant,
    webhook_bot,
    hass_client: ClientSessionGenerator,
    update_message_text,
    mock_generate_secret_token,
) -> None:
    """Test subentry flow with webhook bot."""

    # send a message to the webhook to create a recent chat
    client = await hass_client()
    response = await client.post(
        f"{TELEGRAM_WEBHOOK_URL}_123456",
        json=update_message_text,
        headers={"X-Telegram-Bot-Api-Secret-Token": mock_generate_secret_token},
    )
    assert response.status == 200

    # start the subentry flow
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_ALLOWED_CHAT_IDS),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"] == {
        **DESCRIPTION_PLACEHOLDERS,
        "bot_username": "@mock_bot",
        "bot_url": "https://t.me/mock_bot",
        "most_recent_chat": "mock title (1111111)",
    }


async def test_subentry_flow_polling_bot_without_update(
    hass: HomeAssistant,
    mock_polling_config_entry: MockConfigEntry,
    mock_external_calls: None,
    mock_polling_calls: None,
) -> None:
    """Test subentry flow with polling bot."""

    mock_polling_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_polling_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_polling_config_entry.entry_id, SUBENTRY_TYPE_ALLOWED_CHAT_IDS),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"] == {
        **DESCRIPTION_PLACEHOLDERS,
        "bot_username": "@mock_bot",
        "bot_url": "https://t.me/mock_bot",
        "most_recent_chat": "Not available",
    }


async def test_subentry_flow_broadcast_without_update(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test subentry flow where broadcast bot did not receive any messages."""

    mock_broadcast_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.telegram_bot.bot.Bot.get_updates", return_value=()
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_broadcast_config_entry.entry_id, SUBENTRY_TYPE_ALLOWED_CHAT_IDS),
            context={"source": SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"] == {
        **DESCRIPTION_PLACEHOLDERS,
        "bot_username": "@mock_bot",
        "bot_url": "https://t.me/mock_bot",
        "most_recent_chat": "Not available",
    }


async def test_subentry_flow_broadcast_update_error(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
) -> None:
    """Test subentry flow where broadcast bot encounter error while receiving messages."""

    mock_broadcast_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.telegram_bot.bot.Bot.get_updates",
        side_effect=NetworkError("mock network error"),
    ):
        result = await hass.config_entries.subentries.async_init(
            (mock_broadcast_config_entry.entry_id, SUBENTRY_TYPE_ALLOWED_CHAT_IDS),
            context={"source": SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"] == {
        **DESCRIPTION_PLACEHOLDERS,
        "bot_username": "@mock_bot",
        "bot_url": "https://t.me/mock_bot",
        "most_recent_chat": "Not available",
    }


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test user flow with duplicated entries."""

    data = {
        CONF_PLATFORM: PLATFORM_BROADCAST,
        CONF_API_KEY: "mock api key",
        SECTION_ADVANCED_SETTINGS: {
            CONF_API_ENDPOINT: "http://mock_api_endpoint",
        },
    }

    with patch(
        "homeassistant.components.telegram_bot.config_flow.Bot.get_me",
        return_value=User(123456, "Testbot", True),
    ):
        # test: import first entry success

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=data,
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_PLATFORM] == PLATFORM_BROADCAST
        assert result["data"][CONF_API_KEY] == "mock api key"
        assert result["data"][CONF_API_ENDPOINT] == "http://mock_api_endpoint"
        assert result["options"][ATTR_PARSER] == PARSER_MD

        # test: import 2nd entry failed due to duplicate

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=data,
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
