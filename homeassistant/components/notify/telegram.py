"""
Telegram platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.telegram/
"""
import io
import logging
from urllib.error import HTTPError

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_DATA, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import (
    CONF_API_KEY, CONF_TIMEOUT, ATTR_LOCATION, ATTR_LATITUDE, ATTR_LONGITUDE)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['python-telegram-bot==5.3.0']

ATTR_PARSER = 'parse_mode'
PARSER_MD = 'markdown'
PARSER_HTML = 'html'
ATTR_DISABLE_NOTIF = 'disable_notification'
ATTR_DISABLE_WEB_PREV = 'disable_web_page_preview'
ATTR_REPLY_TO_MSGID = 'reply_to_message_id'

ATTR_PHOTO = 'photo'
ATTR_KEYBOARD = 'keyboard'
ATTR_KEYBOARD_INLINE = 'inline_keyboard'
ATTR_DOCUMENT = 'document'
ATTR_CAPTION = 'caption'
ATTR_CALLBACK_QUERY = 'callback_query'
ATTR_EDIT_MSG = 'edit_message'
ATTR_EDIT_CAPTION = 'edit_caption'
ATTR_EDIT_REPLYMARKUP = 'edit_replymarkup'
ATTR_URL = 'url'
ATTR_FILE = 'file'
ATTR_USERNAME = 'username'
ATTR_PASSWORD = 'password'
ATTR_TARGET = 'target'

CONF_USER_ID = 'user_id'
CONF_CHAT_ID = 'chat_id'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_CHAT_ID, default=None): cv.string,
    vol.Optional(CONF_USER_ID, default=None):
        cv.ordered_dict(cv.positive_int, cv.string),
    vol.Optional(ATTR_PARSER, default=PARSER_MD): cv.string,
})


# noinspection PyUnusedLocal
def get_service(hass, config, discovery_info=None):
    """Get the Telegram notification service."""
    from telegram import Bot

    try:
        chat_id = config.get(CONF_CHAT_ID)
        if chat_id is not None:
            user_id_array = {'User1': chat_id}
        else:
            user_id_array = config.get(CONF_USER_ID)
        api_key = config.get(CONF_API_KEY)
        default_parser = config.get(ATTR_PARSER)
        bot = Bot(token=api_key)
        username = bot.getMe()['username']
        _LOGGER.info("Telegram bot is '@{}', users allowed are: {}, default={}"
                     .format(username, user_id_array, list(user_id_array)[0]))
    except HTTPError:
        _LOGGER.error("Please check your access token")
        return None

    return TelegramNotificationService(api_key, user_id_array, default_parser)


def load_data(url=None, file=None, username=None, password=None):
    """Load photo/document into ByteIO/File container from a source."""
    try:
        if url is not None:
            # load photo from url
            if username is not None and password is not None:
                req = requests.get(url, auth=(username, password), timeout=15)
            else:
                req = requests.get(url, timeout=15)
            return io.BytesIO(req.content)

        elif file is not None:
            # load photo from file
            return open(file, "rb")
        else:
            _LOGGER.warning("Can't load photo no photo found in params!")

    except OSError as error:
        _LOGGER.error("Can't load photo into ByteIO: %s", error)

    return None


class TelegramNotificationService(BaseNotificationService):
    """Implement the notification service for Telegram."""

    def __init__(self, api_key, user_id_array, parser):
        """Initialize the service."""
        from telegram import Bot
        from telegram.parsemode import ParseMode

        self._api_key = api_key
        self._default_user = None
        self._users = {}
        for i, (dev_id, user_id) in enumerate(user_id_array.items()):
            if i == 0:
                self._default_user = user_id
            self._users[user_id] = dev_id
        self._parsers = {PARSER_HTML: ParseMode.HTML,
                         PARSER_MD: ParseMode.MARKDOWN}
        self._parse_mode = self._parsers.get(parser)
        # last_msg_cache:
        self._last_message_id = {user: None for user in self._users.keys()}
        self.bot = Bot(token=self._api_key)

    def _get_msg_ids(self, msg_data, chat_id):
        """Get one of (message_id, inline_message_id) from a msg dict,
        returning a tuple. You can use 'last' as message_id to edit
        the last sended message in the chat_id."""
        message_id = inline_message_id = None
        if 'message_id' in msg_data:
            message_id = msg_data['message_id']
            if (isinstance(message_id, str) and (message_id == 'last') and
                    (self._last_message_id[chat_id] is not None)):
                message_id = self._last_message_id[chat_id]
        else:
            inline_message_id = msg_data['inline_message_id']
        return message_id, inline_message_id

    def _get_target_chat_ids(self, target):
        """Validate chat_id targets, which come as list of strings (['12234'])
        or get the default chat_id. Returns list of chat_id targets (integers).
        """
        if target is not None:
            if isinstance(target, int):
                if target in self._users:
                    return [target]
                _LOGGER.warning('BAD TARGET "{}", using default: {}'
                                .format(target, self._default_user))
            else:
                try:
                    chat_ids = list(filter(lambda x: x in self._users,
                                           [int(t) for t in target]))
                    if len(chat_ids) > 0:
                        return chat_ids
                    _LOGGER.warning('ALL BAD TARGETS: "{}"'.format(target))
                except (ValueError, TypeError):
                    _LOGGER.warning('BAD TARGET DATA "{}", using default: {}'
                                    .format(target, self._default_user))
        return [self._default_user]

    def _get_msg_kwargs(self, data):
        """Get parameters in data kwargs"""

        def _make_row_of_kb(row_keyboard):
            """Espera un str de texto en botones separados por comas,
            o una lista de tuplas de la forma: [(texto_b1, data_callback_b1),
                                                (texto_b2, data_callback_b2), ]
            Devuelve una lista de InlineKeyboardButton.
            """
            from telegram import InlineKeyboardButton
            if isinstance(row_keyboard, str):
                return [InlineKeyboardButton(
                    key.strip()[1:].upper(),
                    callback_data=key)
                        for key in row_keyboard.split(",")]
            elif isinstance(row_keyboard, list):
                return [InlineKeyboardButton(
                    text_btn, callback_data=data_btn)
                        for text_btn, data_btn in row_keyboard]
            else:
                raise ValueError(str(row_keyboard))

        # defaults
        params = dict(parse_mode=self._parse_mode,
                      disable_notification=False,
                      disable_web_page_preview=None,
                      reply_to_message_id=None,
                      reply_markup=None,
                      timeout=None)
        if data is not None:
            if ATTR_PARSER in data:
                params['parse_mode'] = self._parsers.get(data[ATTR_PARSER],
                                                         self._parse_mode)
            if CONF_TIMEOUT in data:
                params['timeout'] = data[CONF_TIMEOUT]
            if ATTR_DISABLE_NOTIF in data:
                params['disable_notification'] = data[ATTR_DISABLE_NOTIF]
            if ATTR_DISABLE_WEB_PREV in data:
                params[ATTR_DISABLE_WEB_PREV] = data[ATTR_DISABLE_WEB_PREV]
            if ATTR_REPLY_TO_MSGID in data:
                params[ATTR_REPLY_TO_MSGID] = data[ATTR_REPLY_TO_MSGID]
            # Keyboards:
            if ATTR_KEYBOARD in data:
                from telegram import ReplyKeyboardMarkup
                keys = data.get(ATTR_KEYBOARD)
                keys = keys if isinstance(keys, list) else [keys]
                params['reply_markup'] = ReplyKeyboardMarkup(
                    [[key.strip() for key in row.split(",")] for row in keys])
            elif ATTR_KEYBOARD_INLINE in data:
                from telegram import InlineKeyboardMarkup
                keys = data.get(ATTR_KEYBOARD_INLINE)
                keys = keys if isinstance(keys, list) else [keys]
                params['reply_markup'] = InlineKeyboardMarkup(
                    [_make_row_of_kb(row) for row in keys])
        return params

    def _send_msg(self, func_send, msg_error, *args_rep, **kwargs_rep):
        """Send one message."""
        from telegram.error import TelegramError
        try:
            out = func_send(*args_rep, **kwargs_rep)
            if not isinstance(out, bool) and hasattr(out, 'message_id'):
                chat_id = out.chat_id
                self._last_message_id[chat_id] = out.message_id
                _LOGGER.debug('LAST MSG ID: {} (from chat_id {})'
                              .format(self._last_message_id, chat_id))
            elif not isinstance(out, bool):
                _LOGGER.warning('UPDATE LAST MSG??: out_type:{}, out={}'
                                .format(type(out), out))
            return out
        except TelegramError:
            _LOGGER.exception(msg_error)

    def send_message(self, message="", target=None, **kwargs):
        """Send a message to one or multiple pre-defined users."""
        title = kwargs.get(ATTR_TITLE)
        data = kwargs.get(ATTR_DATA)
        text = '{}\n{}'.format(title, message) if title else message
        params = self._get_msg_kwargs(data)
        for chat_id in self._get_target_chat_ids(target):
            self._dispatch_msg(text, chat_id, params, data)

    def _dispatch_msg(self, text, chat_id, params, data=None):
        """Dispatch one message to a chat_id."""
        if data is not None:
            if ATTR_PHOTO in data:
                photos = data.get(ATTR_PHOTO)
                photos = photos if isinstance(photos, list) else [photos]
                for photo_data in photos:
                    self.send_photo(photo_data, chat_id=chat_id, **params)
                return
            elif ATTR_LOCATION in data:
                return self.send_location(data.get(ATTR_LOCATION),
                                          chat_id=chat_id, **params)
            elif ATTR_DOCUMENT in data:
                return self.send_document(data.get(ATTR_DOCUMENT),
                                          chat_id=chat_id, **params)
            elif ATTR_CALLBACK_QUERY in data:
                # send answer to callback query
                callback_data = data.get(ATTR_CALLBACK_QUERY)
                callback_query_id = callback_data.pop('callback_query_id')
                _LOGGER.debug('sending answer_callback_query id {}: "{}" ({})'
                              .format(callback_query_id, text, callback_data))
                return self._send_msg(self.bot.answerCallbackQuery,
                                      "Error sending answer to callback query",
                                      callback_query_id,
                                      text=text, **callback_data)
            elif ATTR_EDIT_MSG in data:
                # edit existent text message
                message_id, inline_message_id = self._get_msg_ids(
                    data.get(ATTR_EDIT_MSG), chat_id)
                _LOGGER.debug('editing message w/id {}: "{}" ({})'
                              .format(message_id or inline_message_id, text,
                                      data.get(ATTR_EDIT_MSG)))
                return self._send_msg(self.bot.editMessageText,
                                      "Error editing text message",
                                      text,
                                      chat_id=chat_id, message_id=message_id,
                                      inline_message_id=inline_message_id,
                                      **params)
            elif ATTR_EDIT_CAPTION in data:
                # edit existent caption
                caption = data.get(ATTR_EDIT_CAPTION)['caption']
                message_id, inline_message_id = self._get_msg_ids(
                    data.get(ATTR_EDIT_CAPTION), chat_id)
                _LOGGER.debug('editing message caption w/id {}: "{}" ({})'
                              .format(message_id or inline_message_id, text,
                                      data.get(ATTR_EDIT_CAPTION)))
                return self._send_msg(self.bot.editMessageCaption,
                                      "Error editing message caption",
                                      chat_id=chat_id, message_id=message_id,
                                      inline_message_id=inline_message_id,
                                      caption=caption, **params)
            elif ATTR_EDIT_REPLYMARKUP in data:
                # edit existent replymarkup (like the keyboard)
                message_id, inline_message_id = self._get_msg_ids(
                    data.get(ATTR_EDIT_REPLYMARKUP), chat_id)
                _LOGGER.debug('editing reply_markup w/id {}: "{}" ({})'
                              .format(message_id or inline_message_id, text,
                                      data.get(ATTR_EDIT_REPLYMARKUP)))
                return self._send_msg(self.bot.editMessageReplyMarkup,
                                      "Error editing reply_markup",
                                      chat_id=chat_id, message_id=message_id,
                                      inline_message_id=inline_message_id,
                                      **params)
        # send text message
        _LOGGER.debug('sending message to chat_id: "{}"'.format(chat_id))
        return self._send_msg(self.bot.sendMessage,
                              "Error sending message",
                              chat_id, text, **params)

    def send_photo(self, data, chat_id=None, **kwargs):
        """Send a photo."""
        caption = data.get(ATTR_CAPTION)

        # send photo
        photo = load_data(
            url=data.get(ATTR_URL),
            file=data.get(ATTR_FILE),
            username=data.get(ATTR_USERNAME),
            password=data.get(ATTR_PASSWORD),
        )
        return self._send_msg(self.bot.sendPhoto,
                              "Error sending photo",
                              chat_id, photo,
                              caption=caption, **kwargs)

    def send_document(self, data, chat_id=None, **kwargs):
        """Send a document."""
        caption = data.get(ATTR_CAPTION)

        # send document
        document = load_data(
            url=data.get(ATTR_URL),
            file=data.get(ATTR_FILE),
            username=data.get(ATTR_USERNAME),
            password=data.get(ATTR_PASSWORD),
        )
        return self._send_msg(self.bot.sendDocument,
                              "Error sending document",
                              chat_id, document,
                              caption=caption, **kwargs)

    def send_location(self, gps, chat_id=None, **kwargs):
        """Send a location."""
        latitude = float(gps.get(ATTR_LATITUDE, 0.0))
        longitude = float(gps.get(ATTR_LONGITUDE, 0.0))

        # send location
        return self._send_msg(self.bot.sendLocation,
                              "Error sending location",
                              chat_id=chat_id,
                              latitude=latitude, longitude=longitude,
                              **kwargs)
