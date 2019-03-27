"""
Support for PlayStation 4 consoles.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/ps4/
"""
import logging
import socket

import voluptuous as vol

from homeassistant.components.media_player import (
    ENTITY_IMAGE_URL, MediaPlayerDevice)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC, SUPPORT_SELECT_SOURCE, SUPPORT_STOP, SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON)
from homeassistant.const import (
    ATTR_COMMAND, ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_REGION,
    CONF_TOKEN, STATE_IDLE, STATE_OFF, STATE_PLAYING)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json, save_json

from .const import DOMAIN as PS4_DOMAIN, REGIONS as deprecated_regions

DEPENDENCIES = ['ps4']

_LOGGER = logging.getLogger(__name__)

SUPPORT_PS4 = SUPPORT_TURN_OFF | SUPPORT_TURN_ON | \
    SUPPORT_STOP | SUPPORT_SELECT_SOURCE

PS4_DATA = 'ps4_data'
ICON = 'mdi:playstation'
GAMES_FILE = '.ps4-games.json'
MEDIA_IMAGE_DEFAULT = None

COMMANDS = (
    'up',
    'down',
    'right',
    'left',
    'enter',
    'back',
    'option',
    'ps',
)

SERVICE_COMMAND = 'send_command'

PS4_COMMAND_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_COMMAND): vol.In(list(COMMANDS))
})


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up PS4 from a config entry."""
    config = config_entry

    def add_entities(entities, update_before_add=False):
        """Sync version of async add devices."""
        hass.add_job(async_add_entities, entities, update_before_add)

    await hass.async_add_executor_job(
        setup_platform, hass, config,
        add_entities, None)

    async def async_service_handle(hass):
        """Handle for services."""
        def service_command(call):
            entity_ids = call.data[ATTR_ENTITY_ID]
            command = call.data[ATTR_COMMAND]
            for device in hass.data[PS4_DATA].devices:
                if device.entity_id in entity_ids:
                    device.send_command(command)

        hass.services.async_register(
            PS4_DOMAIN, SERVICE_COMMAND, service_command,
            schema=PS4_COMMAND_SCHEMA)

    await async_service_handle(hass)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up PS4 Platform."""
    import pyps4_homeassistant as pyps4
    hass.data[PS4_DATA] = PS4Data()
    games_file = hass.config.path(GAMES_FILE)
    creds = config.data[CONF_TOKEN]
    device_list = []
    for device in config.data['devices']:
        host = device[CONF_HOST]
        region = device[CONF_REGION]
        name = device[CONF_NAME]
        ps4 = pyps4.Ps4(host, creds)
        device_list.append(PS4Device(
            name, host, region, ps4, games_file))
    add_entities(device_list, True)


class PS4Data():
    """Init Data Class."""

    def __init__(self):
        """Init Class."""
        self.devices = []


class PS4Device(MediaPlayerDevice):
    """Representation of a PS4."""

    def __init__(self, name, host, region, ps4, games_file):
        """Initialize the ps4 device."""
        self._ps4 = ps4
        self._host = host
        self._name = name
        self._region = region
        self._state = None
        self._games_filename = games_file
        self._media_content_id = None
        self._media_title = None
        self._media_image = None
        self._source = None
        self._games = {}
        self._source_list = []
        self._retry = 0
        self._info = None
        self._unique_id = None
        self._power_on = False

    async def async_added_to_hass(self):
        """Subscribe PS4 events."""
        self.hass.data[PS4_DATA].devices.append(self)

    def update(self):
        """Retrieve the latest data."""
        try:
            status = self._ps4.get_status()
            if self._info is None:
                # Add entity to registry
                self.get_device_info(status)
                self._games = self.load_games()
                if self._games is not None:
                    self._source_list = list(sorted(self._games.values()))
                # Non-Breaking although data returned may be inaccurate.
                if self._region in deprecated_regions:
                    _LOGGER.info("""Region: %s has been deprecated.
                                    Please remove PS4 integration
                                    and Re-configure again to utilize
                                    current regions""", self._region)
        except socket.timeout:
            status = None
        if status is not None:
            self._retry = 0
            if status.get('status') == 'Ok':
                # Check if only 1 device in Hass.
                if len(self.hass.data[PS4_DATA].devices) == 1:
                    # Enable keep alive feature for PS4 Connection.
                    # Only 1 device is supported, Since have to use port 997.
                    self._ps4.keep_alive = True
                else:
                    self._ps4.keep_alive = False
                if self._power_on:
                    # Auto Login after Turn On.
                    self._ps4.open()
                    self._power_on = False
                title_id = status.get('running-app-titleid')
                name = status.get('running-app-name')
                if title_id and name is not None:
                    self._state = STATE_PLAYING
                    if self._media_content_id != title_id:
                        self._media_content_id = title_id
                        self.get_title_data(title_id, name)
                else:
                    self.idle()
            else:
                self.state_off()
        elif self._retry > 5:
            self.state_unknown()
        else:
            self._retry += 1

    def idle(self):
        """Set states for state idle."""
        self.reset_title()
        self._state = STATE_IDLE

    def state_off(self):
        """Set states for state off."""
        self.reset_title()
        self._state = STATE_OFF

    def state_unknown(self):
        """Set states for state unknown."""
        self.reset_title()
        self._state = None
        _LOGGER.warning("PS4 could not be reached")
        self._retry = 0

    def reset_title(self):
        """Update if there is no title."""
        self._media_title = None
        self._media_content_id = None
        self._source = None

    def get_title_data(self, title_id, name):
        """Get PS Store Data."""
        app_name = None
        art = None
        try:
            app_name, art = self._ps4.get_ps_store_data(
                name, title_id, self._region)
        except TypeError:
            _LOGGER.error(
                "Could not find data in region: %s for PS ID: %s",
                self._region, title_id)
        finally:
            self._media_title = app_name or name
            self._source = self._media_title
            self._media_image = art
            self.update_list()

    def update_list(self):
        """Update Game List, Correct data if different."""
        if self._media_content_id in self._games:
            store = self._games[self._media_content_id]
            if store != self._media_title:
                self._games.pop(self._media_content_id)
        if self._media_content_id not in self._games:
            self.add_games(self._media_content_id, self._media_title)
            self._games = self.load_games()
        self._source_list = list(sorted(self._games.values()))

    def load_games(self):
        """Load games for sources."""
        g_file = self._games_filename
        try:
            games = load_json(g_file)

        # If file does not exist, create empty file.
        except FileNotFoundError:
            games = {}
            self.save_games(games)
        return games

    def save_games(self, games):
        """Save games to file."""
        g_file = self._games_filename
        try:
            save_json(g_file, games)
        except OSError as error:
            _LOGGER.error("Could not save game list, %s", error)

        # Retry loading file
        if games is None:
            self.load_games()

    def add_games(self, title_id, app_name):
        """Add games to list."""
        games = self._games
        if title_id is not None and title_id not in games:
            game = {title_id: app_name}
            games.update(game)
            self.save_games(games)

    def get_device_info(self, status):
        """Return device info for registry."""
        _sw_version = status['system-version']
        _sw_version = _sw_version[1:4]
        sw_version = "{}.{}".format(_sw_version[0], _sw_version[1:])
        self._info = {
            'name': status['host-name'],
            'model': 'PlayStation 4',
            'identifiers': {
                (PS4_DOMAIN, status['host-id'])
            },
            'manufacturer': 'Sony Interactive Entertainment Inc.',
            'sw_version': sw_version
        }
        self._unique_id = status['host-id']

    async def async_will_remove_from_hass(self):
        """Remove Entity from Hass."""
        # Close TCP Socket
        await self.hass.async_add_executor_job(self._ps4.close)
        self.hass.data[PS4_DATA].devices.remove(self)

    @property
    def device_info(self):
        """Return information about the device."""
        return self._info

    @property
    def unique_id(self):
        """Return Unique ID for entity."""
        return self._unique_id

    @property
    def entity_picture(self):
        """Return picture."""
        if self._state == STATE_PLAYING and self._media_content_id is not None:
            image_hash = self.media_image_hash
            if image_hash is not None:
                return ENTITY_IMAGE_URL.format(
                    self.entity_id, self.access_token, image_hash)
        return MEDIA_IMAGE_DEFAULT

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        """Icon."""
        return ICON

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self._media_content_id

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        # No MEDIA_TYPE_GAME attr as of 0.90.
        return MEDIA_TYPE_MUSIC

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self._media_content_id is None:
            return MEDIA_IMAGE_DEFAULT
        return self._media_image

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._media_title

    @property
    def supported_features(self):
        """Media player features that are supported."""
        return SUPPORT_PS4

    @property
    def source(self):
        """Return the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    def turn_off(self):
        """Turn off media player."""
        self._ps4.standby()

    def turn_on(self):
        """Turn on the media player."""
        self._power_on = True
        self._ps4.wakeup()

    def media_pause(self):
        """Send keypress ps to return to menu."""
        self.send_remote_control('ps')

    def media_stop(self):
        """Send keypress ps to return to menu."""
        self.send_remote_control('ps')

    def select_source(self, source):
        """Select input source."""
        for title_id, game in self._games.items():
            if source == game:
                _LOGGER.debug(
                    "Starting PS4 game %s (%s) using source %s",
                    game, title_id, source)
                self._ps4.start_title(
                    title_id, running_id=self._media_content_id)
                return

    def send_command(self, command):
        """Send Button Command."""
        self.send_remote_control(command)

    def send_remote_control(self, command):
        """Send RC command."""
        self._ps4.remote_control(command)
