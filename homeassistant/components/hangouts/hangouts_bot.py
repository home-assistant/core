"""The Hangouts Bot."""
import logging
import re

from homeassistant.helpers import dispatcher

from .const import (
    ATTR_MESSAGE, ATTR_TARGET, CONF_CONVERSATIONS, CONF_EXPRESSION, CONF_NAME,
    CONF_WORD, DOMAIN, EVENT_HANGOUTS_COMMAND, EVENT_HANGOUTS_CONNECTED,
    EVENT_HANGOUTS_CONVERSATIONS_CHANGED, EVENT_HANGOUTS_DISCONNECTED)

_LOGGER = logging.getLogger(__name__)


class HangoutsBot:
    """The Hangouts Bot."""

    def __init__(self, hass, refresh_token, commands):
        """Set up the client."""
        self.hass = hass
        self._connected = False

        self._refresh_token = refresh_token

        self._commands = commands

        self._word_commands = None
        self._expression_commands = None
        self._client = None
        self._user_list = None
        self._conversation_list = None

    def _resolve_conversation_name(self, name):
        for conv in self._conversation_list.get_all():
            if conv.name == name:
                return conv
        return None

    def async_update_conversation_commands(self, _):
        """Refresh the commands for every conversation."""
        self._word_commands = {}
        self._expression_commands = {}

        for command in self._commands:
            if command.get(CONF_CONVERSATIONS):
                conversations = []
                for conversation in command.get(CONF_CONVERSATIONS):
                    if 'id' in conversation:
                        conversations.append(conversation['id'])
                    elif 'name' in conversation:
                        conversations.append(self._resolve_conversation_name(
                            conversation['name']).id_)
                command['_' + CONF_CONVERSATIONS] = conversations
            else:
                command['_' + CONF_CONVERSATIONS] = \
                    [conv.id_ for conv in self._conversation_list.get_all()]

            if command.get(CONF_WORD):
                for conv_id in command['_' + CONF_CONVERSATIONS]:
                    if conv_id not in self._word_commands:
                        self._word_commands[conv_id] = {}
                    word = command[CONF_WORD].lower()
                    self._word_commands[conv_id][word] = command
            elif command.get(CONF_EXPRESSION):
                command['_' + CONF_EXPRESSION] = re.compile(
                    command.get(CONF_EXPRESSION))

                for conv_id in command['_' + CONF_CONVERSATIONS]:
                    if conv_id not in self._expression_commands:
                        self._expression_commands[conv_id] = []
                    self._expression_commands[conv_id].append(command)

        try:
            self._conversation_list.on_event.remove_observer(
                self._handle_conversation_event)
        except ValueError:
            pass
        self._conversation_list.on_event.add_observer(
            self._handle_conversation_event)

    def _handle_conversation_event(self, event):
        from hangups import ChatMessageEvent
        if event.__class__ is ChatMessageEvent:
            self._handle_conversation_message(
                event.conversation_id, event.user_id, event)

    def _handle_conversation_message(self, conv_id, user_id, event):
        """Handle a message sent to a conversation."""
        user = self._user_list.get_user(user_id)
        if user.is_self:
            return

        _LOGGER.debug("Handling message '%s' from %s",
                      event.text, user.full_name)

        event_data = None

        pieces = event.text.split(' ')
        cmd = pieces[0].lower()
        command = self._word_commands.get(conv_id, {}).get(cmd)
        if command:
            event_data = {
                'command': command[CONF_NAME],
                'conversation_id': conv_id,
                'user_id': user_id,
                'user_name': user.full_name,
                'data': pieces[1:]
            }
        else:
            # After single-word commands, check all regex commands in the room
            for command in self._expression_commands.get(conv_id, []):
                match = command['_' + CONF_EXPRESSION].match(event.text)
                if not match:
                    continue
                event_data = {
                    'command': command[CONF_NAME],
                    'conversation_id': conv_id,
                    'user_id': user_id,
                    'user_name': user.full_name,
                    'data': match.groupdict()
                }
        if event_data is not None:
            self.hass.bus.fire(EVENT_HANGOUTS_COMMAND, event_data)

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

    def _on_disconnect(self):
        """Handle disconnecting."""
        _LOGGER.debug('Connection lost!')
        self._connected = False
        dispatcher.async_dispatcher_send(self.hass,
                                         EVENT_HANGOUTS_DISCONNECTED)

    async def async_disconnect(self):
        """Disconnect the client if it is connected."""
        if self._connected:
            await self._client.disconnect()

    async def async_handle_hass_stop(self, _):
        """Run once when Home Assistant stops."""
        await self.async_disconnect()

    async def _async_send_message(self, message, targets):
        conversations = []
        for target in targets:
            conversation = None
            if 'id' in target:
                conversation = self._conversation_list.get(target['id'])
            elif 'name' in target:
                conversation = self._resolve_conversation_name(target['name'])
            if conversation is not None:
                conversations.append(conversation)

        if not conversations:
            return False

        from hangups import ChatMessageSegment, hangouts_pb2
        messages = []
        for segment in message:
            if 'parse_str' in segment and segment['parse_str']:
                messages.extend(ChatMessageSegment.from_str(segment['text']))
            else:
                if 'parse_str' in segment:
                    del segment['parse_str']
                messages.append(ChatMessageSegment(**segment))
            messages.append(ChatMessageSegment('',
                                               segment_type=hangouts_pb2.
                                               SEGMENT_TYPE_LINE_BREAK))

        if not messages:
            return False
        for conv in conversations:
            await conv.send_message(messages)

    async def _async_list_conversations(self):
        import hangups
        self._user_list, self._conversation_list = \
            (await hangups.build_user_conversation_list(self._client))
        users = {}
        conversations = {}
        for user in self._user_list.get_all():
            users[str(user.id_.chat_id)] = {'full_name': user.full_name,
                                            'is_self': user.is_self}

        for conv in self._conversation_list.get_all():
            users_in_conversation = {}
            for user in conv.users:
                users_in_conversation[str(user.id_.chat_id)] = \
                    {'full_name': user.full_name, 'is_self': user.is_self}
            conversations[str(conv.id_)] = \
                {'name': conv.name, 'users': users_in_conversation}

        self.hass.states.async_set("{}.users".format(DOMAIN),
                                   len(self._user_list.get_all()),
                                   attributes=users)
        self.hass.states.async_set("{}.conversations".format(DOMAIN),
                                   len(self._conversation_list.get_all()),
                                   attributes=conversations)
        dispatcher.async_dispatcher_send(self.hass,
                                         EVENT_HANGOUTS_CONVERSATIONS_CHANGED,
                                         conversations)

    async def async_handle_send_message(self, service):
        """Handle the send_message service."""
        await self._async_send_message(service.data[ATTR_MESSAGE],
                                       service.data[ATTR_TARGET])

    async def async_handle_update_users_and_conversations(self, _=None):
        """Handle the update_users_and_conversations service."""
        await self._async_list_conversations()
