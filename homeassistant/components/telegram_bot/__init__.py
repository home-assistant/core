"""Support to send and receive Telegram messages."""

from __future__ import annotations

from ipaddress import IPv4Network, ip_network
import logging
from types import ModuleType
from typing import Any

from telegram import Bot
from telegram.constants import InputMediaType
from telegram.error import InvalidToken, TelegramError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_API_KEY,
    CONF_PLATFORM,
    CONF_SOURCE,
    CONF_URL,
    Platform,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import broadcast, polling, webhooks
from .bot import TelegramBotConfigEntry, TelegramNotificationService, initialize_bot
from .const import (
    ATTR_ALLOWS_MULTIPLE_ANSWERS,
    ATTR_AUTHENTICATION,
    ATTR_CALLBACK_QUERY_ID,
    ATTR_CAPTION,
    ATTR_CHAT_ACTION,
    ATTR_CHAT_ID,
    ATTR_DISABLE_NOTIF,
    ATTR_DISABLE_WEB_PREV,
    ATTR_FILE,
    ATTR_IS_ANONYMOUS,
    ATTR_IS_BIG,
    ATTR_KEYBOARD,
    ATTR_KEYBOARD_INLINE,
    ATTR_MEDIA_TYPE,
    ATTR_MESSAGE,
    ATTR_MESSAGE_TAG,
    ATTR_MESSAGE_THREAD_ID,
    ATTR_MESSAGEID,
    ATTR_ONE_TIME_KEYBOARD,
    ATTR_OPEN_PERIOD,
    ATTR_OPTIONS,
    ATTR_PARSER,
    ATTR_PASSWORD,
    ATTR_QUESTION,
    ATTR_REACTION,
    ATTR_RESIZE_KEYBOARD,
    ATTR_SHOW_ALERT,
    ATTR_STICKER_ID,
    ATTR_TARGET,
    ATTR_TIMEOUT,
    ATTR_TITLE,
    ATTR_URL,
    ATTR_USERNAME,
    ATTR_VERIFY_SSL,
    CHAT_ACTION_CHOOSE_STICKER,
    CHAT_ACTION_FIND_LOCATION,
    CHAT_ACTION_RECORD_VIDEO,
    CHAT_ACTION_RECORD_VIDEO_NOTE,
    CHAT_ACTION_RECORD_VOICE,
    CHAT_ACTION_TYPING,
    CHAT_ACTION_UPLOAD_DOCUMENT,
    CHAT_ACTION_UPLOAD_PHOTO,
    CHAT_ACTION_UPLOAD_VIDEO,
    CHAT_ACTION_UPLOAD_VIDEO_NOTE,
    CHAT_ACTION_UPLOAD_VOICE,
    CONF_ALLOWED_CHAT_IDS,
    CONF_BOT_COUNT,
    CONF_CONFIG_ENTRY_ID,
    CONF_PROXY_URL,
    CONF_TRUSTED_NETWORKS,
    DEFAULT_TRUSTED_NETWORKS,
    DOMAIN,
    PARSER_MD,
    PLATFORM_BROADCAST,
    PLATFORM_POLLING,
    PLATFORM_WEBHOOKS,
    SERVICE_ANSWER_CALLBACK_QUERY,
    SERVICE_DELETE_MESSAGE,
    SERVICE_EDIT_CAPTION,
    SERVICE_EDIT_MESSAGE,
    SERVICE_EDIT_MESSAGE_MEDIA,
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
    SERVICE_SET_MESSAGE_REACTION,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_PLATFORM): vol.In(
                            (PLATFORM_BROADCAST, PLATFORM_POLLING, PLATFORM_WEBHOOKS)
                        ),
                        vol.Required(CONF_API_KEY): cv.string,
                        vol.Required(CONF_ALLOWED_CHAT_IDS): vol.All(
                            cv.ensure_list, [vol.Coerce(int)]
                        ),
                        vol.Optional(ATTR_PARSER, default=PARSER_MD): cv.string,
                        vol.Optional(CONF_PROXY_URL): cv.string,
                        # webhooks
                        vol.Optional(CONF_URL): cv.url,
                        vol.Optional(
                            CONF_TRUSTED_NETWORKS, default=DEFAULT_TRUSTED_NETWORKS
                        ): vol.All(cv.ensure_list, [ip_network]),
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)

BASE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_TARGET): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(ATTR_PARSER): cv.string,
        vol.Optional(ATTR_DISABLE_NOTIF): cv.boolean,
        vol.Optional(ATTR_DISABLE_WEB_PREV): cv.boolean,
        vol.Optional(ATTR_RESIZE_KEYBOARD): cv.boolean,
        vol.Optional(ATTR_ONE_TIME_KEYBOARD): cv.boolean,
        vol.Optional(ATTR_KEYBOARD): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_KEYBOARD_INLINE): cv.ensure_list,
        vol.Optional(ATTR_TIMEOUT): cv.positive_int,
        vol.Optional(ATTR_MESSAGE_TAG): cv.string,
        vol.Optional(ATTR_MESSAGE_THREAD_ID): vol.Coerce(int),
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA_SEND_MESSAGE = BASE_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_MESSAGE): cv.string, vol.Optional(ATTR_TITLE): cv.string}
)

SERVICE_SCHEMA_SEND_CHAT_ACTION = BASE_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_CHAT_ACTION): vol.In(
            (
                CHAT_ACTION_TYPING,
                CHAT_ACTION_UPLOAD_PHOTO,
                CHAT_ACTION_RECORD_VIDEO,
                CHAT_ACTION_UPLOAD_VIDEO,
                CHAT_ACTION_RECORD_VOICE,
                CHAT_ACTION_UPLOAD_VOICE,
                CHAT_ACTION_UPLOAD_DOCUMENT,
                CHAT_ACTION_CHOOSE_STICKER,
                CHAT_ACTION_FIND_LOCATION,
                CHAT_ACTION_RECORD_VIDEO_NOTE,
                CHAT_ACTION_UPLOAD_VIDEO_NOTE,
            )
        ),
    }
)

SERVICE_SCHEMA_SEND_FILE = BASE_SERVICE_SCHEMA.extend(
    {
        vol.Optional(ATTR_URL): cv.string,
        vol.Optional(ATTR_FILE): cv.string,
        vol.Optional(ATTR_CAPTION): cv.string,
        vol.Optional(ATTR_USERNAME): cv.string,
        vol.Optional(ATTR_PASSWORD): cv.string,
        vol.Optional(ATTR_AUTHENTICATION): cv.string,
        vol.Optional(ATTR_VERIFY_SSL): cv.boolean,
    }
)

SERVICE_SCHEMA_SEND_STICKER = SERVICE_SCHEMA_SEND_FILE.extend(
    {vol.Optional(ATTR_STICKER_ID): cv.string}
)

SERVICE_SCHEMA_SEND_LOCATION = BASE_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_LONGITUDE): cv.string,
        vol.Required(ATTR_LATITUDE): cv.string,
    }
)

SERVICE_SCHEMA_SEND_POLL = vol.Schema(
    {
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_TARGET): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Required(ATTR_QUESTION): cv.string,
        vol.Required(ATTR_OPTIONS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_OPEN_PERIOD): cv.positive_int,
        vol.Optional(ATTR_IS_ANONYMOUS, default=True): cv.boolean,
        vol.Optional(ATTR_ALLOWS_MULTIPLE_ANSWERS, default=False): cv.boolean,
        vol.Optional(ATTR_DISABLE_NOTIF): cv.boolean,
        vol.Optional(ATTR_TIMEOUT): cv.positive_int,
        vol.Optional(ATTR_MESSAGE_THREAD_ID): vol.Coerce(int),
    }
)

SERVICE_SCHEMA_EDIT_MESSAGE = SERVICE_SCHEMA_SEND_MESSAGE.extend(
    {
        vol.Required(ATTR_MESSAGEID): vol.Any(
            cv.positive_int, vol.All(cv.string, "last")
        ),
        vol.Required(ATTR_CHAT_ID): vol.Coerce(int),
    }
)

SERVICE_SCHEMA_EDIT_MESSAGE_MEDIA = vol.Schema(
    {
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_MESSAGEID): vol.Any(
            cv.positive_int, vol.All(cv.string, "last")
        ),
        vol.Required(ATTR_CHAT_ID): vol.Coerce(int),
        vol.Optional(ATTR_TIMEOUT): cv.positive_int,
        vol.Optional(ATTR_CAPTION): cv.string,
        vol.Required(ATTR_MEDIA_TYPE): vol.In(
            (
                str(InputMediaType.ANIMATION),
                str(InputMediaType.AUDIO),
                str(InputMediaType.VIDEO),
                str(InputMediaType.DOCUMENT),
                str(InputMediaType.PHOTO),
            )
        ),
        vol.Optional(ATTR_URL): cv.string,
        vol.Optional(ATTR_FILE): cv.string,
        vol.Optional(ATTR_USERNAME): cv.string,
        vol.Optional(ATTR_PASSWORD): cv.string,
        vol.Optional(ATTR_AUTHENTICATION): cv.string,
        vol.Optional(ATTR_VERIFY_SSL): cv.boolean,
        vol.Optional(ATTR_KEYBOARD_INLINE): cv.ensure_list,
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA_EDIT_CAPTION = vol.Schema(
    {
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_MESSAGEID): vol.Any(
            cv.positive_int, vol.All(cv.string, "last")
        ),
        vol.Required(ATTR_CHAT_ID): vol.Coerce(int),
        vol.Required(ATTR_CAPTION): cv.string,
        vol.Optional(ATTR_KEYBOARD_INLINE): cv.ensure_list,
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA_EDIT_REPLYMARKUP = vol.Schema(
    {
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_MESSAGEID): vol.Any(
            cv.positive_int, vol.All(cv.string, "last")
        ),
        vol.Required(ATTR_CHAT_ID): vol.Coerce(int),
        vol.Required(ATTR_KEYBOARD_INLINE): cv.ensure_list,
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA_ANSWER_CALLBACK_QUERY = vol.Schema(
    {
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Required(ATTR_CALLBACK_QUERY_ID): vol.Coerce(int),
        vol.Optional(ATTR_SHOW_ALERT): cv.boolean,
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA_DELETE_MESSAGE = vol.Schema(
    {
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_CHAT_ID): vol.Coerce(int),
        vol.Required(ATTR_MESSAGEID): vol.Any(
            cv.positive_int, vol.All(cv.string, "last")
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA_LEAVE_CHAT = vol.Schema(
    {
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_CHAT_ID): vol.Coerce(int),
    }
)

SERVICE_SCHEMA_SET_MESSAGE_REACTION = vol.Schema(
    {
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_MESSAGEID): vol.Any(
            cv.positive_int, vol.All(cv.string, "last")
        ),
        vol.Required(ATTR_CHAT_ID): vol.Coerce(int),
        vol.Required(ATTR_REACTION): cv.string,
        vol.Optional(ATTR_IS_BIG, default=False): cv.boolean,
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_MAP = {
    SERVICE_SEND_MESSAGE: SERVICE_SCHEMA_SEND_MESSAGE,
    SERVICE_SEND_CHAT_ACTION: SERVICE_SCHEMA_SEND_CHAT_ACTION,
    SERVICE_SEND_PHOTO: SERVICE_SCHEMA_SEND_FILE,
    SERVICE_SEND_STICKER: SERVICE_SCHEMA_SEND_STICKER,
    SERVICE_SEND_ANIMATION: SERVICE_SCHEMA_SEND_FILE,
    SERVICE_SEND_VIDEO: SERVICE_SCHEMA_SEND_FILE,
    SERVICE_SEND_VOICE: SERVICE_SCHEMA_SEND_FILE,
    SERVICE_SEND_DOCUMENT: SERVICE_SCHEMA_SEND_FILE,
    SERVICE_SEND_LOCATION: SERVICE_SCHEMA_SEND_LOCATION,
    SERVICE_SEND_POLL: SERVICE_SCHEMA_SEND_POLL,
    SERVICE_EDIT_MESSAGE: SERVICE_SCHEMA_EDIT_MESSAGE,
    SERVICE_EDIT_MESSAGE_MEDIA: SERVICE_SCHEMA_EDIT_MESSAGE_MEDIA,
    SERVICE_EDIT_CAPTION: SERVICE_SCHEMA_EDIT_CAPTION,
    SERVICE_EDIT_REPLYMARKUP: SERVICE_SCHEMA_EDIT_REPLYMARKUP,
    SERVICE_ANSWER_CALLBACK_QUERY: SERVICE_SCHEMA_ANSWER_CALLBACK_QUERY,
    SERVICE_DELETE_MESSAGE: SERVICE_SCHEMA_DELETE_MESSAGE,
    SERVICE_LEAVE_CHAT: SERVICE_SCHEMA_LEAVE_CHAT,
    SERVICE_SET_MESSAGE_REACTION: SERVICE_SCHEMA_SET_MESSAGE_REACTION,
}


MODULES: dict[str, ModuleType] = {
    PLATFORM_BROADCAST: broadcast,
    PLATFORM_POLLING: polling,
    PLATFORM_WEBHOOKS: webhooks,
}

PLATFORMS: list[Platform] = [Platform.EVENT, Platform.NOTIFY]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Telegram bot component."""

    # import the last YAML config since existing behavior only works with the last config
    domain_config: list[dict[str, Any]] | None = config.get(DOMAIN)
    if domain_config:
        trusted_networks: list[IPv4Network] = domain_config[-1].get(
            CONF_TRUSTED_NETWORKS, []
        )
        trusted_networks_str: list[str] = (
            [str(trusted_network) for trusted_network in trusted_networks]
            if trusted_networks
            else []
        )
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={CONF_SOURCE: SOURCE_IMPORT},
                data={
                    CONF_PLATFORM: domain_config[-1][CONF_PLATFORM],
                    CONF_API_KEY: domain_config[-1][CONF_API_KEY],
                    CONF_ALLOWED_CHAT_IDS: domain_config[-1][CONF_ALLOWED_CHAT_IDS],
                    ATTR_PARSER: domain_config[-1][ATTR_PARSER],
                    CONF_PROXY_URL: domain_config[-1].get(CONF_PROXY_URL),
                    CONF_URL: domain_config[-1].get(CONF_URL),
                    CONF_TRUSTED_NETWORKS: trusted_networks_str,
                    CONF_BOT_COUNT: len(domain_config),
                },
            )
        )

    async def async_send_telegram_message(service: ServiceCall) -> ServiceResponse:
        """Handle sending Telegram Bot message service calls."""

        msgtype = service.service
        kwargs = dict(service.data)
        _LOGGER.debug("New telegram message %s: %s", msgtype, kwargs)

        config_entry_id: str | None = service.data.get(CONF_CONFIG_ENTRY_ID)
        config_entry: TelegramBotConfigEntry | None = None
        if config_entry_id:
            config_entry = hass.config_entries.async_get_known_entry(config_entry_id)

        else:
            config_entries: list[TelegramBotConfigEntry] = (
                service.hass.config_entries.async_entries(DOMAIN)
            )

            if len(config_entries) == 1:
                config_entry = config_entries[0]

            if len(config_entries) > 1:
                raise ServiceValidationError(
                    "Multiple config entries found. Please specify the Telegram bot to use.",
                    translation_domain=DOMAIN,
                    translation_key="multiple_config_entry",
                )

        if not config_entry or not hasattr(config_entry, "runtime_data"):
            raise ServiceValidationError(
                "No config entries found or setup failed. Please set up the Telegram Bot first.",
                translation_domain=DOMAIN,
                translation_key="missing_config_entry",
            )

        notify_service = config_entry.runtime_data

        messages = None
        if msgtype == SERVICE_SEND_MESSAGE:
            messages = await notify_service.send_message(
                context=service.context, **kwargs
            )
        elif msgtype == SERVICE_SEND_CHAT_ACTION:
            messages = await notify_service.send_chat_action(
                context=service.context, **kwargs
            )
        elif msgtype in [
            SERVICE_SEND_PHOTO,
            SERVICE_SEND_ANIMATION,
            SERVICE_SEND_VIDEO,
            SERVICE_SEND_VOICE,
            SERVICE_SEND_DOCUMENT,
        ]:
            messages = await notify_service.send_file(
                msgtype, context=service.context, **kwargs
            )
        elif msgtype == SERVICE_SEND_STICKER:
            messages = await notify_service.send_sticker(
                context=service.context, **kwargs
            )
        elif msgtype == SERVICE_SEND_LOCATION:
            messages = await notify_service.send_location(
                context=service.context, **kwargs
            )
        elif msgtype == SERVICE_SEND_POLL:
            messages = await notify_service.send_poll(context=service.context, **kwargs)
        elif msgtype == SERVICE_ANSWER_CALLBACK_QUERY:
            await notify_service.answer_callback_query(
                context=service.context, **kwargs
            )
        elif msgtype == SERVICE_DELETE_MESSAGE:
            await notify_service.delete_message(context=service.context, **kwargs)
        elif msgtype == SERVICE_LEAVE_CHAT:
            await notify_service.leave_chat(context=service.context, **kwargs)
        elif msgtype == SERVICE_SET_MESSAGE_REACTION:
            await notify_service.set_message_reaction(context=service.context, **kwargs)
        elif msgtype == SERVICE_EDIT_MESSAGE_MEDIA:
            await notify_service.edit_message_media(context=service.context, **kwargs)
        else:
            await notify_service.edit_message(
                msgtype, context=service.context, **kwargs
            )

        if service.return_response and messages is not None:
            target: list[int] | None = service.data.get(ATTR_TARGET)
            if not target:
                target = notify_service.get_target_chat_ids(None)

            failed_chat_ids = [chat_id for chat_id in target if chat_id not in messages]
            if failed_chat_ids:
                raise HomeAssistantError(
                    f"Failed targets: {failed_chat_ids}",
                    translation_domain=DOMAIN,
                    translation_key="failed_chat_ids",
                    translation_placeholders={
                        "chat_ids": ", ".join([str(i) for i in failed_chat_ids]),
                        "bot_name": config_entry.title,
                    },
                )

            return {
                "chats": [
                    {"chat_id": cid, "message_id": mid} for cid, mid in messages.items()
                ]
            }

        return None

    # Register notification services
    for service_notif, schema in SERVICE_MAP.items():
        supports_response = SupportsResponse.NONE

        if service_notif in [
            SERVICE_SEND_MESSAGE,
            SERVICE_SEND_CHAT_ACTION,
            SERVICE_SEND_PHOTO,
            SERVICE_SEND_ANIMATION,
            SERVICE_SEND_VIDEO,
            SERVICE_SEND_VOICE,
            SERVICE_SEND_DOCUMENT,
            SERVICE_SEND_STICKER,
            SERVICE_SEND_LOCATION,
            SERVICE_SEND_POLL,
        ]:
            supports_response = SupportsResponse.OPTIONAL

        hass.services.async_register(
            DOMAIN,
            service_notif,
            async_send_telegram_message,
            schema=schema,
            supports_response=supports_response,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: TelegramBotConfigEntry) -> bool:
    """Create the Telegram bot from config entry."""
    bot: Bot = await hass.async_add_executor_job(initialize_bot, hass, entry.data)
    try:
        await bot.get_me()
    except InvalidToken as err:
        raise ConfigEntryAuthFailed("Invalid API token for Telegram Bot.") from err
    except TelegramError as err:
        raise ConfigEntryNotReady from err

    p_type: str = entry.data[CONF_PLATFORM]

    _LOGGER.debug("Setting up %s.%s", DOMAIN, p_type)
    try:
        receiver_service = await MODULES[p_type].async_setup_platform(hass, bot, entry)
    except Exception:
        _LOGGER.exception("Error setting up Telegram bot %s", p_type)
        await bot.shutdown()
        return False

    notify_service = TelegramNotificationService(
        hass, receiver_service, bot, entry, entry.options[ATTR_PARSER]
    )
    entry.runtime_data = notify_service

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: TelegramBotConfigEntry) -> None:
    """Handle config changes."""
    entry.runtime_data.parse_mode = entry.options[ATTR_PARSER]

    # reload entities
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: TelegramBotConfigEntry
) -> bool:
    """Unload Telegram app."""
    # broadcast platform has no app
    if entry.runtime_data.app:
        await entry.runtime_data.app.shutdown()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
