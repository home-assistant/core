"""
Support for IRC.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/irc/
"""
import re
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import (
    CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_PORT,
    CONF_SSL, CONF_VERIFY_SSL, CONF_WHITELIST)

REQUIREMENTS = ['irc3==1.0.0']
DOMAIN = 'irc'

_LOGGER = logging.getLogger(__name__)

CONF_CHANNEL = 'channel'
CONF_NICK = 'nick'
CONF_NETWORK = 'network'
CONF_AUTOJOIN = 'autojoin'
CONF_ZNC = 'znc'
CONF_REAL_NAME = 'real_name'
CONF_ONLY_WHEN_ADDRESSED = 'only_when_addressed'

EVENT_PRIVMSG = 'irc_privmsg'

DATA_IRC = 'data_irc'

DEFAULT_USERNAME = 'hass'
DEFAULT_REAL_NAME = 'Home Assistant'
DEFAULT_PORT = 6667

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NICK): cv.string,
        vol.Required(CONF_NETWORK): cv.string,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_REAL_NAME, default=DEFAULT_REAL_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_AUTOJOIN, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_ZNC, default=False): cv.boolean,
        vol.Optional(CONF_WHITELIST, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_ONLY_WHEN_ADDRESSED, default=True): cv.boolean,
    })])
}, extra=vol.ALLOW_EXTRA)


class Observable(object):
    """Wrapper that allows observation of attributes."""

    def __init__(self):
        """Initialize a new Observable instance."""
        self._observers = []
        self._do_notify = True

    def enable(self):
        """Send notification updates."""
        self._do_notify = True

    def disable(self):
        """Do not send notification updates."""
        self._do_notify = False

    def observe(self, observer):
        """Add observer that receives attribute updates."""
        if observer not in self._observers:
            self._observers.append(observer)

    def manual_update(self, attr):
        """Force notify observers of an attribute update."""
        if self._do_notify:
            for observer in self._observers:
                observer.attr_updated(attr, getattr(self, attr))

    def update(self, **kwargs):
        """Make updates to attributes and notify observers."""
        # Update all properties first...
        for attr, value in kwargs.items():
            setattr(self, str(attr), value)

        # ...then notify observers to make sure state is consistent
        if self._do_notify:
            for observer in self._observers:
                for attr, value in kwargs.items():
                    observer.attr_updated(attr, value)


class IRCChannel(Observable):
    """Representation of an IRC channel."""

    def __init__(self, channel):
        """Initialize a new IRC channel."""
        super().__init__()
        self.channel = channel
        self.topic = None
        self.last_speaker = None
        self.last_message = None
        self.users = set()


# The irc3 properties must be applied to methods when the class is defined and
# cannot be added after the object has been constructed (like in __init__).
# It's an implementation detail in a library that irc3 uses, so this is a
# work-around to make it work with Home Assistant.
def make_plugin():
    """Create plugin to intercept messages from IRC server."""
    import irc3

    # pylint: disable=redefined-outer-name
    @irc3.plugin
    class HAPlugin(object):
        """Plugin to IRC3 that handles IRC commands."""

        # Matches topics when re-connecting to active ZNC session
        TOPIC_BNC_REPLAY = irc3.rfc.raw.new(
            'TOPIC_BNC_REPLAY',
            (r'^(@(?P<tags>\S+) )?:(?P<mask>\S+) 332 '
             r'(?P<nick>\S+) (?P<channel>\S+) :(?P<data>.+)'))

        # All users currently in a channel (matches NAMES command)
        NAME_LIST = irc3.rfc.raw.new(
            'NAME_LIST',
            (r'^(@(?P<tags>\S+) )?:(?P<mask>\S+) 353 '
             r'(?P<nick>\S+) . (?P<channel>\S+) :(?P<users>.+)'))

        def __init__(self, context):
            """Initialize a new HAPlugin instance."""
            self.context = context
            self.hass = context.config.get('hass')
            self.config = context.config.get('hass_config')
            self.network = self.config.get(CONF_NETWORK)
            self._channels = {}

        def server_ready(self):
            """Triggered after the server sent the MOTD."""
            _LOGGER.info('Connected to IRC network %s',
                         self.config.get(CONF_NETWORK))

        @staticmethod
        def connection_lost():
            """Triggered when connection is lost."""
            _LOGGER.error('Failed to connect to IRC server')

        def get_channel(self, channel):
            """Return internal channel object."""
            if channel not in self._channels:
                self._channels[channel] = IRCChannel(channel)
            return self._channels[channel]

        @irc3.event(irc3.rfc.PRIVMSG)
        def on_privmsg(self, mask=None, target=None, data=None, **kw):
            """Handle PRIVMSG commands."""
            # Do not trigger updates for znc playback
            self._znc_toggle(mask, target, data)

            nick = mask.split('!')[0]
            self._update_channel(target, last_speaker=nick, last_message=data)

            # Check whitelist before firing an event
            allowed = self.config.get(CONF_WHITELIST)
            if not any(map(lambda pattern: re.match(pattern, nick), allowed)):
                return

            # Check if we must be addressed by user
            only_when_addressed = self.config.get(CONF_ONLY_WHEN_ADDRESSED)
            is_addressed = data.startswith('{0}:'.format(self.context.nick))
            if only_when_addressed and not is_addressed:
                return

            channel = self.get_channel(target)
            self.hass.bus.fire(EVENT_PRIVMSG, {
                'channel': channel.channel,
                'last_speaker': channel.last_speaker,
                'last_message': channel.last_message
            })

        def _znc_toggle(self, mask, channel, data):
            if channel not in self._channels:
                return

            if self.config.get(CONF_ZNC) and mask == '***!znc@znc.in':
                if data == 'Buffer Playback...':
                    self._channels[channel].disable()
                elif data == 'Playback Complete.':
                    self._channels[channel].enable()

        @irc3.event(irc3.rfc.TOPIC)
        @irc3.event(TOPIC_BNC_REPLAY)
        def on_topic(self, channel=None, data=None, **kw):
            """Handle TOPIC commands."""
            self._update_channel(channel, topic=data)

        def _update_channel(self, channel, **kwargs):
            if channel in self._channels:
                obj = self._channels[channel]
                obj.update(**kwargs)

        @irc3.event(NAME_LIST)
        def on_names(self, channel=None, users=None, **kwargs):
            """Handle NAMES commands."""
            if channel not in self._channels:
                return

            chan = self._channels[channel]
            chan.users.clear()
            for user in users.split(' '):
                if user.startswith('@') or user.startswith('+'):
                    user = user[1:]
                chan.users.add(user)
            chan.manual_update('users')

        @irc3.event(irc3.rfc.JOIN_PART_QUIT)
        def on_user_event(self, mask=None, event=None, channel=None, **kwargs):
            """Handle JOIN, PART and QUIT commands."""
            if channel not in self._channels:
                return

            nick = mask.split('!')[0]
            chan = self._channels[channel]
            if event == 'JOIN':
                chan.users.add(nick)
            elif nick in chan.users:
                chan.users.remove(nick)
            chan.manual_update('users')

        @irc3.event(irc3.rfc.KICK)
        def on_user_kick(self, channel, target, **kwargs):
            """Handle KICK commands."""
            if channel not in self._channels:
                return

            chan = self._channels[channel]
            if target in chan.users:
                chan.users.remove(target)
            chan.manual_update('users')

    return HAPlugin


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the IRC component."""
    hass.data[DATA_IRC] = {}

    @asyncio.coroutine
    def async_setup_irc_server(hass, config):
        """Setup a new IRC server."""
        irc_config = {
            'loop': hass.loop,
            'nick': config.get(CONF_NICK),
            'host': config.get(CONF_HOST),
            'port': config.get(CONF_PORT),
            'username': config.get(CONF_USERNAME),
            'realname': config.get(CONF_REAL_NAME),
            'hass': hass,
            'hass_config': config,
            'autojoins': config.get(CONF_AUTOJOIN),
            'ssl': config.get(CONF_SSL),
            'includes': ['irc3.plugins.core', __name__]
        }

        if CONF_PASSWORD in config:
            irc_config.update({'password': config.get(CONF_PASSWORD)})

        if not config.get(CONF_VERIFY_SSL):
            irc_config.update({'ssl_verify': 'CERT_NONE'})

        import irc3
        bot = irc3.IrcBot.from_config(irc_config)
        network = config.get(CONF_NETWORK)
        plugin_path = '{0}.{1}'.format(__name__, HAPlugin.__name__)
        hass.data[DATA_IRC][network] = bot.get_plugin(plugin_path)
        bot.run(forever=False)

        hass.async_add_job(discovery.async_load_platform(
            hass, 'notify', DOMAIN, {
                CONF_NETWORK: network
            }, config))

    # Plugins must have an attribute which is not possible to add globally
    # since Home Assistant installs dependencies on-the-fly. This adds it in
    # runtime instead (sort of a hack).
    global HAPlugin  # pylint: disable=invalid-name,global-variable-undefined
    HAPlugin = make_plugin()

    tasks = [async_setup_irc_server(hass, conf) for conf in config[DOMAIN]]
    if tasks:
        yield from asyncio.wait(tasks, loop=hass.loop)

    return True
