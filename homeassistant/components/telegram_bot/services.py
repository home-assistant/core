"""Support for Telegram bot services."""

import logging

import probatio
from telegram.constants import InputMediaType
from telegram.error import TelegramError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CommonServiceArgument
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)
from homeassistant.helpers.typing import VolSchemaType
from homeassistant.util.json import JsonValueType

from .bot import TelegramBotConfigEntry, TelegramNotificationService
from .const import (
    CONF_CHAT_ID,
    DOMAIN,
    TelegramBotChatAction,
    TelegramBotParseMode,
    TelegramBotService,
    TelegramBotServiceArgument,
    TelegramBotServiceResponse,
)

_LOGGER = logging.getLogger(__name__)

ATTR_PARSER_SCHEMA = probatio.All(
    cv.string,
    probatio.In(list(TelegramBotParseMode)),
)

BASE_SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.ENTITY_ID): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Optional(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Optional(TelegramBotServiceArgument.CHAT_ID): probatio.All(
            probatio.EnsureList(), [probatio.Coerce(int)]
        ),
        probatio.Optional(TelegramBotServiceArgument.PARSE_MODE): ATTR_PARSER_SCHEMA,
        probatio.Optional(TelegramBotServiceArgument.DISABLE_NOTIFICATION): cv.boolean,
        probatio.Optional(
            TelegramBotServiceArgument.DISABLE_WEB_PAGE_PREVIEW
        ): cv.boolean,
        probatio.Optional(TelegramBotServiceArgument.RESIZE_KEYBOARD): cv.boolean,
        probatio.Optional(TelegramBotServiceArgument.ONE_TIME_KEYBOARD): cv.boolean,
        probatio.Optional(TelegramBotServiceArgument.KEYBOARD): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Optional(
            TelegramBotServiceArgument.INLINE_KEYBOARD
        ): probatio.EnsureList(),
        probatio.Optional(TelegramBotServiceArgument.MESSAGE_TAG): cv.string,
        probatio.Optional(
            TelegramBotServiceArgument.MESSAGE_THREAD_ID
        ): probatio.Coerce(int),
    }
)

SERVICE_SCHEMA_SEND_MESSAGE = BASE_SERVICE_SCHEMA.extend(
    {
        probatio.Required(TelegramBotServiceArgument.MESSAGE): cv.string,
        probatio.Optional(TelegramBotServiceArgument.TITLE): cv.string,
        probatio.Optional(
            TelegramBotServiceArgument.REPLY_TO_MESSAGE_ID
        ): probatio.Coerce(int),
    }
)

SERVICE_SCHEMA_SEND_MESSAGE_DRAFT = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.ENTITY_ID): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Optional(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Optional(TelegramBotServiceArgument.CHAT_ID): probatio.All(
            probatio.EnsureList(), [probatio.Coerce(int)]
        ),
        probatio.Optional(
            TelegramBotServiceArgument.MESSAGE_THREAD_ID
        ): probatio.Coerce(int),
        probatio.Required(TelegramBotServiceArgument.DRAFT_ID): probatio.All(
            probatio.Coerce(int), probatio.Range(min=1)
        ),
        probatio.Required(TelegramBotServiceArgument.MESSAGE): cv.string,
        probatio.Optional(TelegramBotServiceArgument.PARSE_MODE): ATTR_PARSER_SCHEMA,
    }
)

SERVICE_SCHEMA_SEND_CHAT_ACTION = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.ENTITY_ID): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Optional(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Optional(TelegramBotServiceArgument.CHAT_ID): probatio.All(
            probatio.EnsureList(), [probatio.Coerce(int)]
        ),
        probatio.Required(TelegramBotServiceArgument.CHAT_ACTION): probatio.In(
            list(TelegramBotChatAction)
        ),
        probatio.Optional(
            TelegramBotServiceArgument.MESSAGE_THREAD_ID
        ): probatio.Coerce(int),
    }
)

SERVICE_SCHEMA_SEND_FILE = BASE_SERVICE_SCHEMA.extend(
    {
        probatio.Optional(TelegramBotServiceArgument.URL): cv.string,
        probatio.Optional(TelegramBotServiceArgument.FILE): cv.string,
        probatio.Optional(TelegramBotServiceArgument.CAPTION): cv.string,
        probatio.Optional(TelegramBotServiceArgument.USERNAME): cv.string,
        probatio.Optional(TelegramBotServiceArgument.PASSWORD): cv.string,
        probatio.Optional(TelegramBotServiceArgument.AUTHENTICATION): cv.string,
        probatio.Optional(TelegramBotServiceArgument.VERIFY_SSL): cv.boolean,
        probatio.Optional(
            TelegramBotServiceArgument.REPLY_TO_MESSAGE_ID
        ): probatio.Coerce(int),
    }
)

SERVICE_SCHEMA_SEND_MEDIA_GROUP = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.ENTITY_ID): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Optional(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Optional(TelegramBotServiceArgument.CHAT_ID): probatio.All(
            probatio.EnsureList(), [probatio.Coerce(int)]
        ),
        probatio.Required(TelegramBotServiceArgument.MEDIA): probatio.All(
            probatio.EnsureList(),
            [
                probatio.Schema(
                    {
                        probatio.Required(
                            TelegramBotServiceArgument.MEDIA_TYPE
                        ): probatio.In(
                            (
                                str(InputMediaType.AUDIO),
                                str(InputMediaType.VIDEO),
                                str(InputMediaType.DOCUMENT),
                                str(InputMediaType.PHOTO),
                            )
                        ),
                        probatio.Optional(TelegramBotServiceArgument.URL): cv.string,
                        probatio.Optional(TelegramBotServiceArgument.FILE): cv.string,
                        probatio.Optional(
                            TelegramBotServiceArgument.CAPTION
                        ): cv.string,
                        probatio.Optional(
                            TelegramBotServiceArgument.USERNAME
                        ): cv.string,
                        probatio.Optional(
                            TelegramBotServiceArgument.PASSWORD
                        ): cv.string,
                        probatio.Optional(
                            TelegramBotServiceArgument.AUTHENTICATION
                        ): cv.string,
                        probatio.Optional(
                            TelegramBotServiceArgument.VERIFY_SSL, default=True
                        ): cv.boolean,
                    }
                )
            ],
            probatio.Length(min=2, max=10),
        ),
        probatio.Optional(TelegramBotServiceArgument.PARSE_MODE): ATTR_PARSER_SCHEMA,
        probatio.Optional(TelegramBotServiceArgument.DISABLE_NOTIFICATION): cv.boolean,
        probatio.Optional(TelegramBotServiceArgument.PROTECT_CONTENT): cv.boolean,
        probatio.Optional(
            TelegramBotServiceArgument.REPLY_TO_MESSAGE_ID
        ): probatio.Coerce(int),
        probatio.Optional(
            TelegramBotServiceArgument.MESSAGE_THREAD_ID
        ): probatio.Coerce(int),
    }
)

SERVICE_SCHEMA_SEND_STICKER = SERVICE_SCHEMA_SEND_FILE.extend(
    {probatio.Optional(TelegramBotServiceArgument.STICKER_ID): cv.string}
)

SERVICE_SCHEMA_SEND_LOCATION = BASE_SERVICE_SCHEMA.extend(
    {
        probatio.Required(TelegramBotServiceArgument.LONGITUDE): cv.string,
        probatio.Required(TelegramBotServiceArgument.LATITUDE): cv.string,
        probatio.Optional(
            TelegramBotServiceArgument.REPLY_TO_MESSAGE_ID
        ): probatio.Coerce(int),
    }
)

SERVICE_SCHEMA_SEND_POLL = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.ENTITY_ID): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Optional(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Optional(TelegramBotServiceArgument.CHAT_ID): probatio.All(
            probatio.EnsureList(), [probatio.Coerce(int)]
        ),
        probatio.Required(TelegramBotServiceArgument.QUESTION): cv.string,
        probatio.Required(TelegramBotServiceArgument.OPTIONS): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Optional(TelegramBotServiceArgument.OPEN_PERIOD): cv.positive_int,
        probatio.Optional(
            TelegramBotServiceArgument.IS_ANONYMOUS, default=True
        ): cv.boolean,
        probatio.Optional(
            TelegramBotServiceArgument.ALLOWS_MULTIPLE_ANSWERS, default=False
        ): cv.boolean,
        probatio.Optional(TelegramBotServiceArgument.DISABLE_NOTIFICATION): cv.boolean,
        probatio.Optional(
            TelegramBotServiceArgument.MESSAGE_THREAD_ID
        ): probatio.Coerce(int),
        probatio.Optional(
            TelegramBotServiceArgument.REPLY_TO_MESSAGE_ID
        ): probatio.Coerce(int),
    }
)

SERVICE_SCHEMA_EDIT_MESSAGE = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.ENTITY_ID): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Optional(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Optional(TelegramBotServiceArgument.TITLE): cv.string,
        probatio.Required(TelegramBotServiceArgument.MESSAGE): cv.string,
        probatio.Required(TelegramBotServiceArgument.MESSAGE_ID): probatio.Any(
            cv.positive_int, probatio.All(cv.string, "last")
        ),
        probatio.Optional(TelegramBotServiceArgument.CHAT_ID): probatio.Coerce(int),
        probatio.Optional(TelegramBotServiceArgument.PARSE_MODE): ATTR_PARSER_SCHEMA,
        probatio.Optional(
            TelegramBotServiceArgument.INLINE_KEYBOARD
        ): probatio.EnsureList(),
        probatio.Optional(
            TelegramBotServiceArgument.DISABLE_WEB_PAGE_PREVIEW
        ): cv.boolean,
    }
)

SERVICE_SCHEMA_EDIT_MESSAGE_MEDIA = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.ENTITY_ID): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Optional(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Required(TelegramBotServiceArgument.MESSAGE_ID): probatio.Any(
            cv.positive_int, probatio.All(cv.string, "last")
        ),
        probatio.Optional(TelegramBotServiceArgument.CHAT_ID): probatio.Coerce(int),
        probatio.Optional(TelegramBotServiceArgument.CAPTION): cv.string,
        probatio.Optional(TelegramBotServiceArgument.PARSE_MODE): ATTR_PARSER_SCHEMA,
        probatio.Required(TelegramBotServiceArgument.MEDIA_TYPE): probatio.In(
            (
                str(InputMediaType.ANIMATION),
                str(InputMediaType.AUDIO),
                str(InputMediaType.VIDEO),
                str(InputMediaType.DOCUMENT),
                str(InputMediaType.PHOTO),
            )
        ),
        probatio.Optional(TelegramBotServiceArgument.URL): cv.string,
        probatio.Optional(TelegramBotServiceArgument.FILE): cv.string,
        probatio.Optional(TelegramBotServiceArgument.USERNAME): cv.string,
        probatio.Optional(TelegramBotServiceArgument.PASSWORD): cv.string,
        probatio.Optional(TelegramBotServiceArgument.AUTHENTICATION): cv.string,
        probatio.Optional(TelegramBotServiceArgument.VERIFY_SSL): cv.boolean,
        probatio.Optional(
            TelegramBotServiceArgument.INLINE_KEYBOARD
        ): probatio.EnsureList(),
    }
)

SERVICE_SCHEMA_EDIT_CAPTION = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.ENTITY_ID): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Optional(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Required(TelegramBotServiceArgument.MESSAGE_ID): probatio.Any(
            cv.positive_int, probatio.All(cv.string, "last")
        ),
        probatio.Optional(TelegramBotServiceArgument.CHAT_ID): probatio.Coerce(int),
        probatio.Optional(TelegramBotServiceArgument.PARSE_MODE): ATTR_PARSER_SCHEMA,
        probatio.Required(TelegramBotServiceArgument.CAPTION): cv.string,
        probatio.Optional(
            TelegramBotServiceArgument.INLINE_KEYBOARD
        ): probatio.EnsureList(),
    }
)

SERVICE_SCHEMA_EDIT_REPLYMARKUP = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.ENTITY_ID): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Optional(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Required(TelegramBotServiceArgument.MESSAGE_ID): probatio.Any(
            cv.positive_int, probatio.All(cv.string, "last")
        ),
        probatio.Optional(TelegramBotServiceArgument.CHAT_ID): probatio.Coerce(int),
        probatio.Required(
            TelegramBotServiceArgument.INLINE_KEYBOARD
        ): probatio.EnsureList(),
    }
)

SERVICE_SCHEMA_ANSWER_CALLBACK_QUERY = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Required(TelegramBotServiceArgument.MESSAGE): cv.string,
        probatio.Required(
            TelegramBotServiceArgument.CALLBACK_QUERY_ID
        ): probatio.Coerce(int),
        probatio.Optional(TelegramBotServiceArgument.SHOW_ALERT): cv.boolean,
    }
)

SERVICE_SCHEMA_DELETE_MESSAGE = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.ENTITY_ID): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Optional(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Optional(TelegramBotServiceArgument.CHAT_ID): probatio.Coerce(int),
        probatio.Required(TelegramBotServiceArgument.MESSAGE_ID): probatio.Any(
            cv.positive_int, probatio.All(cv.string, "last")
        ),
    }
)

SERVICE_SCHEMA_LEAVE_CHAT = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.ENTITY_ID): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Optional(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Optional(TelegramBotServiceArgument.CHAT_ID): probatio.Coerce(int),
    }
)

SERVICE_SCHEMA_SET_MESSAGE_REACTION = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Required(TelegramBotServiceArgument.MESSAGE_ID): probatio.Any(
            cv.positive_int, probatio.All(cv.string, "last")
        ),
        probatio.Optional(TelegramBotServiceArgument.CHAT_ID): probatio.Coerce(int),
        probatio.Required(TelegramBotServiceArgument.REACTION): cv.string,
        probatio.Optional(TelegramBotServiceArgument.IS_BIG, default=False): cv.boolean,
    }
)

SERVICE_SCHEMA_DOWNLOAD_FILE = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Required(TelegramBotServiceArgument.FILE_ID): cv.string,
        probatio.Optional(TelegramBotServiceArgument.DIRECTORY_PATH): cv.string,
        probatio.Optional(TelegramBotServiceArgument.FILE_NAME): cv.string,
    }
)

SERVICE_MAP: dict[str, VolSchemaType] = {
    TelegramBotService.SEND_MESSAGE: SERVICE_SCHEMA_SEND_MESSAGE,
    TelegramBotService.SEND_MESSAGE_DRAFT: SERVICE_SCHEMA_SEND_MESSAGE_DRAFT,
    TelegramBotService.SEND_CHAT_ACTION: SERVICE_SCHEMA_SEND_CHAT_ACTION,
    TelegramBotService.SEND_PHOTO: SERVICE_SCHEMA_SEND_FILE,
    TelegramBotService.SEND_MEDIA_GROUP: SERVICE_SCHEMA_SEND_MEDIA_GROUP,
    TelegramBotService.SEND_STICKER: SERVICE_SCHEMA_SEND_STICKER,
    TelegramBotService.SEND_ANIMATION: SERVICE_SCHEMA_SEND_FILE,
    TelegramBotService.SEND_VIDEO: SERVICE_SCHEMA_SEND_FILE,
    TelegramBotService.SEND_VOICE: SERVICE_SCHEMA_SEND_FILE,
    TelegramBotService.SEND_DOCUMENT: SERVICE_SCHEMA_SEND_FILE,
    TelegramBotService.SEND_LOCATION: SERVICE_SCHEMA_SEND_LOCATION,
    TelegramBotService.SEND_POLL: SERVICE_SCHEMA_SEND_POLL,
    TelegramBotService.EDIT_MESSAGE: SERVICE_SCHEMA_EDIT_MESSAGE,
    TelegramBotService.EDIT_MESSAGE_MEDIA: SERVICE_SCHEMA_EDIT_MESSAGE_MEDIA,
    TelegramBotService.EDIT_CAPTION: SERVICE_SCHEMA_EDIT_CAPTION,
    TelegramBotService.EDIT_REPLYMARKUP: SERVICE_SCHEMA_EDIT_REPLYMARKUP,
    TelegramBotService.ANSWER_CALLBACK_QUERY: SERVICE_SCHEMA_ANSWER_CALLBACK_QUERY,
    TelegramBotService.DELETE_MESSAGE: SERVICE_SCHEMA_DELETE_MESSAGE,
    TelegramBotService.LEAVE_CHAT: SERVICE_SCHEMA_LEAVE_CHAT,
    TelegramBotService.SET_MESSAGE_REACTION: SERVICE_SCHEMA_SET_MESSAGE_REACTION,
    TelegramBotService.DOWNLOAD_FILE: SERVICE_SCHEMA_DOWNLOAD_FILE,
}


async def _async_send_telegram_message(service: ServiceCall) -> ServiceResponse:
    """Handle sending Telegram Bot message service calls."""

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

            if service.service == TelegramBotService.DOWNLOAD_FILE:
                return service_response

            if service_response is not None:
                formatted_responses: list[JsonValueType] = []
                for chat_id, message_id in service_response.items():
                    formatted_response: dict[str, JsonValueType] = {
                        TelegramBotServiceResponse.CHAT_ID: int(chat_id),
                        TelegramBotServiceResponse.MESSAGE_ID: message_id,
                    }

                    if target_notify_entity_id:
                        formatted_response[TelegramBotServiceResponse.ENTITY_ID] = (
                            target_notify_entity_id
                        )

                    formatted_responses.append(formatted_response)

                assert isinstance(service_responses, list)
                service_responses.extend(formatted_responses)
        except (HomeAssistantError, TelegramError) as ex:
            target = target_notify_entity_id or str(target_chat_id)
            errors.append((ex, target))

    if len(errors) == 1:
        if isinstance(errors[0][0], HomeAssistantError):
            raise errors[0][0]
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="action_failed",
            translation_placeholders={"error": str(errors[0][0])},
        ) from errors[0][0]

    if len(errors) > 1:
        error_messages: list[str] = []
        for error, target in errors:
            target_type = (
                TelegramBotServiceArgument.CHAT_ID
                if target.isdigit()
                else CommonServiceArgument.ENTITY_ID
            )
            error_messages.append(f"`{target_type}` {target}: {error}")

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="multiple_errors",
            translation_placeholders={"errors": "\n".join(error_messages)},
        )

    if service.return_response:
        return {TelegramBotServiceResponse.CHATS: service_responses}

    return None


async def _call_service(
    service: ServiceCall, notify_service: TelegramNotificationService, chat_id: int
) -> dict[str, JsonValueType] | None:
    """Calls a Telegram bot service using the specified bot and chat_id."""

    service_name = service.service

    kwargs = dict(service.data)
    kwargs[TelegramBotServiceArgument.CHAT_ID] = chat_id

    messages: dict[str, JsonValueType] | None = None
    if service_name == TelegramBotService.SEND_MESSAGE:
        messages = await notify_service.send_message(context=service.context, **kwargs)
    elif service_name == TelegramBotService.SEND_MEDIA_GROUP:
        messages = await notify_service.send_media_group(
            context=service.context, **kwargs
        )
    elif service_name == TelegramBotService.SEND_CHAT_ACTION:
        messages = await notify_service.send_chat_action(
            context=service.context, **kwargs
        )
    elif service_name in [
        TelegramBotService.SEND_PHOTO,
        TelegramBotService.SEND_ANIMATION,
        TelegramBotService.SEND_VIDEO,
        TelegramBotService.SEND_VOICE,
        TelegramBotService.SEND_DOCUMENT,
    ]:
        messages = await notify_service.send_file(
            service_name, context=service.context, **kwargs
        )
    elif service_name == TelegramBotService.SEND_STICKER:
        messages = await notify_service.send_sticker(context=service.context, **kwargs)
    elif service_name == TelegramBotService.SEND_LOCATION:
        messages = await notify_service.send_location(context=service.context, **kwargs)
    elif service_name == TelegramBotService.SEND_POLL:
        messages = await notify_service.send_poll(context=service.context, **kwargs)
    elif service_name == TelegramBotService.ANSWER_CALLBACK_QUERY:
        await notify_service.answer_callback_query(context=service.context, **kwargs)
    elif service_name == TelegramBotService.DELETE_MESSAGE:
        await notify_service.delete_message(context=service.context, **kwargs)
    elif service_name == TelegramBotService.LEAVE_CHAT:
        await notify_service.leave_chat(context=service.context, **kwargs)
    elif service_name == TelegramBotService.SET_MESSAGE_REACTION:
        await notify_service.set_message_reaction(context=service.context, **kwargs)
    elif service_name == TelegramBotService.EDIT_MESSAGE_MEDIA:
        await notify_service.edit_message_media(context=service.context, **kwargs)
    elif service_name == TelegramBotService.SEND_MESSAGE_DRAFT:
        await notify_service.send_message_draft(context=service.context, **kwargs)
    elif service_name == TelegramBotService.DOWNLOAD_FILE:
        return await notify_service.download_file(context=service.context, **kwargs)
    else:
        await notify_service.edit_message(
            service_name, context=service.context, **kwargs
        )

    if service.return_response and messages is not None:
        return messages

    return None


def _build_targets(
    service: ServiceCall,
) -> list[tuple[TelegramBotConfigEntry, int, str]]:
    """Builds a list of targets from the service parameters.

    Each target is a tuple of (config_entry, chat_id, notify_entity_id).
    The config_entry identifies the bot to use for the service call.
    The chat_id or notify_entity_id identifies the recipient of the message.
    """

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
        if not entity_entry or entity_entry.platform != DOMAIN:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_notify_entity",
                translation_placeholders={"entity_id": notify_entity_id},
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
        notify_chat_id: int = notify_config_subentry.data[CONF_CHAT_ID]

        targets.append((notify_config_entry, notify_chat_id, notify_entity_id))

    # build target list using service data: `config_entry_id` and `chat_id`

    config_entry: TelegramBotConfigEntry | None = None
    if CommonServiceArgument.CONFIG_ENTRY_ID in service.data:
        # parse config entry from service data
        config_entry_id: str = service.data[CommonServiceArgument.CONFIG_ENTRY_ID]
        config_entry = service.hass.config_entries.async_get_known_entry(
            config_entry_id
        )
        if config_entry.domain != DOMAIN:
            raise ServiceValidationError(
                translation_domain=HOMEASSISTANT_DOMAIN,
                translation_key="service_config_entry_wrong_domain",
                translation_placeholders={
                    "domain": DOMAIN,
                    "entry_title": config_entry.title,
                },
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
        chat_ids: set[int] = set()
        if TelegramBotServiceArgument.CHAT_ID in service.data:
            chat_ids = set(
                [service.data[TelegramBotServiceArgument.CHAT_ID]]
                if isinstance(service.data[TelegramBotServiceArgument.CHAT_ID], int)
                else service.data[TelegramBotServiceArgument.CHAT_ID]
            )

        if not chat_ids and not targets:
            # no targets from service data, so we default
            # to the first allowed chat IDs of the config entry
            subentries = list(config_entry.subentries.values())
            if not subentries:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="missing_allowed_chat_ids",
                    translation_placeholders={
                        "bot_name": config_entry.title,
                    },
                )

            default_chat_id: int = subentries[0].data[CONF_CHAT_ID]
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


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Telegram bot services."""
    for service_notif, schema in SERVICE_MAP.items():
        supports_response = SupportsResponse.NONE

        if service_notif in [
            TelegramBotService.SEND_MESSAGE,
            TelegramBotService.SEND_CHAT_ACTION,
            TelegramBotService.SEND_PHOTO,
            TelegramBotService.SEND_MEDIA_GROUP,
            TelegramBotService.SEND_ANIMATION,
            TelegramBotService.SEND_VIDEO,
            TelegramBotService.SEND_VOICE,
            TelegramBotService.SEND_DOCUMENT,
            TelegramBotService.SEND_STICKER,
            TelegramBotService.SEND_LOCATION,
            TelegramBotService.SEND_POLL,
            TelegramBotService.DOWNLOAD_FILE,
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
