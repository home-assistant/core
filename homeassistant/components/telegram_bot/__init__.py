"""Support to send and receive Telegram messages."""

from __future__ import annotations

import logging
from typing import Protocol, cast

from telegram import Bot
from telegram.constants import InputMediaType
from telegram.error import InvalidToken, TelegramError
import voluptuous as vol

from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_SERVICE,
    CONF_PLATFORM,
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
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)
from homeassistant.helpers.typing import ConfigType, VolSchemaType
from homeassistant.util.json import JsonValueType

from . import broadcast, polling, webhooks
from .bot import (
    BaseTelegramBot,
    TelegramBotConfigEntry,
    TelegramNotificationService,
    initialize_bot,
)
from .const import (
    ATTR_ALLOWS_MULTIPLE_ANSWERS,
    ATTR_AUTHENTICATION,
    ATTR_CALLBACK_QUERY_ID,
    ATTR_CAPTION,
    ATTR_CHAT_ACTION,
    ATTR_CHAT_ID,
    ATTR_DIRECTORY_PATH,
    ATTR_DISABLE_NOTIF,
    ATTR_DISABLE_WEB_PREV,
    ATTR_FILE,
    ATTR_FILE_ID,
    ATTR_FILE_NAME,
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
    ATTR_REPLY_TO_MSGID,
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
    CONF_API_ENDPOINT,
    CONF_CONFIG_ENTRY_ID,
    DEFAULT_API_ENDPOINT,
    DOMAIN,
    PARSER_HTML,
    PARSER_MD,
    PARSER_MD2,
    PARSER_PLAIN_TEXT,
    PLATFORM_BROADCAST,
    PLATFORM_POLLING,
    PLATFORM_WEBHOOKS,
    SERVICE_ANSWER_CALLBACK_QUERY,
    SERVICE_DELETE_MESSAGE,
    SERVICE_DOWNLOAD_FILE,
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

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ATTR_PARSER_SCHEMA = vol.All(
    cv.string,
    vol.In([PARSER_HTML, PARSER_MD, PARSER_MD2, PARSER_PLAIN_TEXT]),
)

BASE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_TARGET): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_CHAT_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(ATTR_PARSER): ATTR_PARSER_SCHEMA,
        vol.Optional(ATTR_DISABLE_NOTIF): cv.boolean,
        vol.Optional(ATTR_DISABLE_WEB_PREV): cv.boolean,
        vol.Optional(ATTR_RESIZE_KEYBOARD): cv.boolean,
        vol.Optional(ATTR_ONE_TIME_KEYBOARD): cv.boolean,
        vol.Optional(ATTR_KEYBOARD): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_KEYBOARD_INLINE): cv.ensure_list,
        vol.Optional(ATTR_TIMEOUT): cv.positive_int,
        vol.Optional(ATTR_MESSAGE_TAG): cv.string,
        vol.Optional(ATTR_MESSAGE_THREAD_ID): vol.Coerce(int),
    }
)

SERVICE_SCHEMA_SEND_MESSAGE = vol.All(
    cv.deprecated(ATTR_TIMEOUT),
    BASE_SERVICE_SCHEMA.extend(
        {
            vol.Required(ATTR_MESSAGE): cv.string,
            vol.Optional(ATTR_TITLE): cv.string,
            vol.Optional(ATTR_REPLY_TO_MSGID): vol.Coerce(int),
        }
    ),
)

SERVICE_SCHEMA_SEND_CHAT_ACTION = vol.All(
    cv.deprecated(ATTR_TIMEOUT),
    vol.Schema(
        {
            vol.Optional(ATTR_ENTITY_ID): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
            vol.Optional(ATTR_TARGET): vol.All(cv.ensure_list, [vol.Coerce(int)]),
            vol.Optional(ATTR_CHAT_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
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
            vol.Optional(ATTR_MESSAGE_THREAD_ID): vol.Coerce(int),
        }
    ),
)

SERVICE_SCHEMA_BASE_SEND_FILE = BASE_SERVICE_SCHEMA.extend(
    {
        vol.Optional(ATTR_URL): cv.string,
        vol.Optional(ATTR_FILE): cv.string,
        vol.Optional(ATTR_CAPTION): cv.string,
        vol.Optional(ATTR_USERNAME): cv.string,
        vol.Optional(ATTR_PASSWORD): cv.string,
        vol.Optional(ATTR_AUTHENTICATION): cv.string,
        vol.Optional(ATTR_VERIFY_SSL): cv.boolean,
        vol.Optional(ATTR_REPLY_TO_MSGID): vol.Coerce(int),
    }
)

SERVICE_SCHEMA_SEND_FILE = vol.All(
    cv.deprecated(ATTR_TIMEOUT),
    SERVICE_SCHEMA_BASE_SEND_FILE,
)


SERVICE_SCHEMA_SEND_STICKER = vol.All(
    cv.deprecated(ATTR_TIMEOUT),
    SERVICE_SCHEMA_BASE_SEND_FILE.extend({vol.Optional(ATTR_STICKER_ID): cv.string}),
)

SERVICE_SCHEMA_SEND_LOCATION = vol.All(
    cv.deprecated(ATTR_TIMEOUT),
    BASE_SERVICE_SCHEMA.extend(
        {
            vol.Required(ATTR_LONGITUDE): cv.string,
            vol.Required(ATTR_LATITUDE): cv.string,
            vol.Optional(ATTR_REPLY_TO_MSGID): vol.Coerce(int),
        }
    ),
)

SERVICE_SCHEMA_SEND_POLL = vol.All(
    cv.deprecated(ATTR_TIMEOUT),
    vol.Schema(
        {
            vol.Optional(ATTR_ENTITY_ID): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
            vol.Optional(ATTR_CHAT_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
            vol.Optional(ATTR_TARGET): vol.All(cv.ensure_list, [vol.Coerce(int)]),
            vol.Required(ATTR_QUESTION): cv.string,
            vol.Required(ATTR_OPTIONS): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_OPEN_PERIOD): cv.positive_int,
            vol.Optional(ATTR_IS_ANONYMOUS, default=True): cv.boolean,
            vol.Optional(ATTR_ALLOWS_MULTIPLE_ANSWERS, default=False): cv.boolean,
            vol.Optional(ATTR_DISABLE_NOTIF): cv.boolean,
            vol.Optional(ATTR_MESSAGE_THREAD_ID): vol.Coerce(int),
            vol.Optional(ATTR_REPLY_TO_MSGID): vol.Coerce(int),
        }
    ),
)

SERVICE_SCHEMA_EDIT_MESSAGE = vol.All(
    cv.deprecated(ATTR_TIMEOUT),
    vol.Schema(
        {
            vol.Optional(ATTR_ENTITY_ID): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
            vol.Optional(ATTR_TITLE): cv.string,
            vol.Required(ATTR_MESSAGE): cv.string,
            vol.Required(ATTR_MESSAGEID): vol.Any(
                cv.positive_int, vol.All(cv.string, "last")
            ),
            vol.Optional(ATTR_CHAT_ID): vol.Coerce(int),
            vol.Optional(ATTR_PARSER): ATTR_PARSER_SCHEMA,
            vol.Optional(ATTR_KEYBOARD_INLINE): cv.ensure_list,
            vol.Optional(ATTR_DISABLE_WEB_PREV): cv.boolean,
        }
    ),
)

SERVICE_SCHEMA_EDIT_MESSAGE_MEDIA = vol.All(
    cv.deprecated(ATTR_TIMEOUT),
    vol.Schema(
        {
            vol.Optional(ATTR_ENTITY_ID): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
            vol.Required(ATTR_MESSAGEID): vol.Any(
                cv.positive_int, vol.All(cv.string, "last")
            ),
            vol.Optional(ATTR_CHAT_ID): vol.Coerce(int),
            vol.Optional(ATTR_CAPTION): cv.string,
            vol.Optional(ATTR_PARSER): ATTR_PARSER_SCHEMA,
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
        }
    ),
)

SERVICE_SCHEMA_EDIT_CAPTION = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_MESSAGEID): vol.Any(
            cv.positive_int, vol.All(cv.string, "last")
        ),
        vol.Optional(ATTR_CHAT_ID): vol.Coerce(int),
        vol.Optional(ATTR_PARSER): ATTR_PARSER_SCHEMA,
        vol.Required(ATTR_CAPTION): cv.string,
        vol.Optional(ATTR_KEYBOARD_INLINE): cv.ensure_list,
    }
)

SERVICE_SCHEMA_EDIT_REPLYMARKUP = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_MESSAGEID): vol.Any(
            cv.positive_int, vol.All(cv.string, "last")
        ),
        vol.Optional(ATTR_CHAT_ID): vol.Coerce(int),
        vol.Required(ATTR_KEYBOARD_INLINE): cv.ensure_list,
    }
)

SERVICE_SCHEMA_ANSWER_CALLBACK_QUERY = vol.Schema(
    {
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Required(ATTR_CALLBACK_QUERY_ID): vol.Coerce(int),
        vol.Optional(ATTR_SHOW_ALERT): cv.boolean,
    }
)

SERVICE_SCHEMA_DELETE_MESSAGE = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_CHAT_ID): vol.Coerce(int),
        vol.Required(ATTR_MESSAGEID): vol.Any(
            cv.positive_int, vol.All(cv.string, "last")
        ),
    }
)

SERVICE_SCHEMA_LEAVE_CHAT = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_CHAT_ID): vol.Coerce(int),
    }
)

SERVICE_SCHEMA_SET_MESSAGE_REACTION = vol.Schema(
    {
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_MESSAGEID): vol.Any(
            cv.positive_int, vol.All(cv.string, "last")
        ),
        vol.Optional(ATTR_CHAT_ID): vol.Coerce(int),
        vol.Required(ATTR_REACTION): cv.string,
        vol.Optional(ATTR_IS_BIG, default=False): cv.boolean,
    }
)

SERVICE_SCHEMA_DOWNLOAD_FILE = vol.Schema(
    {
        vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_FILE_ID): cv.string,
        vol.Optional(ATTR_DIRECTORY_PATH): cv.string,
        vol.Optional(ATTR_FILE_NAME): cv.string,
    }
)

SERVICE_MAP: dict[str, VolSchemaType] = {
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
    SERVICE_DOWNLOAD_FILE: SERVICE_SCHEMA_DOWNLOAD_FILE,
}


class BotPlatformModule(Protocol):
    """Define the module protocol for telegram bot modules."""

    async def async_setup_bot_platform(
        self, hass: HomeAssistant, bot: Bot, config: TelegramBotConfigEntry
    ) -> BaseTelegramBot | None:
        """Set up the Telegram bot platform."""


MODULES = {
    PLATFORM_BROADCAST: broadcast,
    PLATFORM_POLLING: polling,
    PLATFORM_WEBHOOKS: webhooks,
}

PLATFORMS: list[Platform] = [Platform.EVENT, Platform.NOTIFY]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Telegram bot component."""

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
            SERVICE_DOWNLOAD_FILE,
        ]:
            supports_response = SupportsResponse.OPTIONAL

        hass.services.async_register(
            DOMAIN,
            service_notif,
            _async_send_telegram_message,
            schema=schema,
            supports_response=supports_response,
            description_placeholders={
                "formatting_options_url": "https://core.telegram.org/bots/api#formatting-options"
            },
        )

    return True


async def _async_send_telegram_message(service: ServiceCall) -> ServiceResponse:
    """Handle sending Telegram Bot message service calls."""

    _deprecate_timeout(service)

    # this is the list of targets to send the message to
    targets = _build_targets(service)

    service_responses: JsonValueType = []
    errors: list[tuple[Exception, str]] = []

    # invoke the service for each target
    for target_config_entry, target_chat_id, target_notify_entity_id in targets:
        try:
            service_response = await _call_service(
                service, target_config_entry.runtime_data, target_chat_id
            )

            if service.service == SERVICE_DOWNLOAD_FILE:
                return service_response

            if service_response is not None:
                formatted_responses: list[JsonValueType] = []
                for chat_id, message_id in service_response.items():
                    formatted_response = {
                        ATTR_CHAT_ID: int(chat_id),
                        ATTR_MESSAGEID: message_id,
                    }

                    if target_notify_entity_id:
                        formatted_response[ATTR_ENTITY_ID] = target_notify_entity_id

                    formatted_responses.append(formatted_response)

                assert isinstance(service_responses, list)
                service_responses.extend(formatted_responses)
        except (HomeAssistantError, TelegramError) as ex:
            target = target_notify_entity_id or str(target_chat_id)
            errors.append((ex, target))

    if len(errors) == 1:
        raise errors[0][0]

    if len(errors) > 1:
        error_messages: list[str] = []
        for error, target in errors:
            target_type = ATTR_CHAT_ID if target.isdigit() else ATTR_ENTITY_ID
            error_messages.append(f"`{target_type}` {target}: {error}")

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="multiple_errors",
            translation_placeholders={"errors": "\n".join(error_messages)},
        )

    if service.return_response:
        return {"chats": service_responses}

    return None


async def _call_service(
    service: ServiceCall, notify_service: TelegramNotificationService, chat_id: int
) -> dict[str, JsonValueType] | None:
    """Calls a Telegram bot service using the specified bot and chat_id."""

    service_name = service.service

    kwargs = dict(service.data)
    kwargs[ATTR_CHAT_ID] = chat_id

    messages: dict[str, JsonValueType] | None = None
    if service_name == SERVICE_SEND_MESSAGE:
        messages = await notify_service.send_message(context=service.context, **kwargs)
    elif service_name == SERVICE_SEND_CHAT_ACTION:
        messages = await notify_service.send_chat_action(
            context=service.context, **kwargs
        )
    elif service_name in [
        SERVICE_SEND_PHOTO,
        SERVICE_SEND_ANIMATION,
        SERVICE_SEND_VIDEO,
        SERVICE_SEND_VOICE,
        SERVICE_SEND_DOCUMENT,
    ]:
        messages = await notify_service.send_file(
            service_name, context=service.context, **kwargs
        )
    elif service_name == SERVICE_SEND_STICKER:
        messages = await notify_service.send_sticker(context=service.context, **kwargs)
    elif service_name == SERVICE_SEND_LOCATION:
        messages = await notify_service.send_location(context=service.context, **kwargs)
    elif service_name == SERVICE_SEND_POLL:
        messages = await notify_service.send_poll(context=service.context, **kwargs)
    elif service_name == SERVICE_ANSWER_CALLBACK_QUERY:
        await notify_service.answer_callback_query(context=service.context, **kwargs)
    elif service_name == SERVICE_DELETE_MESSAGE:
        await notify_service.delete_message(context=service.context, **kwargs)
    elif service_name == SERVICE_LEAVE_CHAT:
        await notify_service.leave_chat(context=service.context, **kwargs)
    elif service_name == SERVICE_SET_MESSAGE_REACTION:
        await notify_service.set_message_reaction(context=service.context, **kwargs)
    elif service_name == SERVICE_EDIT_MESSAGE_MEDIA:
        await notify_service.edit_message_media(context=service.context, **kwargs)
    elif service_name == SERVICE_DOWNLOAD_FILE:
        return await notify_service.download_file(context=service.context, **kwargs)
    else:
        await notify_service.edit_message(
            service_name, context=service.context, **kwargs
        )

    if service.return_response and messages is not None:
        return messages

    return None


def _deprecate_timeout(service: ServiceCall) -> None:
    if ATTR_TIMEOUT not in service.data:
        return

    # default: service was called using frontend such as developer tools or automation editor
    service_call_origin = "call_service"

    origin = service.context.origin_event
    if origin and ATTR_ENTITY_ID in origin.data:
        # automation
        service_call_origin = origin.data[ATTR_ENTITY_ID]
    elif origin and origin.data.get(ATTR_DOMAIN) == SCRIPT_DOMAIN:
        # script
        service_call_origin = f"{origin.data[ATTR_DOMAIN]}.{origin.data[ATTR_SERVICE]}"

    ir.async_create_issue(
        service.hass,
        DOMAIN,
        "deprecated_timeout_parameter",
        breaks_in_ha_version="2026.7.0",
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_timeout_parameter",
        translation_placeholders={
            "integration_title": "Telegram Bot",
            "action": f"{DOMAIN}.{service.service}",
            "action_origin": service_call_origin,
        },
        learn_more_url="https://github.com/home-assistant/core/pull/155198",
    )


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: TelegramBotConfigEntry
) -> bool:
    """Migrate Telegram Bot config entry."""

    version = config_entry.version
    minor_version = config_entry.minor_version
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        version,
        minor_version,
    )

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    # version 1.1: to add default API endpoint
    if version == 1 and minor_version == 1:
        new_data = {**config_entry.data}
        new_data[CONF_API_ENDPOINT] = DEFAULT_API_ENDPOINT
        updated = hass.config_entries.async_update_entry(
            config_entry, data=new_data, minor_version=2
        )
        _LOGGER.debug(
            "Migrated Telegram Bot config entry to %s.%s, entry updated: %s",
            config_entry.version,
            config_entry.minor_version,
            updated,
        )

    return True


def _build_targets(
    service: ServiceCall,
) -> list[tuple[TelegramBotConfigEntry, int, str]]:
    """Builds a list of targets from the service parameters.

    Each target is a tuple of (config_entry, chat_id, notify_entity_id).
    The config_entry identifies the bot to use for the service call.
    The chat_id or notify_entity_id identifies the recipient of the message.
    """

    migrate_chat_ids = _warn_chat_id_migration(service)

    targets: list[tuple[TelegramBotConfigEntry, int, str]] = []

    # build target list from notify entities using service data: `entity_id`

    referenced = async_extract_referenced_entity_ids(
        service.hass, TargetSelection(service.data)
    )
    notify_entity_ids = referenced.referenced | referenced.indirectly_referenced

    # parse entity IDs
    entity_registry = er.async_get(service.hass)
    for notify_entity_id in notify_entity_ids:
        # get config entry from notify entity
        entity_entry = entity_registry.async_get(notify_entity_id)
        if not entity_entry:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_notify_entity",
                translation_placeholders={ATTR_ENTITY_ID: notify_entity_id},
            )
        assert entity_entry.config_entry_id is not None
        notify_config_entry = service.hass.config_entries.async_get_known_entry(
            entity_entry.config_entry_id
        )

        # get chat id from subentry
        assert entity_entry.config_subentry_id is not None
        notify_config_subentry = notify_config_entry.subentries[
            entity_entry.config_subentry_id
        ]
        notify_chat_id: int = notify_config_subentry.data[ATTR_CHAT_ID]

        targets.append((notify_config_entry, notify_chat_id, notify_entity_id))

    # build target list using service data: `config_entry_id` and `chat_id`

    config_entry: TelegramBotConfigEntry | None = None
    if CONF_CONFIG_ENTRY_ID in service.data:
        # parse config entry from service data
        config_entry_id: str = service.data[CONF_CONFIG_ENTRY_ID]
        config_entry = service.hass.config_entries.async_get_known_entry(
            config_entry_id
        )
    else:
        # config entry not provided so we try to determine the default
        config_entries: list[TelegramBotConfigEntry] = (
            service.hass.config_entries.async_entries(DOMAIN)
        )
        if len(config_entries) == 1:
            config_entry = config_entries[0]

    # parse chat IDs from service data: `chat_id`
    if config_entry is not None:
        chat_ids: set[int] = migrate_chat_ids
        if ATTR_CHAT_ID in service.data:
            chat_ids = chat_ids | set(
                [service.data[ATTR_CHAT_ID]]
                if isinstance(service.data[ATTR_CHAT_ID], int)
                else service.data[ATTR_CHAT_ID]
            )

        if not chat_ids and not targets:
            # no targets from service data, so we default to the first allowed chat IDs of the config entry
            subentries = list(config_entry.subentries.values())
            if not subentries:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="missing_allowed_chat_ids",
                    translation_placeholders={
                        "bot_name": config_entry.title,
                    },
                )

            default_chat_id: int = subentries[0].data[ATTR_CHAT_ID]
            _LOGGER.debug(
                "Defaulting to chat ID %s for bot %s",
                default_chat_id,
                config_entry.title,
            )
            chat_ids = {default_chat_id}

        invalid_chat_ids: set[int] = set()
        for chat_id in chat_ids:
            # map chat_id to notify entity ID

            if config_entry.state is not ConfigEntryState.LOADED:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="entry_not_loaded",
                    translation_placeholders={"telegram_bot": config_entry.title},
                )

            entity_id = entity_registry.async_get_entity_id(
                "notify",
                DOMAIN,
                f"{config_entry.runtime_data.bot.id}_{chat_id}",
            )

            if not entity_id:
                invalid_chat_ids.add(chat_id)
            else:
                targets.append((config_entry, chat_id, entity_id))

        if invalid_chat_ids:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_chat_ids",
                translation_placeholders={
                    "chat_ids": ", ".join(str(chat_id) for chat_id in invalid_chat_ids),
                    "bot_name": config_entry.title,
                },
            )

    # we're done building targets from service data
    if targets:
        return targets

    # can't determine default since multiple config entries exist
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="missing_notify_entities",
    )


def _warn_chat_id_migration(service: ServiceCall) -> set[int]:
    if not service.data.get(ATTR_TARGET):
        return set()

    chat_ids: set[int] = set(
        [service.data[ATTR_TARGET]]
        if isinstance(service.data[ATTR_TARGET], int)
        else service.data[ATTR_TARGET]
    )

    # default: service was called using frontend such as developer tools or automation editor
    service_call_origin = "call_service"

    origin = service.context.origin_event
    if origin and ATTR_ENTITY_ID in origin.data:
        # automation
        service_call_origin = origin.data[ATTR_ENTITY_ID]
    elif origin and origin.data.get(ATTR_DOMAIN) == SCRIPT_DOMAIN:
        # script
        service_call_origin = f"{origin.data[ATTR_DOMAIN]}.{origin.data[ATTR_SERVICE]}"

    ir.async_create_issue(
        service.hass,
        DOMAIN,
        f"migrate_chat_ids_in_target_{service_call_origin}_{service.service}",
        breaks_in_ha_version="2026.9.0",
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="migrate_chat_ids_in_target",
        translation_placeholders={
            "integration_title": "Telegram Bot",
            "action": f"{DOMAIN}.{service.service}",
            "chat_ids": ", ".join(str(chat_id) for chat_id in chat_ids),
            "action_origin": service_call_origin,
            "telegram_bot_entities_url": "/config/entities?domain=telegram_bot",
            "example_old": f"```yaml\naction: {service.service}\ndata:\n  target:  # to be updated\n    - 1234567890\n...\n```",
            "example_new_entity_id": f"```yaml\naction: {service.service}\ndata:\n  entity_id:\n    - notify.telegram_bot_1234567890_1234567890  # replace with your notify entity\n...\n```",
            "example_new_chat_id": f"```yaml\naction: {service.service}\ndata:\n  chat_id:\n    - 1234567890  # replace with your chat_id\n...\n```",
        },
        learn_more_url="https://github.com/home-assistant/core/pull/154868",
    )

    return chat_ids


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
    module = cast(BotPlatformModule, MODULES[p_type])
    try:
        receiver_service = await module.async_setup_bot_platform(hass, bot, entry)
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
