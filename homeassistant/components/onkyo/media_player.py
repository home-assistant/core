"""Support for Onkyo Receivers."""
import logging
from typing import List

import eiscp
from eiscp import eISCP
import voluptuous as vol
import re

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    DOMAIN,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_SOURCES = "sources"
CONF_MAX_VOLUME = "max_volume"
CONF_RECEIVER_MAX_VOLUME = "receiver_max_volume"

DEFAULT_NAME = "Onkyo Receiver"
SUPPORTED_MAX_VOLUME = 100
DEFAULT_RECEIVER_MAX_VOLUME = 80

SUPPORT_ONKYO = (
    SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
)

SUPPORT_ONKYO_WO_VOLUME = (
    SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
)

KNOWN_HOSTS: List[str] = []
DEFAULT_SOURCES = {
    "tv": "TV",
    "bd": "Bluray",
    "game": "Game",
    "aux1": "Aux1",
    "video1": "Video 1",
    "video2": "Video 2",
    "video3": "Video 3",
    "video4": "Video 4",
    "video5": "Video 5",
    "video6": "Video 6",
    "video7": "Video 7",
    "fm": "Radio",
}

DEFAULT_PLAYABLE_SOURCES = ("fm", "am", "tuner")

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MAX_VOLUME, default=SUPPORTED_MAX_VOLUME): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
        vol.Optional(
            CONF_RECEIVER_MAX_VOLUME, default=DEFAULT_RECEIVER_MAX_VOLUME
        ): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(CONF_SOURCES, default=DEFAULT_SOURCES): {cv.string: cv.string},
    }
)

TIMEOUT_MESSAGE = "Timeout waiting for response."


ATTR_HDMI_OUTPUT = "hdmi_output"
ATTR_PRESET = "preset"

ACCEPTED_VALUES = [
    "no",
    "analog",
    "yes",
    "out",
    "out-sub",
    "sub",
    "hdbaset",
    "both",
    "up",
]
ONKYO_SELECT_OUTPUT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_HDMI_OUTPUT): vol.In(ACCEPTED_VALUES),
    }
)

SERVICE_SELECT_HDMI_OUTPUT = "onkyo_select_hdmi_output"

"""
The main zone will check for any new messages, and put them in this queue.
All other zones will pop from the queue if the update is for them.
"""
MSG_QUEUE = []


def iscp_to_command(iscp_message):
    """This is part of the eISCP library, but does not return the zone in their implementation. TODO: Open a change request in the source library"""
    command = None
    for zone, zone_cmds in eiscp.core.commands.COMMANDS.items():
        # For now, ISCP commands are always three characters, which
        # makes this easy.
        command, args = iscp_message[:3], iscp_message[3:]
        if command in zone_cmds:
            if args in zone_cmds[command]["values"]:
                command = (
                    zone,
                    zone_cmds[command]["name"],
                    zone_cmds[command]["values"][args]["name"],
                )
                break
            else:
                match = re.match("[+-]?[0-9a-f]+$", args, re.IGNORECASE)
                if match:
                    command = zone, zone_cmds[command]["name"], int(args, 16)
                    break
                else:
                    command = zone, zone_cmds[command]["name"], args
                    break
    else:
        raise ValueError(
            "Cannot convert ISCP message to command: {}".format(iscp_message)
        )
    return command


def determine_zones(receiver):
    """Determine what zones are available for the receiver."""
    out = {"zone2": False, "zone3": False}
    try:
        _LOGGER.debug("Checking for zone 2 capability")
        receiver.raw("ZPW")
        out["zone2"] = True
    except ValueError as error:
        if str(error) != TIMEOUT_MESSAGE:
            raise error
        _LOGGER.debug("Zone 2 timed out, assuming no functionality")
    try:
        _LOGGER.debug("Checking for zone 3 capability")
        receiver.raw("PW3")
        out["zone3"] = True
    except ValueError as error:
        if str(error) != TIMEOUT_MESSAGE:
            raise error
        _LOGGER.debug("Zone 3 timed out, assuming no functionality")
    return out


def query_volume_enabled(receiver, zones):
    """Send volume query requests to all enabled zones (except main)
    Zones will default to not supporting volume until a volume response arrives."""
    for zone in (zone for zone, enabled in zones.items() if enabled):
        try:
            iscp_command = eiscp.core.command_to_iscp(f"{zone}.volume=query")
            receiver.send(iscp_command)
        except (ValueError, OSError, AttributeError, AssertionError):
            _LOGGER.debug("An error occured sending a command")


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Onkyo platform."""
    host = config.get(CONF_HOST)
    hosts = []

    def service_handle(service):
        """Handle for services."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        devices = [d for d in hosts if d.entity_id in entity_ids]

        for device in devices:
            if service.service == SERVICE_SELECT_HDMI_OUTPUT:
                device.select_output(service.data.get(ATTR_HDMI_OUTPUT))

    hass.services.register(
        DOMAIN,
        SERVICE_SELECT_HDMI_OUTPUT,
        service_handle,
        schema=ONKYO_SELECT_OUTPUT_SCHEMA,
    )

    if CONF_HOST in config and host not in KNOWN_HOSTS:
        try:
            receiver = eiscp.eISCP(host)
            hosts.append(
                OnkyoDevice(
                    "main",
                    receiver,
                    config.get(CONF_SOURCES),
                    name=config.get(CONF_NAME),
                    max_volume=config.get(CONF_MAX_VOLUME),
                    receiver_max_volume=config.get(CONF_RECEIVER_MAX_VOLUME),
                )
            )
            KNOWN_HOSTS.append(host)

            zones = determine_zones(receiver)
            query_volume_enabled(receiver, zones)

            # Add Zone2 if available
            if zones["zone2"]:
                _LOGGER.debug("Setting up zone 2")
                hosts.append(
                    OnkyoDevice(
                        "zone2",
                        receiver,
                        config.get(CONF_SOURCES),
                        name=f"{config[CONF_NAME]} Zone 2",
                        max_volume=config.get(CONF_MAX_VOLUME),
                        receiver_max_volume=config.get(CONF_RECEIVER_MAX_VOLUME),
                    )
                )
            # Add Zone3 if available
            if zones["zone3"]:
                _LOGGER.debug("Setting up zone 3")
                hosts.append(
                    OnkyoDevice(
                        "zone3",
                        receiver,
                        config.get(CONF_SOURCES),
                        name=f"{config[CONF_NAME]} Zone 3",
                        max_volume=config.get(CONF_MAX_VOLUME),
                        receiver_max_volume=config.get(CONF_RECEIVER_MAX_VOLUME),
                    )
                )
        except OSError:
            _LOGGER.error("Unable to connect to receiver at %s", host)
    else:
        for receiver in eISCP.discover():
            if receiver.host not in KNOWN_HOSTS:
                hosts.append(OnkyoDevice("main", receiver, config.get(CONF_SOURCES)))
                KNOWN_HOSTS.append(receiver.host)
    add_entities(hosts, True)


class OnkyoDevice(MediaPlayerEntity):
    """Representation of an Onkyo device."""

    def __init__(
        self,
        zone,
        receiver,
        sources,
        name=None,
        max_volume=SUPPORTED_MAX_VOLUME,
        receiver_max_volume=DEFAULT_RECEIVER_MAX_VOLUME,
    ):
        """Initialize the Onkyo Receiver."""
        self._zone = zone
        self._receiver = receiver
        self._muted = False
        self._supports_volume = zone == "main"  # Main zone supports volume always
        self._volume = 0
        self._pwstate = STATE_OFF
        self._name = (
            name or f"{receiver.info['model_name']}_{receiver.info['identifier']}"
        )
        self._max_volume = max_volume
        self._receiver_max_volume = receiver_max_volume
        self._current_source = None
        self._source_list = list(sources.values())
        self._source_mapping = sources
        self._reverse_mapping = {value: key for key, value in sources.items()}
        self._attributes = {}

    def command(self, command):
        """Send a non-blocking request to the reciever."""
        try:
            iscp_command = eiscp.core.command_to_iscp(f"{self._zone}.{command}")
            self._receiver.send(iscp_command)
        except (ValueError, OSError, AttributeError, AssertionError):
            _LOGGER.debug("An error occured sending a command")

    def update(self):
        """Let the main zone do the querying"""
        _LOGGER.info("Updating %s", self._zone)

        if self._zone == "main":
            try:
                raw_update = self._receiver.get()
                while not (raw_update is None):
                    MSG_QUEUE.append(iscp_to_command(raw_update))
                    raw_update = self._receiver.get()
            except (AssertionError):
                _LOGGER.info("An assertion erorr occured")

        if MSG_QUEUE:
            zone, command, value = MSG_QUEUE[0]
            if zone == self._zone:
                MSG_QUEUE.pop(0)
                if command == "system-power":
                    if value == "on":
                        self._pwstate = STATE_ON
                    else:
                        self._pwstate = STATE_OFF
                elif command == "master-volume" or command == "volume":
                    self._supports_volume = True
                    self._volume = (
                        value / self._receiver_max_volume * (self._max_volume / 100)
                    )
                elif command == "audio-muting":
                    self._muted = bool(value == "on")
                elif command == "input-selector":
                    # eiscp can return string or tuple. Make everything tuples.
                    if isinstance(value, str):
                        current_source_tuples = (command, (value,))
                    else:
                        current_source_tuples = (command, value)

                    for source in current_source_tuples[1]:
                        if source in self._source_mapping:
                            self._current_source = self._source_mapping[source]
                            break
                        self._current_source = "_".join(current_source_tuples[1])
                elif command == "hdmi-output-selector":
                    self._attributes["video_out"] = ",".join(value)
                elif command == "preset":
                    if self._current_source.lower() == "radio":
                        self._attributes[ATTR_PRESET] = value
                    elif ATTR_PRESET in self._attributes:
                        del self._attributes[ATTR_PRESET]

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._pwstate

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Return boolean indicating mute status."""
        return self._muted

    @property
    def supported_features(self):
        """Return media player features that are supported."""
        if self._supports_volume:
            return SUPPORT_ONKYO
        return SUPPORT_ONKYO_WO_VOLUME

    @property
    def source(self):
        """Return the current input source of the device."""
        return self._current_source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return self._attributes

    def turn_off(self):
        """Turn the media player off."""
        self.command("system-power standby")

    def set_volume_level(self, volume):
        """
        Set volume level, input is range 0..1.

        However full volume on the amp is usually far too loud so allow the user to specify the upper range
        with CONF_MAX_VOLUME.  we change as per max_volume set by user. This means that if max volume is 80 then full
        volume in HA will give 80% volume on the receiver. Then we convert
        that to the correct scale for the receiver.
        """
        #        HA_VOL * (MAX VOL / 100) * MAX_RECEIVER_VOL
        self.command(
            f"volume={int(volume * (self._max_volume / 100) * self._receiver_max_volume)}"
        )

    def volume_up(self):
        """Increase volume by 1 step."""
        self.command("volume=level-up")

    def volume_down(self):
        """Decrease volume by 1 step."""
        self.command("volume=level-down")

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        if mute:
            self.command("audio-muting=on")
        else:
            self.command("audio-muting=off")

    def turn_on(self):
        """Turn the media player on."""
        self.command("power=on")

    def select_source(self, source):
        """Set the input source."""
        if source in self._source_list:
            source = self._reverse_mapping[source]
        self.command(f"input-selector={source}")

    def play_media(self, media_type, media_id, **kwargs):
        """Play radio station by preset number."""
        source = self._reverse_mapping[self._current_source]
        if media_type.lower() == "radio" and source in DEFAULT_PLAYABLE_SOURCES:
            self.command(f"preset={media_id}")

    def select_output(self, output):
        """Set hdmi-out."""
        self.command(f"hdmi-output-selector={output}")
