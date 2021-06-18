"""The xmpp component."""

import asyncio
import logging
import re

import slixmpp
from slixmpp.exceptions import XMPPError
import voluptuous as vol

from homeassistant.components.notify import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RESOURCE,
    CONF_SENDER,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    BOOL_GROUPCHAT,
    CONF_TLS,
    CONF_VERIFY,
    DEFAULT_RESOURCE,
    DOMAIN,
    SERVICE_SEND_MESSAGE,
)

_LOGGER = logging.getLogger(__name__)

EVENT_XMPP_COMMAND = "xmpp_command"
CONF_ROOMS = "rooms"
CONF_COMMANDS = "commands"
CONF_WORD = "word"
CONF_EXPRESSION = "expression"
CONF_DIRECT_MESSAGE = "direct_message_contacts"

# variables for sending messages (notify)
ATTR_PATH = "path"
ATTR_PATH_TEMPLATE = "path_template"
ATTR_TIMEOUT = "timeout"
ATTR_URL = "url"
ATTR_URL_TEMPLATE = "url_template"
ATTR_VERIFY = "verify"
ATTR_IMAGES = "images"
ATTR_TARGET_ROOMS = "target_rooms"
ATTR_RECIPIENT_ROOMS = "recipient_rooms"

DEFAULT_CONTENT_TYPE = "application/octet-stream"

COMMAND_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Exclusive(CONF_WORD, "trigger"): cv.string,
            vol.Exclusive(CONF_EXPRESSION, "trigger"): cv.is_regex,
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(CONF_ROOMS, default=[]): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_DIRECT_MESSAGE, default=[]): vol.All(
                cv.ensure_list, [cv.string]
            ),
        }
    ),
    cv.has_at_least_one_key(CONF_WORD, CONF_EXPRESSION),
)

SERVICE_SCHEMA_SEND_MESSAGE = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_DATA): {
            vol.Optional(ATTR_PATH): cv.string,
            vol.Optional(ATTR_URL): cv.string,
        },
        vol.Required(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(BOOL_GROUPCHAT): cv.boolean,
    }
)


def setup(hass, config):
    """Set up the XMPP bot component."""
    try:
        asyncio.get_event_loop()

    except RuntimeError:
        # workaround for: https://lab.louiz.org/poezio/slixmpp/-/issues/3456
        _LOGGER.info("Eventloop RuntimeError ignored")
        asyncio.set_event_loop(asyncio.new_event_loop())

    # check if old config is set
    notify = False
    if config.get("notify") is not None:
        notify = True
        config_notify = config.get("notify")[0]

    try:
        # if sender is set, use the old config
        if notify and config_notify.get("sender") is not None:
            _LOGGER.info("Using old config in notify")
            bot = XMPPBot(
                hass,
                config_notify.get(CONF_SENDER),
                config_notify.get(CONF_PASSWORD),
                None,  # commands not supported in old config
                None,
                None,
                config_notify.get(CONF_RESOURCE),
                config_notify.get(CONF_VERIFY),
            )
            tls = config_notify.get(CONF_TLS, True)

        # use new config
        else:
            new_config = config[DOMAIN]
            bot = XMPPBot(
                hass,
                new_config[CONF_USERNAME],
                new_config[CONF_PASSWORD],
                new_config.get(CONF_ROOMS),
                new_config.get(CONF_DIRECT_MESSAGE),
                new_config.get(CONF_COMMANDS),
                new_config.get(CONF_RESOURCE),
                new_config.get(CONF_VERIFY_SSL),
            )
            tls = new_config.get(CONF_TLS, True)

        hass.data[DOMAIN] = bot

        bot.connect(force_starttls=tls, use_ssl=False)

    except XMPPError as exception:
        _LOGGER.error("Exception: %s", str(exception))
        return False
    if notify:
        hass.services.register(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            bot.handle_send_message,
            schema=SERVICE_SCHEMA_SEND_MESSAGE,
        )
    _LOGGER.info("Finished Setup!")
    return True


def generate_word_commands(
    commands, senders, conf_senders, all_conf_senders, conf_word="word"
):
    """Generate the necessary command dictionaries.

    :param commands: commands from the config file
    :param senders: addresses which can trigger the commands if the addresses of the specific commands are empty
    :param conf_senders: word from the config of the senders, e.g. 'rooms'
    :param all_conf_senders: array with all words from the config of the senders, e.g. ['rooms', 'direct_message_contacts']
    :param conf_word: word for the command in the config, e.g. 'word'
    :returns: 2 dictionaries: word_commands, expression_commands

    """
    word_commands = {}
    expression_commands = {}
    for command in commands:
        continue_because_other_message_type = False
        if command.get("default_message_types") is None:
            command["default_message_types"] = []
        if not command.get(conf_senders):

            # check if there are no other message types that have been registered on this command
            # e.g. if testcommand has only rooms and no direct_message_contacts defined
            for config_sender in all_conf_senders:
                if (
                    config_sender != conf_senders
                    and command.get(config_sender)
                    and config_sender not in command["default_message_types"]
                ):
                    command[conf_senders] = None
                    _LOGGER.debug(
                        "The sender for %s is not defined for this message type: %s",
                        command["name"],
                        conf_senders,
                    )
                    continue_because_other_message_type = True

            if continue_because_other_message_type:
                continue
            command[conf_senders] = senders
            command["default_message_types"].append(conf_senders)

        if command.get(conf_word):
            for room_id in command[conf_senders]:
                if room_id not in word_commands:
                    word_commands[room_id] = {}
                word_commands[room_id][command[conf_word]] = command

        else:
            for room_id in command[conf_senders]:
                if room_id not in expression_commands:
                    expression_commands[room_id] = []
                expression_commands[room_id].append(command)
    return word_commands, expression_commands


class XMPPBot(slixmpp.ClientXMPP):
    """Service for receiving Jabber (XMPP) messages."""

    def __init__(
        self,
        hass,
        username,
        password,
        listening_rooms,
        listening_contacts,
        commands,
        resource,
        verify_ssl=True,
    ):
        """Initialize the Jabber Bot."""
        if resource is None:
            resource = DEFAULT_RESOURCE
        full_username = f"{username}/{resource}"
        super().__init__(full_username, password)

        self.hass = hass
        self._listening_rooms = listening_rooms
        self._listening_contacts = listening_contacts
        self.client_name = resource

        # it is possible to configure all commands to be sent from a group or a contact (direct message)
        # so we have to generate separate dictionaries
        # Word commands are stored dict-of-dict: First dict indexes by room ID
        #  / alias, second dict indexes by the word
        # Regular expression commands are stored as a list of commands per
        # room, i.e., a dict-of-list

        all_conf_senders = ["rooms", "direct_message_contacts"]

        if self._listening_rooms is not None:
            (
                self._room_word_commands,
                self._room_expression_commands,
            ) = generate_word_commands(
                commands, self._listening_rooms, all_conf_senders[0], all_conf_senders
            )

        if self._listening_contacts is not None:
            (
                self._direct_message_word_commands,
                self._direct_message_expression_commands,
            ) = generate_word_commands(
                commands,
                self._listening_contacts,
                all_conf_senders[1],
                all_conf_senders,
            )

        self.use_ipv6 = False

        self.register_plugin("xep_0045")  # XEP for multi-user chat (groups)
        self.add_event_handler("failed_auth", self.disconnect_on_login_fail)
        self.add_event_handler("session_start", self.start)
        if self._listening_rooms is not None or self._listening_contacts is not None:
            self.add_event_handler("message", self.message)

        self.hass.bus.listen_once(EVENT_HOMEASSISTANT_START, self.handle_startup)
        self.hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, self.stop_client)

        if not verify_ssl:
            self.add_event_handler("ssl_invalid_cert", self.discard_ssl_invalid_cert)

    def _join_rooms(self, rooms=None):
        """Join the XMPP rooms that we listen for commands in."""
        if rooms is None:
            rooms = self._listening_rooms
        if isinstance(rooms, str):
            rooms = [rooms]
        for room in rooms:
            if room in self.plugin["xep_0045"].get_joined_rooms():
                _LOGGER.debug("Room already joined: %s", room)
                continue
            _LOGGER.info("Joining room %s", room)
            self.plugin["xep_0045"].join_muc(room, self.client_name)
        _LOGGER.info("Successfully joined all rooms")

    def handle_startup(self, _):
        """Run once when Home Assistant finished startup."""
        _LOGGER.debug("Handle Startup")
        self.process(forever=True)

    def stop_client(self, _):
        """Run once when Home Assistant stops."""
        self.disconnect()

    async def start(self, event):
        """Start the communication."""
        _LOGGER.debug("Start method")
        self.send_presence()
        await self.get_roster()
        if self._listening_rooms is not None:
            self._join_rooms()
        _LOGGER.debug("Start method end")

    async def message(self, msg):
        """Handle a message sent to the user."""
        _LOGGER.debug("Message received!")
        message_text = msg["body"]
        name = msg["from"].bare
        sender = msg[
            "from"
        ].bare  # only in group chats, the sender is different from the name (room name)
        _LOGGER.debug("Handling message: %s", message_text)

        if msg["type"] == "groupchat":  # group message
            sender = msg["mucnick"]
            self.send_command_to_home_assistant(
                self.hass,
                self._room_word_commands,
                self._room_expression_commands,
                message_text,
                name,
                sender,
                CONF_NAME,
                EVENT_XMPP_COMMAND,
                CONF_EXPRESSION,
            )

        elif msg["type"] == "chat":  # direct message
            self.send_command_to_home_assistant(
                self.hass,
                self._direct_message_word_commands,
                self._direct_message_expression_commands,
                message_text,
                name,
                sender,
                CONF_NAME,
                EVENT_XMPP_COMMAND,
                CONF_EXPRESSION,
            )
        else:
            _LOGGER.info("No direct or group message, skipping")
            return

    def _send_text_messages(self, message, targets, target_is_groupchat):
        """Send the message to the XMPP server."""
        mtype = "chat"
        for target_room in targets:
            if target_is_groupchat:
                mtype = "groupchat"
                self._join_rooms(target_room)
            self.send_message(mto=target_room, mbody=message, mtype=mtype)
            _LOGGER.debug("target_is_groupchat %s", str(target_is_groupchat))
            _LOGGER.debug("message sent: " + message + " to: " + target_room)

    async def handle_send_message(self, service):
        """Handle the send_message service."""
        # text message
        if service.data.get(ATTR_MESSAGE) is not None:
            _LOGGER.info("Sending text message")
            self._send_text_messages(
                service.data.get(ATTR_MESSAGE),
                service.data[ATTR_TARGET],
                service.data[BOOL_GROUPCHAT],
            )
        if service.data.get(ATTR_MESSAGE) is None:
            _LOGGER.warning("No data received, didn't send Message!")

    @staticmethod
    def send_command_to_home_assistant(
        hass,
        word_commands,
        expression_commands,
        message_text,
        name,
        sender,
        conf_name,
        event_xmpp_command,
        conf_expression,
    ):
        """Send a Command to HomeAssistant."""
        if message_text[0] == "!":
            pieces = message_text.split(" ")
            cmd = pieces[0][1:]
            command = word_commands.get(name, {}).get(cmd)
            if command:
                event_data = {
                    "command": command[conf_name],
                    "sender": sender,
                    "room": name,
                    "args": pieces[1:],
                }
                hass.bus.fire(event_xmpp_command, event_data)

        # Check regex command
        for command in expression_commands.get(name, []):
            match = re.match(command[conf_expression], message_text)
            if not match:
                continue
            event_data = {
                "command": command[conf_name],
                "sender": sender,
                "room": name,
                "args": match.groupdict(),
            }
            hass.bus.fire(event_xmpp_command, event_data)

    def disconnect_on_login_fail(self, _):
        """Disconnect from the server if credentials are invalid."""
        _LOGGER.error("Login failed")
        self.disconnect()

    @staticmethod
    def discard_ssl_invalid_cert():
        """Do nothing if ssl certificate is invalid."""
        _LOGGER.info("Ignoring invalid SSL certificate as requested")
