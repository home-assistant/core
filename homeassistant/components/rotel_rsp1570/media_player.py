"""
Support for the Rotel RSP-1570 processor.

Although only the RSP-1570 is supported at the moment, the
low level library could easily be updated to support other
products of a similar vintage.
"""
import asyncio
import logging
import voluptuous as vol
from homeassistant.components.media_player import (
    DOMAIN, MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP, SUPPORT_VOLUME_SET)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE, CONF_NAME,
    STATE_OFF, STATE_ON,
    EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Rotel RSP-1570'

SUPPORT_ROTEL_RSP1570 = \
    SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

ROTEL_RSP1570_SOURCES = {
    ' CD': 'SOURCE_CD',
    'TUNER': 'SOURCE_TUNER',
    'TAPE': 'SOURCE_TAPE',
    'VIDEO 1': 'SOURCE_VIDEO_1',
    'VIDEO 2': 'SOURCE_VIDEO_2',
    'VIDEO 3': 'SOURCE_VIDEO_3',
    'VIDEO 4': 'SOURCE_VIDEO_4',
    'VIDEO 5': 'SOURCE_VIDEO_5',
    'MULTI': 'SOURCE_MULTI_INPUT',
}

CONF_SOURCE_ALIASES = "source_aliases"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SOURCE_ALIASES): vol.Schema(
        {vol.Any(*ROTEL_RSP1570_SOURCES.keys()): vol.Any(str, None)}),
})

ATTR_SOURCE_NAME = "source_name"
ATTR_VOLUME = "volume"
ATTR_MUTE_ON = "mute_on"
ATTR_PARTY_MODE_ON = "party_mode_on"
ATTR_INFO = "info"
ATTR_ICONS = "icons"
ATTR_SPEAKER_ICONS = "speaker_icons"
ATTR_STATE_ICONS = "state_icons"
ATTR_INPUT_ICONS = "input_icons"
ATTR_SOUND_MODE_ICONS = "sound_mode_icons"
ATTR_MISC_ICONS = "misc_icons"
ATTR_TRIGGERS = "triggers"

ATTR_COMMAND_NAME = "command_name"
SERVICE_SEND_COMMAND = "rotel_send_command"
SERVICE_SEND_COMMAND_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids,
    vol.Required(ATTR_COMMAND_NAME): cv.string,
})
SERVICE_RECONNECT = "rotel_reconnect"
SERVICE_RECONNECT_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids,
})


async def async_setup_platform(
        hass,
        config,
        async_add_entities,
        discovery_info=None):
    """Set up the rsp1570serial platform."""
    # pylint: disable=unused-argument

    device = RotelRSP1570Device(
        config.get(CONF_NAME),
        config.get(CONF_DEVICE),
        config.get(CONF_SOURCE_ALIASES))

    async def handle_hass_stop_event(event):
        """Clean up when hass stops."""
        await device.cleanup()

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP,
        handle_hass_stop_event)
    _LOGGER.debug("Registered device '%s' for HASS stop event", device.name)

    await device.open_connection()

    async_add_entities([device])
    device.start_read_messages(hass)
    setup_hass_services(hass)


def setup_hass_services(hass):
    """
    Register services.

    Note that this function is called for every entity but it
    only needs to be called once for the platform.
    It doesn't seem to do any harm but I'd like to tidy that up at some point.
    """
    _LOGGER.debug("Setting up hass services")

    async def async_handle_send_command(entity, call):
        command_name = call.data.get(ATTR_COMMAND_NAME)
        if isinstance(entity, RotelRSP1570Device):
            _LOGGER.debug(
                "%s service sending command %s to entity %s",
                SERVICE_SEND_COMMAND,
                command_name,
                entity.entity_id)
            await entity.send_command(command_name)
        else:
            _LOGGER.debug(
                "%s service not sending command %s to incompatible entity %s",
                SERVICE_SEND_COMMAND,
                command_name,
                entity.entity_id)

    async def async_handle_reconnect(entity, call):
        # pylint: disable=unused-argument
        if isinstance(entity, RotelRSP1570Device):
            _LOGGER.debug("%s service reconnecting entity %s",
                          SERVICE_RECONNECT, entity.entity_id)
            await entity.reconnect()
        else:
            _LOGGER.debug("%s service not reconnecting incompatible entity %s",
                          SERVICE_RECONNECT, entity.entity_id)

    component = hass.data[DOMAIN]
    component.async_register_entity_service(
        SERVICE_SEND_COMMAND, SERVICE_SEND_COMMAND_SCHEMA,
        async_handle_send_command)
    component.async_register_entity_service(
        SERVICE_RECONNECT, SERVICE_RECONNECT_SCHEMA,
        async_handle_reconnect)


class RotelRSP1570Device(MediaPlayerDevice):
    """Representation of a Rotel RSP-1570 device."""

    # pylint: disable=abstract-method
    # pylint: disable=too-many-public-methods
    # pylint: disable=too-many-instance-attributes

    def __init__(self, name, device, source_aliases):
        """Initialize the Rotel RSP-1570 device."""
        self._name = name
        self._device = device
        self._conn = None  # Make sure that you call open_connection...
        self._read_messages_task = None  # ... and start_read_messages
        self._state = STATE_OFF
        self._source_name = None
        self._volume = None
        self.set_source_lists(source_aliases)
        self._mute_on = None
        self._party_mode_on = None
        self._info = None
        self._icons = None
        self._speaker_icons = None
        self._state_icons = None
        self._input_icons = None
        self._sound_mode_icons = None
        self._misc_icons = None
        self._triggers = None

    @property
    def should_poll(self) -> bool:
        """Do not poll because this entity pushes its state to HA."""
        return False

    async def open_connection(self):
        """Open a connection to the device."""
        from rsp1570serial.connection import RotelAmpConn
        conn = RotelAmpConn(self._device)
        try:
            await conn.open()
        except Exception:
            _LOGGER.error("Could not open connection", exc_info=True)
            raise
        self._conn = conn

    def close_connection(self):
        """Close the connection to the device."""
        if self._conn is not None:
            self._conn.close()

    def start_read_messages(self, hass):
        """Create a task to start reading messages."""
        self._read_messages_task = hass.loop.create_task(
            self.async_read_messages()
        )

    async def cancel_read_messages(self):
        """Cancel the _read_messages_task."""
        if self._read_messages_task is not None:
            _LOGGER.info("Cancelling read_messages task.  Done was: %r.",
                         self._read_messages_task.done())
            if not self._read_messages_task.done():
                self._read_messages_task.cancel()
                await self._read_messages_task
            else:
                ex = self._read_messages_task.exception()
                if ex is not None:
                    _LOGGER.error(
                        "Read messages task contained an exception.",
                        exc_info=ex)
            self._read_messages_task = None

    async def async_read_messages(self):
        """
        Read messages published by the device.

        Read messages published by the device and use them to maintain the
        state of this object.
        Schedule a DISPLAY_REFRESH command before we start reading.
        If the device is already on then this is a null command that will
        simply trigger a feedback message that will sync the state of this
        object with the physical device.
        """
        _LOGGER.info("Message reader started for %s.", self.name)
        try:
            await self.send_command('DISPLAY_REFRESH')
            async for message in self._conn.read_messages():
                _LOGGER.debug("Message received by %s.", self.name)
                self.handle_message(message)
        except asyncio.CancelledError:
            _LOGGER.info("Message reader cancelled for %s", self.name)
        except Exception:
            _LOGGER.error((
                "Message reader for '%s' exiting due to unexpected exception. "
                "Message reader can be reinstated by calling '%s' service."
            ), self.name, SERVICE_RECONNECT)
            raise

    async def reconnect(self):
        """
        Reconnect.

        Don't call this more often than needed - it is asynchronous
        and it doesn't check for activity in progress on the connection
        so there could be a risk of a conflict.
        """
        await self.cancel_read_messages()

        # Ignore any errors while closing the connection because
        # the reason we'd be doing this would probably be due to some
        # sort of issue with the existing connection anyway.
        try:
            self.close_connection()
        # pylint: disable=broad-except
        except Exception:
            _LOGGER.error("Could not close connection", exc_info=True)
            _LOGGER.warning("Ignoring error and attempting to reconnect")

        # Set the state to OFF by default
        # If the player is actually on then the state will be refreshed
        # when the message reader restarts
        self._state = STATE_OFF
        self.async_schedule_update_ha_state()

        await self.open_connection()

        # N.B. this line can only be executed after
        # async_add_entities has been called and completed
        # because otherwise self.hass won't be available.
        self.start_read_messages(self.hass)

    async def cleanup(self):
        """Close connection and stop message reader."""
        _LOGGER.info("Cleaning up '%s'", self.name)
        await self.cancel_read_messages()
        self.close_connection()
        _LOGGER.info("Finished cleaning up '%s'", self.name)

    def set_source_lists(self, source_aliases):
        """
        Set list of sources that can be selected.

        For sources that have an alias defined then let the user pick that
        instead. To use an alias for a source, provide an entry in the
        source_aliases map of the form <source>: <alias>
        To suppress a source, provide an entry in the source_aliases
        map of the form <source>: None
        Any sources not suppressed and not aliased will remain as-is
        Note that the amp could still be switched to one of the suppressed
        sources using the remote control or front panel.  The
        media player card seems to handle this gracefully enough.
        Example of using source_aliases in configuration.yaml:

        media_player:
        - platform: rotel_rsp1570
          device: /dev/ttyUSB0
          source_aliases:
            TAPE:
            MULTI:
            VIDEO 1: CATV
            VIDEO 2: NMT
            VIDEO 3: APPLE TV
            VIDEO 4: FIRE TV
            VIDEO 5: BLU RAY
        """
        _LOGGER.debug("source_aliases: %r", source_aliases)
        sources_to_select = {}
        aliased_sources = set()
        if source_aliases is not None:
            for source, alias in source_aliases.items():
                if alias is None:
                    aliased_sources.add(source)
                else:
                    aliased_sources.add(source)
                    sources_to_select[alias] = ROTEL_RSP1570_SOURCES[source]
        for source, cmd in ROTEL_RSP1570_SOURCES.items():
            if source not in aliased_sources:
                sources_to_select[source] = cmd
        _LOGGER.debug("Sources to select: %r", sources_to_select)
        self._sources_to_select = sources_to_select

    def handle_message(self, message):
        """Route each type of message to an appropriate handler."""
        from rsp1570serial.messages import FeedbackMessage, TriggerMessage
        if isinstance(message, FeedbackMessage):
            self.handle_feedback_message(message)
        elif isinstance(message, TriggerMessage):
            self.handle_trigger_message(message)
        else:
            _LOGGER.warning("Unknown message type encountered")

    def handle_feedback_message(self, message):
        """Map feedback message to object attributes."""
        fields = message.parse_display_lines()
        self._state = STATE_ON if fields['is_on'] else STATE_OFF
        self._source_name = fields['source_name']
        self._volume = fields['volume']
        _LOGGER.debug("Volume from amp is %r", self._volume)
        self._mute_on = fields['mute_on']
        self._party_mode_on = fields['party_mode_on']
        self._info = fields['info']
        self._icons = message.icons_that_are_on()

        def binary_sensor_value(icon_flag):
            return False if icon_flag is None else bool(icon_flag)

        self._speaker_icons = {
            k: binary_sensor_value(message.icons[k]) for k in (
                'CBL', 'CBR', 'SB', 'SL', 'SR', 'SW', 'FL', 'C', 'FR')}
        self._state_icons = {
            k: binary_sensor_value(message.icons[k]) for k in (
                'Standby LED', 'Zone', 'Zone 2', 'Zone 3', 'Zone 4',
                'Display Mode0', 'Display Mode1')}
        self._sound_mode_icons = {
            k: binary_sensor_value(message.icons[k]) for k in (
                'Pro Logic', 'II', 'x', 'Dolby Digital', 'dts', 'ES',
                'EX', '5.1', '7.1')}
        self._input_icons = {
            k: binary_sensor_value(message.icons[k]) for k in (
                'HDMI', 'Coaxial', 'Optical', 'A', '1', '2', '3', '4', '5')}
        # Not actually sure what these are.
        # Might move them if I ever work it out.
        self._misc_icons = {
            k: binary_sensor_value(message.icons[k]) for k in ('<', '>')}
        self.async_schedule_update_ha_state()

    def handle_trigger_message(self, message):
        """Map trigger message to object attributes."""
        self._triggers = message.flags_to_list(message.flags)
        self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_ROTEL_RSP1570

    @property
    def assumed_state(self):
        """Indicate that state is assumed."""
        return True

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    async def async_turn_on(self):
        """Turn the media player on."""
        await self._conn.send_command('POWER_ON')
        self._state = STATE_ON

    async def async_turn_off(self):
        """Turn off media player."""
        await self._conn.send_command('POWER_OFF')
        self._state = STATE_OFF

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return sorted((self._sources_to_select.keys()))

    @property
    def source(self):
        """Return the current input source."""
        return self._source_name

    async def async_select_source(self, source):
        """Select input source."""
        await self._conn.send_command(self._sources_to_select[source])

    async def async_volume_up(self):
        """Volume up media player."""
        await self._conn.send_command('VOLUME_UP')

    async def async_volume_down(self):
        """Volume down media player."""
        await self._conn.send_command('VOLUME_DOWN')

    async def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        # Note that the main zone has a MUTE_ON and MUTE_OFF command
        # Could switch to that instead but for now sticking with the
        # regular mute commands that affect whatever zone is on the
        # info display
        if self._mute_on is None:
            # Chances are that this is the right thing to do
            await self._conn.send_command('MUTE_TOGGLE')
        elif self._mute_on and not mute:
            await self._conn.send_command('MUTE_TOGGLE')
        elif not self._mute_on and mute:
            await self._conn.send_command('MUTE_TOGGLE')

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        if self.state == STATE_OFF:
            return None
        attributes = {
            ATTR_SOURCE_NAME: self._source_name,
            ATTR_VOLUME: self._volume,
            ATTR_PARTY_MODE_ON: self._party_mode_on,
            ATTR_INFO: self._info,
            ATTR_ICONS: self._icons,
            ATTR_SPEAKER_ICONS: self._speaker_icons,
            ATTR_STATE_ICONS: self._state_icons,
            ATTR_INPUT_ICONS: self._input_icons,
            ATTR_SOUND_MODE_ICONS: self._sound_mode_icons,
            ATTR_MISC_ICONS: self._misc_icons,
            ATTR_TRIGGERS: self._triggers,
        }
        return attributes

    @property
    def _volume_max(self):
        """Max volume level of the media player."""
        from rsp1570serial.commands import MAX_VOLUME
        return MAX_VOLUME

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._volume is None:
            return None
        return self._volume / self._volume_max

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        scaled_volume = round(volume * self._volume_max)
        _LOGGER.debug("Set volume to: %r", scaled_volume)
        await self._conn.send_volume_direct_command(1, scaled_volume)

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute_on

    async def send_command(self, command_name):
        """Send a command to the device."""
        await self._conn.send_command(command_name)
