"""
The matrix bot component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/matrix/
"""
import logging
import os

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (ATTR_TARGET, ATTR_MESSAGE)
from homeassistant.const import (CONF_EMAIL, CONF_PASSWORD, CONF_NAME)
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = ['hangups==0.4.4']

_LOGGER = logging.getLogger(__name__)

SESSION_FILE = '.hangouts.conf'

CONF_CONVERSATIONS = 'conversations'
CONF_COMMANDS = 'commands'
CONF_WORD = 'word'
CONF_EXPRESSION = 'expression'

EVENT_HANGOUTS_COMMAND = 'hangouts_command'

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
    vol.Optional('is_unterline'): cv.boolean,
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
    import homeassistant

    homeassistant.util.async_.fire_coroutine_threadsafe(bot.async_handle_update_users_and_conversations(None), hass.loop)

    hass.services.async_register(DOMAIN, SERVICE_SEND_MESSAGE, bot.async_handle_send_message,
                                 schema=MESSAGE_SCHEMA)
    
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_USERS_AND_CONVERSATIONS, bot.async_handle_update_users_and_conversations, schema=None)

    return True

class HangoutsCredentials(object):
    def __init__(self, email, password):
        self._email = email
        self._password = password
    
    def get_email(self):
        return self._email
    
    def get_password(self):
        return self._password
    
    def get_verification_code(self):
        from hangups.auth import GoogleAuthError
        raise GoogleAuthError('2FA Login not possible!')
    

class HangoutsBot(object):
    """The Hangouts Bot."""

    def __init__(self, hass, config_file,
                 email, password, commands):
        """Set up the client."""
        self.hass = hass

        self._session_filepath = config_file

        self._email = email
        self._password = password

        # We have to fetch the aliases for every room to make sure we don't
        # join it twice by accident. However, fetching aliases is costly,
        # so we only do it once per room.
        self._aliases_fetched_for = set()

        # word commands are stored dict-of-dict: First dict indexes by room ID
        #  / alias, second dict indexes by the word
        self._word_commands = {}

        # regular expression commands are stored as a list of commands per
        # room, i.e., a dict-of-list
        self._expression_commands = {}

        for command in commands:
            if not command.get(CONF_CONVERSATIONS):
                command[CONF_CONVERSATIONS] = None #TODO: all conversations

            if command.get(CONF_WORD):
                for room_id in command[CONF_CONVERSATIONS]:
                    if room_id not in self._word_commands:
                        self._word_commands[room_id] = {}
                    self._word_commands[room_id][command[CONF_WORD]] = command
            else:
                for room_id in command[CONF_CONVERSATIONS]:
                    if room_id not in self._expression_commands:
                        self._expression_commands[room_id] = []
                    self._expression_commands[room_id].append(command)
        
    def _handle_conversation_message(self, room_id, conversation, event):
        """Handle a message sent to a conversatio."""
        if event['content']['msgtype'] != 'm.text':
            return

        if event['sender'] == self.username:
            return

        _LOGGER.debug("Handling message: %s", event['content']['body'])

        if event['content']['body'][0] == "!":
            # Could trigger a single-word command.
            pieces = event['content']['body'].split(' ')
            cmd = pieces[0][1:]

            command = self._word_commands.get(room_id, {}).get(cmd)
            if command:
                event_data = {
                    'command': command[CONF_NAME],
                    'sender': event['sender'],
                    'room': room_id,
                    'args': pieces[1:]
                }
                self.hass.bus.fire(EVENT_HANGOUTS_COMMAND, event_data)

        # After single-word commands, check all regex commands in the room
        for command in self._expression_commands.get(room_id, []):
            match = command[CONF_EXPRESSION].match(event['content']['body'])
            if not match:
                continue
            event_data = {
                'command': command[CONF_NAME],
                'sender': event['sender'],
                'room': room_id,
                'args': match.groupdict()
            }
            self.hass.bus.fire(EVENT_HANGOUTS_COMMAND, event_data)


    async def async_connect(self):
        """Login to the Google Hangouts and return the client instance."""
        
        from hangups import Client
        from hangups import RefreshTokenCache
        from hangups import get_auth
        
        import homeassistant
        
        self._client = Client(get_auth(HangoutsCredentials(self._email, self._password), RefreshTokenCache(self._session_filepath)))
        self._client.on_connect.add_observer(self._on_connect)
        self._client.on_disconnect.add_observer(self._on_disconnect)

        homeassistant.util.async_.fire_coroutine_threadsafe(self._client.connect(), self.hass.loop)


    def _on_connect(self):
        _LOGGER.info('Connected!')

    def _on_disconnect(self):
        """Handle disconnecting"""
        _LOGGER.info('Connection lost!')

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
        
        if len(conversations) == 0: return False
        
        from hangups import ChatMessageSegment, hangouts_pb2
        messages = []
        for m in message:
            if 'parse_str' in m and m['parse_str']:
                messages.extend(ChatMessageSegment.from_str(m['text']))
            else:
                messages.append(ChatMessageSegment(**m))
            messages.append(ChatMessageSegment('', segment_type=hangouts_pb2.SEGMENT_TYPE_LINE_BREAK))
            
        if len(messages) == 0: return False
        for conv in conversations:
            await conv.send_message(messages)
            
        

    async def _async_list_conversations(self):
        import hangups
        self._user_list, self._conversation_list = (await hangups.build_user_conversation_list(self._client))
        users = {}
        conversations = {}
        for user in self._user_list.get_all():
            users[str(user.id_.chat_id)] = {'full_name': user.full_name, 'is_self': user.is_self}
        
        for conv in self._conversation_list.get_all():
            u = {}
            for user in conv.users:
                u[str(user.id_.chat_id)] = {'full_name': user.full_name, 'is_self': user.is_self}
            conversations[str(conv.id_)] = {'name': conv.name, 'users': u}
            
        self.hass.states.async_set("{}.users".format(DOMAIN), len(self._user_list.get_all()), attributes=users)
        self.hass.states.async_set("{}.conversations".format(DOMAIN), len(self._conversation_list.get_all()), attributes=conversations)

    async def async_handle_send_message(self, service):
        """Handle the send_message service."""
        await self._async_send_message(service.data[ATTR_MESSAGE], service.data[ATTR_TARGET])


    async def async_handle_update_users_and_conversations(self, service):
        """Handle the update_users_and_conversations service."""
        await self._async_list_conversations()
