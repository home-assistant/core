"""The Hangouts Bot."""
import io
import logging
import asyncio
import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import dispatcher, intent

from .const import (
    ATTR_MESSAGE, ATTR_TARGET, ATTR_DATA, CONF_CONVERSATIONS, DOMAIN,
    EVENT_HANGOUTS_CONNECTED, EVENT_HANGOUTS_CONVERSATIONS_CHANGED,
    EVENT_HANGOUTS_DISCONNECTED, EVENT_HANGOUTS_MESSAGE_RECEIVED,
    CONF_MATCHERS, CONF_CONVERSATION_ID,
    CONF_CONVERSATION_NAME, EVENT_HANGOUTS_CONVERSATIONS_RESOLVED, INTENT_HELP)

_LOGGER = logging.getLogger(__name__)


class HangoutsBot:
    """The Hangouts Bot."""

    def __init__(self, hass, refresh_token, intents,
                 default_convs, error_suppressed_convs):
        """Set up the client."""
        self.hass = hass
        self._connected = False

        self._refresh_token = refresh_token

        self._intents = intents
        self._conversation_intents = None

        self._client = None
        self._user_list = None
        self._conversation_list = None
        self._default_convs = default_convs
        self._default_conv_ids = None
        self._error_suppressed_convs = error_suppressed_convs
        self._error_suppressed_conv_ids = None

        dispatcher.async_dispatcher_connect(
            self.hass, EVENT_HANGOUTS_MESSAGE_RECEIVED,
            self._async_handle_conversation_message)

    def _resolve_conversation_id(self, obj):
        if CONF_CONVERSATION_ID in obj:
            return obj[CONF_CONVERSATION_ID]
        if CONF_CONVERSATION_NAME in obj:
            conv = self._resolve_conversation_name(obj[CONF_CONVERSATION_NAME])
            if conv is not None:
                return conv.id_
        return None

    def _resolve_conversation_name(self, name):
        for conv in self._conversation_list.get_all():
            if conv.name == name:
                return conv
        return None

    def async_update_conversation_commands(self):
        """Refresh the commands for every conversation."""
        self._conversation_intents = {}

        for intent_type, data in self._intents.items():
            if data.get(CONF_CONVERSATIONS):
                conversations = []
                for conversation in data.get(CONF_CONVERSATIONS):
                    conv_id = self._resolve_conversation_id(conversation)
                    if conv_id is not None:
                        conversations.append(conv_id)
                data['_' + CONF_CONVERSATIONS] = conversations
            elif self._default_conv_ids:
                data['_' + CONF_CONVERSATIONS] = self._default_conv_ids
            else:
                data['_' + CONF_CONVERSATIONS] = \
                    [conv.id_ for conv in self._conversation_list.get_all()]

            for conv_id in data['_' + CONF_CONVERSATIONS]:
                if conv_id not in self._conversation_intents:
                    self._conversation_intents[conv_id] = {}

                self._conversation_intents[conv_id][intent_type] = data

        try:
            self._conversation_list.on_event.remove_observer(
                self._async_handle_conversation_event)
        except ValueError:
            pass
        self._conversation_list.on_event.add_observer(
            self._async_handle_conversation_event)

    def async_resolve_conversations(self, _):
        """Resolve the list of default and error suppressed conversations."""
        self._default_conv_ids = []
        self._error_suppressed_conv_ids = []

        for conversation in self._default_convs:
            conv_id = self._resolve_conversation_id(conversation)
            if conv_id is not None:
                self._default_conv_ids.append(conv_id)

        for conversation in self._error_suppressed_convs:
            conv_id = self._resolve_conversation_id(conversation)
            if conv_id is not None:
                self._error_suppressed_conv_ids.append(conv_id)
        dispatcher.async_dispatcher_send(self.hass,
                                         EVENT_HANGOUTS_CONVERSATIONS_RESOLVED)

    async def _async_handle_conversation_event(self, event):
        from hangups import ChatMessageEvent
        if isinstance(event, ChatMessageEvent):
            dispatcher.async_dispatcher_send(self.hass,
                                             EVENT_HANGOUTS_MESSAGE_RECEIVED,
                                             event.conversation_id,
                                             event.user_id, event)

    async def _async_handle_conversation_message(self,
                                                 conv_id, user_id, event):
        """Handle a message sent to a conversation."""
        user = self._user_list.get_user(user_id)
        if user.is_self:
            return
        message = event.text

        _LOGGER.debug("Handling message '%s' from %s",
                      message, user.full_name)

        intents = self._conversation_intents.get(conv_id)
        if intents is not None:
            is_error = False
            try:
                intent_result = await self._async_process(intents, message,
                                                          conv_id)
            except (intent.UnknownIntent, intent.IntentHandleError) as err:
                is_error = True
                intent_result = intent.IntentResponse()
                intent_result.async_set_speech(str(err))

            if intent_result is None:
                is_error = True
                intent_result = intent.IntentResponse()
                intent_result.async_set_speech(
                    "Sorry, I didn't understand that")

            message = intent_result.as_dict().get('speech', {})\
                .get('plain', {}).get('speech')

            if (message is not None) and not (
                    is_error and conv_id in self._error_suppressed_conv_ids):
                await self._async_send_message(
                    [{'text': message, 'parse_str': True}],
                    [{CONF_CONVERSATION_ID: conv_id}],
                    None)

    async def _async_process(self, intents, text, conv_id):
        """Detect a matching intent."""
        for intent_type, data in intents.items():
            for matcher in data.get(CONF_MATCHERS, []):
                match = matcher.match(text)

                if not match:
                    continue
                if intent_type == INTENT_HELP:
                    return await self.hass.helpers.intent.async_handle(
                        DOMAIN, intent_type,
                        {'conv_id': {'value': conv_id}}, text)

                return await self.hass.helpers.intent.async_handle(
                    DOMAIN, intent_type,
                    {key: {'value': value}
                     for key, value in match.groupdict().items()}, text)

    async def async_connect(self):
        """Login to the Google Hangouts."""
        from .hangups_utils import HangoutsRefreshToken, HangoutsCredentials

        from hangups import Client
        from hangups import get_auth
        session = await self.hass.async_add_executor_job(
            get_auth, HangoutsCredentials(None, None, None),
            HangoutsRefreshToken(self._refresh_token))

        self._client = Client(session)
        self._client.on_connect.add_observer(self._on_connect)
        self._client.on_disconnect.add_observer(self._on_disconnect)

        self.hass.loop.create_task(self._client.connect())

    def _on_connect(self):
        _LOGGER.debug('Connected!')
        self._connected = True
        dispatcher.async_dispatcher_send(self.hass, EVENT_HANGOUTS_CONNECTED)

    async def _on_disconnect(self):
        """Handle disconnecting."""
        if self._connected:
            _LOGGER.debug('Connection lost! Reconnect...')
            await self.async_connect()
        else:
            dispatcher.async_dispatcher_send(self.hass,
                                             EVENT_HANGOUTS_DISCONNECTED)

    async def async_disconnect(self):
        """Disconnect the client if it is connected."""
        if self._connected:
            self._connected = False
            await self._client.disconnect()

    async def async_handle_hass_stop(self, _):
        """Run once when Home Assistant stops."""
        await self.async_disconnect()

    async def _async_send_message(self, message, targets, data):
        conversations = []
        for target in targets:
            conversation = None
            if CONF_CONVERSATION_ID in target:
                conversation = self._conversation_list.get(
                    target[CONF_CONVERSATION_ID])
            elif CONF_CONVERSATION_NAME in target:
                conversation = self._resolve_conversation_name(
                    target[CONF_CONVERSATION_NAME])
            if conversation is not None:
                conversations.append(conversation)

        if not conversations:
            return False

        from hangups import ChatMessageSegment, hangouts_pb2
        messages = []
        for segment in message:
            if messages:
                messages.append(ChatMessageSegment('',
                                                   segment_type=hangouts_pb2.
                                                   SEGMENT_TYPE_LINE_BREAK))
            if 'parse_str' in segment and segment['parse_str']:
                messages.extend(ChatMessageSegment.from_str(segment['text']))
            else:
                if 'parse_str' in segment:
                    del segment['parse_str']
                messages.append(ChatMessageSegment(**segment))

        image_file = None
        if data:
            if data.get('image_url'):
                uri = data.get('image_url')
                try:
                    websession = async_get_clientsession(self.hass)
                    async with websession.get(uri, timeout=5) as response:
                        if response.status != 200:
                            _LOGGER.error(
                                'Fetch image failed, %s, %s',
                                response.status,
                                response
                            )
                            image_file = None
                        else:
                            image_data = await response.read()
                            image_file = io.BytesIO(image_data)
                            image_file.name = "image.png"
                except (asyncio.TimeoutError, aiohttp.ClientError) as error:
                    _LOGGER.error(
                        'Failed to fetch image, %s',
                        type(error)
                    )
                    image_file = None
            elif data.get('image_file'):
                uri = data.get('image_file')
                if self.hass.config.is_allowed_path(uri):
                    try:
                        image_file = open(uri, 'rb')
                    except IOError as error:
                        _LOGGER.error(
                            'Image file I/O error(%s): %s',
                            error.errno,
                            error.strerror
                        )
                else:
                    _LOGGER.error('Path "%s" not allowed', uri)

        if not messages:
            return False
        for conv in conversations:
            await conv.send_message(messages, image_file)

    async def _async_list_conversations(self):
        import hangups
        self._user_list, self._conversation_list = \
            (await hangups.build_user_conversation_list(self._client))
        conversations = {}
        for i, conv in enumerate(self._conversation_list.get_all()):
            users_in_conversation = []
            for user in conv.users:
                users_in_conversation.append(user.full_name)
            conversations[str(i)] = {CONF_CONVERSATION_ID: str(conv.id_),
                                     CONF_CONVERSATION_NAME: conv.name,
                                     'users': users_in_conversation}

        self.hass.states.async_set("{}.conversations".format(DOMAIN),
                                   len(self._conversation_list.get_all()),
                                   attributes=conversations)
        dispatcher.async_dispatcher_send(self.hass,
                                         EVENT_HANGOUTS_CONVERSATIONS_CHANGED,
                                         conversations)

    async def async_handle_send_message(self, service):
        """Handle the send_message service."""
        await self._async_send_message(service.data[ATTR_MESSAGE],
                                       service.data[ATTR_TARGET],
                                       service.data.get(ATTR_DATA, {}))

    async def async_handle_update_users_and_conversations(self, _=None):
        """Handle the update_users_and_conversations service."""
        await self._async_list_conversations()

    async def async_handle_reconnect(self, _=None):
        """Handle the reconnect service."""
        await self.async_disconnect()
        await self.async_connect()

    def get_intents(self, conv_id):
        """Return the intents for a specific conversation."""
        return self._conversation_intents.get(conv_id)
