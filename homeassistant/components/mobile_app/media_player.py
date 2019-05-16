"""A media_player class for mobile_app."""
import logging
import voluptuous as vol

from homeassistant.components.media_player import (
    ENTITY_ID_FORMAT, MediaPlayerDevice)
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_CONTENT_TYPE, ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PLAY_MEDIA,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET)
from homeassistant.components.websocket_api import (ActiveConnection,
                                                    async_register_command,
                                                    event_message,
                                                    result_message,
                                                    websocket_command)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (ATTR_STATE, CONF_WEBHOOK_ID, STATE_OFF)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import (async_dispatcher_connect,
                                              async_dispatcher_send)
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.typing import HomeAssistantType

from .const import (ATTR_DEVICE_ID, ATTR_DEVICE_NAME, ATTR_MANUFACTURER,
                    ATTR_MODEL, ATTR_OS_VERSION, DATA_DEVICES, DOMAIN)

DATA_WS_CONNECTIONS = 'websocket_connections'

SIGNAL_MEDIA_PLAYER_STATE_UPDATE = DOMAIN + '_media_player_state_update'

SUPPORTED_FEATURES = SUPPORT_PAUSE | SUPPORT_PLAY | SUPPORT_PLAY_MEDIA |\
                     SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the mobile_app media_player platform."""
    _LOGGER.error(
        'Loading mobile_app by media_player platform config is unsupported')


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up mobile app media player from a config entry."""
    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    device = hass.data[DOMAIN][DATA_DEVICES][webhook_id]

    async_register_command(hass, forward_media_player_events)
    async_register_command(hass, update_media_player_state)

    async_add_entities([MobileAppMediaPlayer(hass, device, config_entry)])


@callback
@websocket_command({
    vol.Required('type'): 'mobile_app/subscribe_media_player',
    vol.Required(CONF_WEBHOOK_ID): str,
})
def forward_media_player_events(hass: HomeAssistantType,
                                connection: ActiveConnection,
                                msg: dict) -> None:
    """Handle forwarding media_player events to connected mobile_app.

    Async friendly.
    """
    webhook_id = msg[CONF_WEBHOOK_ID]

    _LOGGER.debug("Received connection for reg %s (%s)", webhook_id, msg['id'])

    @callback
    def send_to_mobile_app(event_type, event_data):
        """Forward events to websocket."""
        payload = {'type': event_type, 'data': event_data}
        connection.send_message(event_message(msg['id'], payload))

    if DATA_WS_CONNECTIONS not in hass.data[DOMAIN]:
        hass.data[DOMAIN][DATA_WS_CONNECTIONS] = {}

    hass.data[DOMAIN][DATA_WS_CONNECTIONS][webhook_id] = send_to_mobile_app

    @callback
    def async_cleanup() -> None:
        """Remove hass.data entry and other cleanup."""
        update_payload = {ATTR_STATE: STATE_OFF}
        async_dispatcher_send(hass, SIGNAL_MEDIA_PLAYER_STATE_UPDATE,
                              update_payload)
        hass.data[DOMAIN][DATA_WS_CONNECTIONS].pop(webhook_id, {})

    connection.subscriptions[msg['id']] = async_cleanup

    connection.send_message(result_message(msg['id']))


@callback
@websocket_command({
    vol.Required('type'): 'mobile_app/update_media_player_state',
    vol.Required(CONF_WEBHOOK_ID): str,
    vol.Required('player_state'): vol.Schema({
        vol.Required(ATTR_STATE): cv.string,
        vol.Required(ATTR_MEDIA_CONTENT_ID): cv.string,
        vol.Required(ATTR_MEDIA_CONTENT_TYPE): cv.string,
        vol.Required(ATTR_MEDIA_VOLUME_LEVEL): cv.small_float,
        vol.Required(ATTR_MEDIA_VOLUME_MUTED): cv.boolean,
    })
})
def update_media_player_state(hass: HomeAssistantType,
                              connection: ActiveConnection,
                              msg: dict) -> None:
    """Handle media player state updates from device via websocket.

    Async friendly.
    """
    webhook_id = msg[CONF_WEBHOOK_ID]

    _LOGGER.debug("Received state update for reg %s (%s)", webhook_id,
                  msg)

    async_dispatcher_send(hass, SIGNAL_MEDIA_PLAYER_STATE_UPDATE, msg)

    connection.send_message(result_message(msg['id']))


class MobileAppMediaPlayer(MediaPlayerDevice):
    """Representation of an mobile app media player."""

    def __init__(self, hass, device: DeviceEntry, entry: ConfigEntry):
        """Initialize the media player."""
        self._device = device
        self._entry = entry
        self._registration = entry.data
        self._player_state = {
            ATTR_STATE: STATE_OFF,
            ATTR_MEDIA_VOLUME_LEVEL: 0,
            ATTR_MEDIA_VOLUME_MUTED: False,
            ATTR_MEDIA_CONTENT_ID: None,
            ATTR_MEDIA_CONTENT_TYPE: None,
        }
        self.unsub_dispatcher = None
        name = self._registration[ATTR_DEVICE_NAME]
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT,
                                                  name=name, hass=hass)

    async def async_added_to_hass(self):
        """Register callbacks."""
        signal = SIGNAL_MEDIA_PLAYER_STATE_UPDATE
        self.unsub_dispatcher = async_dispatcher_connect(self.hass, signal,
                                                         self._handle_update)

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self.unsub_dispatcher is not None:
            self.unsub_dispatcher()

    def send_to_connection(self, event_type, event_data):
        """Send event_type and event_data to connection."""
        conns = self.hass.data[DOMAIN].get(DATA_WS_CONNECTIONS, {})
        webhook_id = self._registration[CONF_WEBHOOK_ID]
        if webhook_id in conns:
            conns[webhook_id](event_type, event_data)

    @property
    def should_poll(self) -> bool:
        """Declare that this entity pushes its state to HA."""
        return False

    @property
    def name(self):
        """Return the name of the mobile app media player."""
        return self._registration[ATTR_DEVICE_NAME]

    @property
    def unique_id(self):
        """Return the unique ID of this media player."""
        return '{}_media_player'.format(self._registration[CONF_WEBHOOK_ID])

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            'identifiers': {
                (ATTR_DEVICE_ID, self._registration[ATTR_DEVICE_ID]),
                (CONF_WEBHOOK_ID, self._registration[CONF_WEBHOOK_ID])
            },
            'manufacturer': self._registration[ATTR_MANUFACTURER],
            'model': self._registration[ATTR_MODEL],
            'device_name': self._registration[ATTR_DEVICE_NAME],
            'sw_version': self._registration[ATTR_OS_VERSION],
            'config_entries': self._device.config_entries
        }

    @property
    def state(self):
        """State of the player."""
        return self._player_state.get(ATTR_STATE, STATE_OFF)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._player_state.get(ATTR_MEDIA_VOLUME_LEVEL, 0)

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._player_state.get(ATTR_MEDIA_VOLUME_MUTED, False)

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self._player_state.get(ATTR_MEDIA_CONTENT_ID)

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return self._player_state.get(ATTR_MEDIA_CONTENT_TYPE)

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORTED_FEATURES

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self.send_to_connection('set_volume_level', volume)

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) the volume."""
        self.send_to_connection('mute', mute)

    def play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        payload = {
            ATTR_MEDIA_CONTENT_ID: media_id,
            ATTR_MEDIA_CONTENT_TYPE: media_type
        }
        self.send_to_connection('play_media', payload)

    def media_play(self):
        """Send play command."""
        self.send_to_connection('media_play', {})

    def media_pause(self):
        """Send pause command."""
        self.send_to_connection('media_pause', {})

    @callback
    def _handle_update(self, data):
        """Handle async event updates."""
        self._player_state = data['player_state']
        self.async_schedule_update_ha_state()
