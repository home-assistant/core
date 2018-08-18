"""
The hangouts bot component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/matrix/
"""
import logging
import os

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (ATTR_TARGET, ATTR_MESSAGE)
from homeassistant.const import (CONF_EMAIL,
                                 CONF_PASSWORD,
                                 CONF_NAME,
                                 EVENT_HOMEASSISTANT_STOP)

REQUIREMENTS = ['hangups==0.4.5']

_LOGGER = logging.getLogger(__name__)

SESSION_FILE = '.hangouts.conf'

CONF_CONVERSATIONS = 'conversations'
CONF_COMMANDS = 'commands'
CONF_WORD = 'word'
CONF_EXPRESSION = 'expression'

EVENT_HANGOUTS_COMMAND = 'hangouts_command'

EVENT_HANGOUTS_CONNECTED = 'hangouts_connected'
EVENT_HANGOUTS_USERS_CHANGED = 'hangouts_users_changed'
EVENT_HANGOUTS_CONVERSATIONS_CHANGED = 'hangouts_conversations_changed'

CONF_CONVERSATION_ID = 'id'
CONF_CONVERSATION_NAME = 'name'

DOMAIN = 'hangouts'

TARGETS_SCHEMA = vol.All(
    vol.Schema({
        vol.Exclusive(CONF_CONVERSATION_ID, 'id'): cv.string,
        vol.Exclusive(CONF_CONVERSATION_NAME, 'id'): cv.string
    }),
    cv.has_at_least_one_key(CONF_CONVERSATION_ID, CONF_CONVERSATION_NAME)
)
MESSAGE_SEGMENT_SCHEMA = vol.Schema({
    vol.Required('text'): cv.string,
    vol.Optional('is_bold'): cv.boolean,
    vol.Optional('is_italic'): cv.boolean,
    vol.Optional('is_strikethrough'): cv.boolean,
    vol.Optional('is_underline'): cv.boolean,
    vol.Optional('parse_str'): cv.boolean,
    vol.Optional('link_target'): cv.string
})

MESSAGE_SCHEMA = vol.Schema({
    vol.Required(ATTR_TARGET): [TARGETS_SCHEMA],
    vol.Required(ATTR_MESSAGE): [MESSAGE_SEGMENT_SCHEMA]
})

COMMAND_SCHEMA = vol.All(
    # Basic Schema
    vol.Schema({
        vol.Exclusive(CONF_WORD, 'trigger'): cv.string,
        vol.Exclusive(CONF_EXPRESSION, 'trigger'): cv.is_regex,
        vol.Required(CONF_NAME): cv.string,
    }),
    # Make sure it's either a word or an expression command
    cv.has_at_least_one_key(CONF_WORD, CONF_EXPRESSION)
)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_COMMANDS, default=[]): [COMMAND_SCHEMA]
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_SEND_MESSAGE = 'send_message'

SERVICE_UPDATE_USERS_AND_CONVERSATIONS = 'update_users_and_conversations'


async def async_setup(hass, config):
    """Set up the Hangouts bot component."""
    from hangups.auth import GoogleAuthError

    config = config[DOMAIN]

    try:
        bot = HangoutsBot(
            hass,
            os.path.join(hass.config.path(), SESSION_FILE),
            config[CONF_EMAIL],
            config[CONF_PASSWORD],
            config[CONF_COMMANDS])
        hass.data[DOMAIN] = bot
    except GoogleAuthError as exception:
        _LOGGER.error("Hangouts failed to log in: %s", str(exception))
        return False

    await bot.async_connect()

    hass.services.async_register(DOMAIN, SERVICE_SEND_MESSAGE,
                                 bot.async_handle_send_message,
                                 schema=MESSAGE_SCHEMA)
    hass.services.async_register(DOMAIN,
                                 SERVICE_UPDATE_USERS_AND_CONVERSATIONS,
                                 bot.
                                 async_handle_update_users_and_conversations,
                                 schema=None)

    return True


class HangoutsBot:
    """The Hangouts Bot."""

    def __init__(self, hass, config_file, email, password, commands):
        """Set up the client."""
        self.hass = hass

        self._session_filepath = config_file

        self._email = email
        self._password = password
        self._commands = commands

        self._word_commands = None
        self._expression_commands = None
        self._client = None
        self._user_list = None
        self._conversation_list = None

        self.hass.bus.async_listen(EVENT_HANGOUTS_CONNECTED,
                                   self.
                                   async_handle_update_users_and_conversations)
        self.hass.bus.async_listen(EVENT_HANGOUTS_CONVERSATIONS_CHANGED,
                                   self._update_conversaition_commands)
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                                        self._async_handle_hass_stop)

    def _update_conversaition_commands(self, _):
        self._word_commands = {}

        self._expression_commands = {}

        for command in self._commands:
            if not command.get(CONF_CONVERSATIONS):
                command[CONF_CONVERSATIONS] = \
                    [conv.id_ for conv in self._conversation_list.get_all()]

            if command.get(CONF_WORD):
                for conv_id in command[CONF_CONVERSATIONS]:
                    if conv_id not in self._word_commands:
                        self._word_commands[conv_id] = {}
                    word = command[CONF_WORD].lower()
                    self._word_commands[conv_id][word] = command
            else:
                for conv_id in command[CONF_CONVERSATIONS]:
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
                match = command[CONF_EXPRESSION].match(event.text)
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
        import homeassistant

        from hangups import Client
        from hangups import RefreshTokenCache
        from hangups import get_auth
        from hangups import CredentialsPrompt

        class _HangoutsCredentials(CredentialsPrompt):
            def __init__(self, email, password):
                self._email = email
                self._password = password

            def get_email(self):
                return self._email

            def get_password(self):
                return self._password

            def get_verification_code(self):
                from hangups.auth import GoogleAuthError
                raise GoogleAuthError(
                    '2FA Login not possible! - '
                    'Use an app-specific password instead.')

        self._client = Client(
            get_auth(_HangoutsCredentials(self._email, self._password),
                     RefreshTokenCache(self._session_filepath)))
        self._client.on_connect.add_observer(self._on_connect)
        self._client.on_disconnect.add_observer(self._on_disconnect)

        homeassistant.util.async_.fire_coroutine_threadsafe(
            self._client.connect(), self.hass.loop)

    def _on_connect(self):
        _LOGGER.info('Connected!')
        self.hass.bus.fire(EVENT_HANGOUTS_CONNECTED)

    def _on_disconnect(self):
        """Handle disconnecting."""
        _LOGGER.info('Connection lost!')
        self.hass.bus.fire('hangouts.disconnected')

    async def _async_handle_hass_stop(self, _):
        """Run once when Home Assistant stops."""
        await self._client.disconnect()

    async def _async_send_message(self, message, targets):
        conversations = []
        for target in targets:
            conversation = None
            if 'id' in target:
                conversation = self._conversation_list.get(target['id'])
            elif 'name' in target:
                for conv in self._conversation_list.get_all():
                    if conv.name == target['name']:
                        conversation = conv
                        break
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
        self.hass.bus.fire(EVENT_HANGOUTS_USERS_CHANGED, users)
        self.hass.states.async_set("{}.conversations".format(DOMAIN),
                                   len(self._conversation_list.get_all()),
                                   attributes=conversations)
        self.hass.bus.fire(EVENT_HANGOUTS_CONVERSATIONS_CHANGED, conversations)

    async def async_handle_send_message(self, service):
        """Handle the send_message service."""
        await self._async_send_message(service.data[ATTR_MESSAGE],
                                       service.data[ATTR_TARGET])

    async def async_handle_update_users_and_conversations(self, _):
        """Handle the update_users_and_conversations service."""
        await self._async_list_conversations()
