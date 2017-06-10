"""
Component to send and receive Telegram messages.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/telegram_bot/
"""
import asyncio
import io
from functools import partial
import logging
import os

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_MESSAGE, ATTR_TITLE, ATTR_DATA)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    CONF_PLATFORM, CONF_API_KEY, CONF_TIMEOUT, ATTR_LATITUDE, ATTR_LONGITUDE,
    HTTP_DIGEST_AUTHENTICATION)
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import TemplateError
from homeassistant.setup import async_prepare_setup_platform

REQUIREMENTS = ['python-telegram-bot==6.0.3']

_LOGGER = logging.getLogger(__name__)

ATTR_ARGS = 'args'
ATTR_AUTHENTICATION = 'authentication'
ATTR_CALLBACK_QUERY = 'callback_query'
ATTR_CALLBACK_QUERY_ID = 'callback_query_id'
ATTR_CAPTION = 'caption'
ATTR_CHAT_ID = 'chat_id'
ATTR_CHAT_INSTANCE = 'chat_instance'
ATTR_COMMAND = 'command'
ATTR_DISABLE_NOTIF = 'disable_notification'
ATTR_DISABLE_WEB_PREV = 'disable_web_page_preview'
ATTR_EDITED_MSG = 'edited_message'
ATTR_FILE = 'file'
ATTR_FROM_FIRST = 'from_first'
ATTR_FROM_LAST = 'from_last'
ATTR_KEYBOARD = 'keyboard'
ATTR_KEYBOARD_INLINE = 'inline_keyboard'
ATTR_MESSAGEID = 'message_id'
ATTR_MSG = 'message'
ATTR_MSGID = 'id'
ATTR_PARSER = 'parse_mode'
ATTR_PASSWORD = 'password'
ATTR_REPLY_TO_MSGID = 'reply_to_message_id'
ATTR_REPLYMARKUP = 'reply_markup'
ATTR_SHOW_ALERT = 'show_alert'
ATTR_TARGET = 'target'
ATTR_TEXT = 'text'
ATTR_URL = 'url'
ATTR_USER_ID = 'user_id'
ATTR_USERNAME = 'username'

CONF_ALLOWED_CHAT_IDS = 'allowed_chat_ids'

DOMAIN = 'telegram_bot'

SERVICE_SEND_MESSAGE = 'send_message'
SERVICE_SEND_PHOTO = 'send_photo'
SERVICE_SEND_DOCUMENT = 'send_document'
SERVICE_SEND_LOCATION = 'send_location'
SERVICE_EDIT_MESSAGE = 'edit_message'
SERVICE_EDIT_CAPTION = 'edit_caption'
SERVICE_EDIT_REPLYMARKUP = 'edit_replymarkup'
SERVICE_ANSWER_CALLBACK_QUERY = 'answer_callback_query'

EVENT_TELEGRAM_CALLBACK = 'telegram_callback'
EVENT_TELEGRAM_COMMAND = 'telegram_command'
EVENT_TELEGRAM_TEXT = 'telegram_text'

PARSER_HTML = 'html'
PARSER_MD = 'markdown'

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PLATFORM): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_ALLOWED_CHAT_IDS):
        vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Optional(ATTR_PARSER, default=PARSER_MD): cv.string,
})

BASE_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_TARGET): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Optional(ATTR_PARSER): cv.string,
    vol.Optional(ATTR_DISABLE_NOTIF): cv.boolean,
    vol.Optional(ATTR_DISABLE_WEB_PREV): cv.boolean,
    vol.Optional(ATTR_KEYBOARD): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_KEYBOARD_INLINE): cv.ensure_list,
}, extra=vol.ALLOW_EXTRA)

SERVICE_SCHEMA_SEND_MESSAGE = BASE_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_MESSAGE): cv.template,
    vol.Optional(ATTR_TITLE): cv.template,
})

SERVICE_SCHEMA_SEND_FILE = BASE_SERVICE_SCHEMA.extend({
    vol.Optional(ATTR_URL): cv.template,
    vol.Optional(ATTR_FILE): cv.template,
    vol.Optional(ATTR_CAPTION): cv.template,
    vol.Optional(ATTR_USERNAME): cv.string,
    vol.Optional(ATTR_PASSWORD): cv.string,
    vol.Optional(ATTR_AUTHENTICATION): cv.string,
})

SERVICE_SCHEMA_SEND_LOCATION = BASE_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_LONGITUDE): cv.template,
    vol.Required(ATTR_LATITUDE): cv.template,
})

SERVICE_SCHEMA_EDIT_MESSAGE = SERVICE_SCHEMA_SEND_MESSAGE.extend({
    vol.Required(ATTR_MESSAGEID): vol.Any(cv.positive_int, cv.string),
    vol.Required(ATTR_CHAT_ID): vol.Coerce(int),
})

SERVICE_SCHEMA_EDIT_CAPTION = vol.Schema({
    vol.Required(ATTR_MESSAGEID): vol.Any(cv.positive_int, cv.string),
    vol.Required(ATTR_CHAT_ID): vol.Coerce(int),
    vol.Required(ATTR_CAPTION): cv.template,
    vol.Optional(ATTR_KEYBOARD_INLINE): cv.ensure_list,
}, extra=vol.ALLOW_EXTRA)

SERVICE_SCHEMA_EDIT_REPLYMARKUP = vol.Schema({
    vol.Required(ATTR_MESSAGEID): vol.Any(cv.positive_int, cv.string),
    vol.Required(ATTR_CHAT_ID): vol.Coerce(int),
    vol.Required(ATTR_KEYBOARD_INLINE): cv.ensure_list,
}, extra=vol.ALLOW_EXTRA)

SERVICE_SCHEMA_ANSWER_CALLBACK_QUERY = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.template,
    vol.Required(ATTR_CALLBACK_QUERY_ID): vol.Coerce(int),
    vol.Optional(ATTR_SHOW_ALERT): cv.boolean,
}, extra=vol.ALLOW_EXTRA)

SERVICE_MAP = {
    SERVICE_SEND_MESSAGE: SERVICE_SCHEMA_SEND_MESSAGE,
    SERVICE_SEND_PHOTO: SERVICE_SCHEMA_SEND_FILE,
    SERVICE_SEND_DOCUMENT: SERVICE_SCHEMA_SEND_FILE,
    SERVICE_SEND_LOCATION: SERVICE_SCHEMA_SEND_LOCATION,
    SERVICE_EDIT_MESSAGE: SERVICE_SCHEMA_EDIT_MESSAGE,
    SERVICE_EDIT_CAPTION: SERVICE_SCHEMA_EDIT_CAPTION,
    SERVICE_EDIT_REPLYMARKUP: SERVICE_SCHEMA_EDIT_REPLYMARKUP,
    SERVICE_ANSWER_CALLBACK_QUERY: SERVICE_SCHEMA_ANSWER_CALLBACK_QUERY,
}


def load_data(url=None, filepath=None, username=None, password=None,
              authentication=None, num_retries=5):
    """Load photo/document into ByteIO/File container from a source."""
    try:
        if url is not None:
            # Load photo from URL
            params = {"timeout": 15}
            if username is not None and password is not None:
                if authentication == HTTP_DIGEST_AUTHENTICATION:
                    params["auth"] = HTTPDigestAuth(username, password)
                else:
                    params["auth"] = HTTPBasicAuth(username, password)
            retry_num = 0
            while retry_num < num_retries:
                req = requests.get(url, **params)
                if not req.ok:
                    _LOGGER.warning("Status code %s (retry #%s) loading %s.",
                                    req.status_code, retry_num + 1, url)
                else:
                    data = io.BytesIO(req.content)
                    if data.read():
                        data.seek(0)
                        data.name = url
                        return data
                    _LOGGER.warning("Empty data (retry #%s) in %s).",
                                    retry_num + 1, url)
                retry_num += 1
            _LOGGER.warning("Can't load photo in %s after %s retries.",
                            url, retry_num)
        elif filepath is not None:
            # Load photo from file
            return open(filepath, "rb")
        else:
            _LOGGER.warning("Can't load photo. No photo found in params!")

    except (OSError, TypeError) as error:
        _LOGGER.error("Can't load photo into ByteIO: %s", error)

    return None


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Telegram bot component."""
    if not config[DOMAIN]:
        return False

    p_config = config[DOMAIN][0]
    descriptions = yield from hass.async_add_job(
        load_yaml_config_file,
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    p_type = p_config.get(CONF_PLATFORM)

    platform = yield from async_prepare_setup_platform(
        hass, config, DOMAIN, p_type)

    if platform is None:
        return

    _LOGGER.info("Setting up %s.%s", DOMAIN, p_type)
    try:
        receiver_service = yield from \
            platform.async_setup_platform(hass, p_config)
        if receiver_service is None:
            _LOGGER.error(
                "Failed to initialize Telegram bot %s", p_type)
            return False

    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Error setting up platform %s", p_type)
        return False

    notify_service = TelegramNotificationService(
        hass,
        p_config.get(CONF_API_KEY),
        p_config.get(CONF_ALLOWED_CHAT_IDS),
        p_config.get(ATTR_PARSER)
    )

    @asyncio.coroutine
    def async_send_telegram_message(service):
        """Handle sending Telegram Bot message service calls."""
        def _render_template_attr(data, attribute):
            attribute_templ = data.get(attribute)
            if attribute_templ:
                if any([isinstance(attribute_templ, vtype)
                        for vtype in [float, int, str]]):
                    data[attribute] = attribute_templ
                else:
                    attribute_templ.hass = hass
                    try:
                        data[attribute] = attribute_templ.async_render()
                    except TemplateError as exc:
                        _LOGGER.error(
                            "TemplateError in %s: %s -> %s",
                            attribute, attribute_templ.template, exc)
                        data[attribute] = attribute_templ.template

        msgtype = service.service
        kwargs = dict(service.data)
        for attribute in [ATTR_MESSAGE, ATTR_TITLE, ATTR_URL, ATTR_FILE,
                          ATTR_CAPTION, ATTR_LONGITUDE, ATTR_LATITUDE]:
            _render_template_attr(kwargs, attribute)
        _LOGGER.debug("New telegram message %s: %s", msgtype, kwargs)

        if msgtype == SERVICE_SEND_MESSAGE:
            yield from hass.async_add_job(
                partial(notify_service.send_message, **kwargs))
        elif msgtype == SERVICE_SEND_PHOTO:
            yield from hass.async_add_job(
                partial(notify_service.send_file, True, **kwargs))
        elif msgtype == SERVICE_SEND_DOCUMENT:
            yield from hass.async_add_job(
                partial(notify_service.send_file, False, **kwargs))
        elif msgtype == SERVICE_SEND_LOCATION:
            yield from hass.async_add_job(
                partial(notify_service.send_location, **kwargs))
        elif msgtype == SERVICE_ANSWER_CALLBACK_QUERY:
            yield from hass.async_add_job(
                partial(notify_service.answer_callback_query, **kwargs))
        else:
            yield from hass.async_add_job(
                partial(notify_service.edit_message, msgtype, **kwargs))

    # Register notification services
    for service_notif, schema in SERVICE_MAP.items():
        hass.services.async_register(
            DOMAIN, service_notif, async_send_telegram_message,
            descriptions.get(service_notif), schema=schema)

    return True


class TelegramNotificationService:
    """Implement the notification services for the Telegram Bot domain."""

    def __init__(self, hass, api_key, allowed_chat_ids, parser):
        """Initialize the service."""
        from telegram import Bot
        from telegram.parsemode import ParseMode

        self.allowed_chat_ids = allowed_chat_ids
        self._default_user = self.allowed_chat_ids[0]
        self._last_message_id = {user: None for user in self.allowed_chat_ids}
        self._parsers = {PARSER_HTML: ParseMode.HTML,
                         PARSER_MD: ParseMode.MARKDOWN}
        self._parse_mode = self._parsers.get(parser)
        self.bot = Bot(token=api_key)
        self.hass = hass

    def _get_msg_ids(self, msg_data, chat_id):
        """Get the message id to edit.

        This can be one of (message_id, inline_message_id) from a msg dict,
        returning a tuple.
        **You can use 'last' as message_id** to edit
        the last sended message in the chat_id.
        """
        message_id = inline_message_id = None
        if ATTR_MESSAGEID in msg_data:
            message_id = msg_data[ATTR_MESSAGEID]
            if (isinstance(message_id, str) and (message_id == 'last') and
                    (self._last_message_id[chat_id] is not None)):
                message_id = self._last_message_id[chat_id]
        else:
            inline_message_id = msg_data['inline_message_id']
        return message_id, inline_message_id

    def _get_target_chat_ids(self, target):
        """Validate chat_id targets or return default target (first).

        :param target: optional list of integers ([12234, -12345])
        :return list of chat_id targets (integers)
        """
        if target is not None:
            if isinstance(target, int):
                target = [target]
            chat_ids = [t for t in target if t in self.allowed_chat_ids]
            if chat_ids:
                return chat_ids
            _LOGGER.warning("Unallowed targets: %s, using default: %s",
                            target, self._default_user)
        return [self._default_user]

    def _get_msg_kwargs(self, data):
        """Get parameters in message data kwargs."""
        def _make_row_inline_keyboard(row_keyboard):
            """Make a list of InlineKeyboardButtons.

            It can accept:
              - a list of tuples like:
                `[(text_b1, data_callback_b1),
                (text_b2, data_callback_b2), ...]
              - a string like: `/cmd1, /cmd2, /cmd3`
              - or a string like: `text_b1:/cmd1, text_b2:/cmd2`
            """
            from telegram import InlineKeyboardButton
            buttons = []
            if isinstance(row_keyboard, str):
                for key in row_keyboard.split(","):
                    if ':/' in key:
                        # commands like: 'Label:/cmd' become ('Label', '/cmd')
                        label = key.split(':/')[0]
                        command = key[len(label) + 1:]
                        buttons.append(
                            InlineKeyboardButton(label, callback_data=command))
                    else:
                        # commands like: '/cmd' become ('CMD', '/cmd')
                        label = key.strip()[1:].upper()
                        buttons.append(
                            InlineKeyboardButton(label, callback_data=key))
            elif isinstance(row_keyboard, list):
                for entry in row_keyboard:
                    text_btn, data_btn = entry
                    buttons.append(
                        InlineKeyboardButton(text_btn, callback_data=data_btn))
            else:
                raise ValueError(str(row_keyboard))
            return buttons

        # Defaults
        params = {
            ATTR_PARSER: self._parse_mode,
            ATTR_DISABLE_NOTIF: False,
            ATTR_DISABLE_WEB_PREV: None,
            ATTR_REPLY_TO_MSGID: None,
            ATTR_REPLYMARKUP: None,
            CONF_TIMEOUT: None
        }
        if data is not None:
            if ATTR_PARSER in data:
                params[ATTR_PARSER] = self._parsers.get(
                    data[ATTR_PARSER], self._parse_mode)
            if CONF_TIMEOUT in data:
                params[CONF_TIMEOUT] = data[CONF_TIMEOUT]
            if ATTR_DISABLE_NOTIF in data:
                params[ATTR_DISABLE_NOTIF] = data[ATTR_DISABLE_NOTIF]
            if ATTR_DISABLE_WEB_PREV in data:
                params[ATTR_DISABLE_WEB_PREV] = data[ATTR_DISABLE_WEB_PREV]
            if ATTR_REPLY_TO_MSGID in data:
                params[ATTR_REPLY_TO_MSGID] = data[ATTR_REPLY_TO_MSGID]
            # Keyboards:
            if ATTR_KEYBOARD in data:
                from telegram import ReplyKeyboardMarkup
                keys = data.get(ATTR_KEYBOARD)
                keys = keys if isinstance(keys, list) else [keys]
                params[ATTR_REPLYMARKUP] = ReplyKeyboardMarkup(
                    [[key.strip() for key in row.split(",")] for row in keys])
            elif ATTR_KEYBOARD_INLINE in data:
                from telegram import InlineKeyboardMarkup
                keys = data.get(ATTR_KEYBOARD_INLINE)
                keys = keys if isinstance(keys, list) else [keys]
                params[ATTR_REPLYMARKUP] = InlineKeyboardMarkup(
                    [_make_row_inline_keyboard(row) for row in keys])
        return params

    def _send_msg(self, func_send, msg_error, *args_rep, **kwargs_rep):
        """Send one message."""
        from telegram.error import TelegramError
        try:
            out = func_send(*args_rep, **kwargs_rep)
            if not isinstance(out, bool) and hasattr(out, ATTR_MESSAGEID):
                chat_id = out.chat_id
                self._last_message_id[chat_id] = out[ATTR_MESSAGEID]
                _LOGGER.debug("Last message ID: %s (from chat_id %s)",
                              self._last_message_id, chat_id)
            elif not isinstance(out, bool):
                _LOGGER.warning("Update last message: out_type:%s, out=%s",
                                type(out), out)
            return out
        except TelegramError:
            _LOGGER.exception(msg_error)

    def send_message(self, message="", target=None, **kwargs):
        """Send a message to one or multiple pre-allowed chat IDs."""
        title = kwargs.get(ATTR_TITLE)
        text = '{}\n{}'.format(title, message) if title else message
        params = self._get_msg_kwargs(kwargs)
        for chat_id in self._get_target_chat_ids(target):
            _LOGGER.debug("Send message in chat ID %s with params: %s",
                          chat_id, params)
            self._send_msg(self.bot.sendMessage,
                           "Error sending message",
                           chat_id, text, **params)

    def edit_message(self, type_edit, chat_id=None, **kwargs):
        """Edit a previously sent message."""
        chat_id = self._get_target_chat_ids(chat_id)[0]
        message_id, inline_message_id = self._get_msg_ids(kwargs, chat_id)
        params = self._get_msg_kwargs(kwargs)
        _LOGGER.debug("Edit message %s in chat ID %s with params: %s",
                      message_id or inline_message_id, chat_id, params)
        if type_edit == SERVICE_EDIT_MESSAGE:
            message = kwargs.get(ATTR_MESSAGE)
            title = kwargs.get(ATTR_TITLE)
            text = '{}\n{}'.format(title, message) if title else message
            _LOGGER.debug("Editing message with ID %s.",
                          message_id or inline_message_id)
            return self._send_msg(self.bot.editMessageText,
                                  "Error editing text message",
                                  text, chat_id=chat_id, message_id=message_id,
                                  inline_message_id=inline_message_id,
                                  **params)
        elif type_edit == SERVICE_EDIT_CAPTION:
            func_send = self.bot.editMessageCaption
            params[ATTR_CAPTION] = kwargs.get(ATTR_CAPTION)
        else:
            func_send = self.bot.editMessageReplyMarkup
        return self._send_msg(func_send,
                              "Error editing message attributes",
                              chat_id=chat_id, message_id=message_id,
                              inline_message_id=inline_message_id,
                              **params)

    def answer_callback_query(self, message, callback_query_id,
                              show_alert=False, **kwargs):
        """Answer a callback originated with a press in an inline keyboard."""
        params = self._get_msg_kwargs(kwargs)
        _LOGGER.debug("Answer callback query with callback ID %s: %s, "
                      "alert: %s.", callback_query_id, message, show_alert)
        self._send_msg(self.bot.answerCallbackQuery,
                       "Error sending answer callback query",
                       callback_query_id,
                       text=message, show_alert=show_alert, **params)

    def send_file(self, is_photo=True, target=None, **kwargs):
        """Send a photo or a document."""
        params = self._get_msg_kwargs(kwargs)
        caption = kwargs.get(ATTR_CAPTION)
        func_send = self.bot.sendPhoto if is_photo else self.bot.sendDocument
        file_content = load_data(
            url=kwargs.get(ATTR_URL),
            filepath=kwargs.get(ATTR_FILE),
            username=kwargs.get(ATTR_USERNAME),
            password=kwargs.get(ATTR_PASSWORD),
            authentication=kwargs.get(ATTR_AUTHENTICATION),
        )
        if file_content:
            for chat_id in self._get_target_chat_ids(target):
                _LOGGER.debug("Send file to chat ID %s. Caption: %s.",
                              chat_id, caption)
                self._send_msg(func_send, "Error sending file",
                               chat_id, file_content,
                               caption=caption, **params)
                file_content.seek(0)
        else:
            _LOGGER.error("Can't send file with kwargs: %s", kwargs)

    def send_location(self, latitude, longitude, target=None, **kwargs):
        """Send a location."""
        latitude = float(latitude)
        longitude = float(longitude)
        params = self._get_msg_kwargs(kwargs)
        for chat_id in self._get_target_chat_ids(target):
            _LOGGER.debug("Send location %s/%s to chat ID %s.",
                          latitude, longitude, chat_id)
            self._send_msg(self.bot.sendLocation,
                           "Error sending location",
                           chat_id=chat_id,
                           latitude=latitude, longitude=longitude, **params)


class BaseTelegramBotEntity:
    """The base class for the telegram bot."""

    def __init__(self, hass, allowed_chat_ids):
        """Initialize the bot base class."""
        self.allowed_chat_ids = allowed_chat_ids
        self.hass = hass

    def _get_message_data(self, msg_data):
        """Return boolean msg_data_is_ok and dict msg_data."""
        if not msg_data:
            return False, None
        bad_fields = ('text' not in msg_data and
                      'data' not in msg_data and
                      'chat' not in msg_data)
        if bad_fields or 'from' not in msg_data:
            # Message is not correct.
            _LOGGER.error("Incoming message does not have required data (%s)",
                          msg_data)
            return False, None

        if (msg_data['from'].get('id') not in self.allowed_chat_ids or
                ('chat' in msg_data and
                 msg_data['chat'].get('id') not in self.allowed_chat_ids)):
            # Origin is not allowed.
            _LOGGER.error("Incoming message is not allowed (%s)", msg_data)
            return True, None

        data = {
            ATTR_USER_ID: msg_data['from']['id'],
            ATTR_FROM_FIRST: msg_data['from']['first_name']
        }
        if 'last_name' in msg_data['from']:
            data[ATTR_FROM_LAST] = msg_data['from']['last_name']
        if 'chat' in msg_data:
            data[ATTR_CHAT_ID] = msg_data['chat']['id']

        return True, data

    def process_message(self, data):
        """Check for basic message rules and fire an event if message is ok."""
        if ATTR_MSG in data or ATTR_EDITED_MSG in data:
            event = EVENT_TELEGRAM_COMMAND
            if ATTR_MSG in data:
                data = data.get(ATTR_MSG)
            else:
                data = data.get(ATTR_EDITED_MSG)
            message_ok, event_data = self._get_message_data(data)
            if event_data is None:
                return message_ok

            if 'text' in data:
                if data['text'][0] == '/':
                    pieces = data['text'].split(' ')
                    event_data[ATTR_COMMAND] = pieces[0]
                    event_data[ATTR_ARGS] = pieces[1:]
                else:
                    event_data[ATTR_TEXT] = data['text']
                    event = EVENT_TELEGRAM_TEXT
            else:
                _LOGGER.warning("Message without text data received: %s", data)
                event_data[ATTR_TEXT] = str(data)
                event = EVENT_TELEGRAM_TEXT

            self.hass.bus.async_fire(event, event_data)
            return True
        elif ATTR_CALLBACK_QUERY in data:
            event = EVENT_TELEGRAM_CALLBACK
            data = data.get(ATTR_CALLBACK_QUERY)
            message_ok, event_data = self._get_message_data(data)
            if event_data is None:
                return message_ok

            event_data[ATTR_DATA] = data[ATTR_DATA]
            event_data[ATTR_MSG] = data[ATTR_MSG]
            event_data[ATTR_CHAT_INSTANCE] = data[ATTR_CHAT_INSTANCE]
            event_data[ATTR_MSGID] = data[ATTR_MSGID]

            self.hass.bus.async_fire(event, event_data)
            return True
        else:
            _LOGGER.warning("Message with unknown data received: %s", data)
            return True
