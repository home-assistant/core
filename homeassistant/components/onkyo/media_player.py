"""Support for Onkyo Receivers."""
from __future__ import annotations

import logging
from typing import Callable, List

import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import (
    ACCEPTED_VALUES,
    ATTR_HDMI_OUTPUT,
    ATTR_PRESET,
    CONF_MAX_VOLUME,
    CONF_RECEIVER_MAX_VOLUME,
    CONF_SOURCES,
    DEFAULT_NAME,
    DEFAULT_PLAYABLE_SOURCES,
    DEFAULT_RECEIVER_MAX_VOLUME,
    DOMAIN,
    SERVICE_SELECT_HDMI_OUTPUT,
    SUPPORT_ONKYO,
    SUPPORT_ONKYO_WO_VOLUME,
    SUPPORTED_MAX_VOLUME,
    TIMEOUT_MESSAGE,
)

ONKYO_SELECT_OUTPUT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_HDMI_OUTPUT): vol.In(ACCEPTED_VALUES),
    }
)

_LOGGER = logging.getLogger(__name__)


def determine_zones(receiver) -> dict:
    """Determine what zones are available for the receiver."""
    out = []
    try:
        _LOGGER.debug("Checking for zone 2 capability")
        receiver.raw("ZPWQSTN")
        out.append(2)
    except ValueError as error:
        if str(error) != TIMEOUT_MESSAGE:
            raise error
        _LOGGER.debug("Zone 2 timed out, assuming no functionality")
    try:
        _LOGGER.debug("Checking for zone 3 capability")
        receiver.raw("PW3QSTN")
        out.append(3)
    except ValueError as error:
        if str(error) != TIMEOUT_MESSAGE:
            raise error
        _LOGGER.debug("Zone 3 timed out, assuming no functionality")
    except AssertionError:
        _LOGGER.error("Zone 3 detection failed")

    return out


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up the Onkyo entry."""
    entities = []
    receiver = hass.data[DOMAIN][config_entry.unique_id]
    entities.append(
        OnkyoDevice(
            receiver,
            config_entry.options.get(CONF_SOURCES),
            unique_id=config_entry.unique_id,
            name=config_entry.data.get(CONF_NAME, DEFAULT_NAME),
            max_volume=config_entry.data.get(CONF_MAX_VOLUME, SUPPORTED_MAX_VOLUME),
            receiver_max_volume=config_entry.data.get(
                CONF_RECEIVER_MAX_VOLUME, DEFAULT_RECEIVER_MAX_VOLUME
            ),
        )
    )
    zones = determine_zones(receiver)
    for zone in zones:
        entities.append(
            OnkyoDeviceZone(
                zone,
                receiver,
                config_entry.options.get(CONF_SOURCES),
                unique_id=config_entry.unique_id,
                name=config_entry.data.get(CONF_NAME, DEFAULT_NAME),
                max_volume=config_entry.data.get(CONF_MAX_VOLUME, SUPPORTED_MAX_VOLUME),
                receiver_max_volume=config_entry.data.get(
                    CONF_RECEIVER_MAX_VOLUME, DEFAULT_RECEIVER_MAX_VOLUME
                ),
            )
        )

    async def async_service_handler(service):
        """Handle for services."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        devices = [d for d in entities if d.entity_id in entity_ids]
        for device in devices:
            if service.service == SERVICE_SELECT_HDMI_OUTPUT:
                device.select_output(service.data.get(ATTR_HDMI_OUTPUT))

    hass.services.async_register(
        DOMAIN,
        SERVICE_SELECT_HDMI_OUTPUT,
        async_service_handler,
        schema=ONKYO_SELECT_OUTPUT_SCHEMA,
    )

    async_add_entities(entities, True)


class OnkyoDevice(MediaPlayerEntity):
    """Representation of an Onkyo device."""

    def __init__(
        self,
        receiver,
        sources,
        unique_id,
        name,
        max_volume=SUPPORTED_MAX_VOLUME,
        receiver_max_volume=DEFAULT_RECEIVER_MAX_VOLUME,
    ):
        """Initialize the Onkyo Receiver."""
        self._receiver = receiver
        self._muted = False
        self._volume = 0
        self._pwstate = STATE_OFF
        self._uid = receiver.info["identifier"]
        self._name = name
        self._max_volume = max_volume
        self._receiver_max_volume = receiver_max_volume
        self._current_source = None
        self._source_list = list(sources.values())
        self._source_mapping = sources
        self._reverse_mapping = {value: key for key, value in sources.items()}
        self._attributes = {}
        self._hdmi_out_supported = True
        self._unique_id = unique_id

    def command(self, command):
        """Run an eiscp command and catch connection errors."""
        try:
            result = self._receiver.command(command)
        except (ValueError, OSError, AttributeError, AssertionError):
            if self._receiver.command_socket:
                self._receiver.command_socket = None
                _LOGGER.debug("Resetting connection to %s", self._name)
            else:
                _LOGGER.info("%s is disconnected. Attempting to reconnect", self._name)
            return False
        _LOGGER.debug("Result for %s: %s", command, result)
        return result

    def update(self):
        """Get the latest state from the device."""
        status = self.command("system-power query")

        if not status:
            return
        if status[1] == "on":
            self._pwstate = STATE_ON
        else:
            self._pwstate = STATE_OFF
            self._attributes.pop(ATTR_AUDIO_INFORMATION, None)
            self._attributes.pop(ATTR_VIDEO_INFORMATION, None)
            self._attributes.pop(ATTR_PRESET, None)
            self._attributes.pop(ATTR_VIDEO_OUT, None)
            return

        volume_raw = self.command("volume query")
        mute_raw = self.command("audio-muting query")
        current_source_raw = self.command("input-selector query")
        # If the following command is sent to a device with only one HDMI out,
        # the display shows 'Not Available'.
        # We avoid this by checking if HDMI out is supported
        if self._hdmi_out_supported:
            hdmi_out_raw = self.command("hdmi-output-selector query")
        else:
            hdmi_out_raw = []
        preset_raw = self.command("preset query")
        if self._audio_info_supported:
            audio_information_raw = self.command("audio-information query")
        if self._video_info_supported:
            video_information_raw = self.command("video-information query")
        if not (volume_raw and mute_raw and current_source_raw):
            return

        sources = _parse_onkyo_payload(current_source_raw)

        for source in sources:
            if source in self._source_mapping:
                self._current_source = self._source_mapping[source]
                break
            self._current_source = "_".join(sources)

        if preset_raw and self._current_source.lower() == "radio":
            self._attributes[ATTR_PRESET] = preset_raw[1]
        elif ATTR_PRESET in self._attributes:
            del self._attributes[ATTR_PRESET]

        self._muted = bool(mute_raw[1] == "on")
        #       AMP_VOL/MAX_RECEIVER_VOL*(MAX_VOL/100)
        self._volume = volume_raw[1] / (
            self._receiver_max_volume * self._max_volume / 100
        )

        self._parse_audio_information(audio_information_raw)
        self._parse_video_information(video_information_raw)

        if not hdmi_out_raw:
            return
        self._attributes[ATTR_VIDEO_OUT] = ",".join(hdmi_out_raw[1])
        if hdmi_out_raw[1] == "N/A":
            self._hdmi_out_supported = False

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return self._unique_id

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
        return SUPPORT_ONKYO

    @property
    def source(self):
        """Return the current input source of the device."""
        return self._current_source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return self._attributes

    def turn_off(self):
        """Turn the media player off."""
        self.command("system-power standby")

    def set_volume_level(self, volume):
        """Set volume level, input is range 0..1.

        However full volume on the amp is usually far too loud so allow the user to specify the upper range
        with CONF_MAX_VOLUME.  we change as per max_volume set by user. This means that if max volume is 80 then full
        volume in HA will give 80% volume on the receiver. Then we convert
        that to the correct scale for the receiver.
        """
        #        HA_VOL * (MAX VOL / 100) * MAX_RECEIVER_VOL
        self.command(
            f"volume {int(volume * (self._max_volume / 100) * self._receiver_max_volume)}"
        )

    def volume_up(self):
        """Increase volume by 1 step."""
        self.command("volume level-up")

    def volume_down(self):
        """Decrease volume by 1 step."""
        self.command("volume level-down")

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        if mute:
            self.command("audio-muting on")
        else:
            self.command("audio-muting off")

    def turn_on(self):
        """Turn the media player on."""
        self.command("system-power on")

    def select_source(self, source):
        """Set the input source."""
        if source in self._source_list:
            source = self._reverse_mapping[source]
        self.command(f"input-selector {source}")

    def play_media(self, media_type, media_id, **kwargs):
        """Play radio station by preset number."""
        source = self._reverse_mapping[self._current_source]
        if media_type.lower() == "radio" and source in DEFAULT_PLAYABLE_SOURCES:
            self.command(f"preset {media_id}")

    def select_output(self, output):
        """Set hdmi-out."""
        self.command(f"hdmi-output-selector={output}")

    @property
    def device_info(self):
        """Return device information."""
        return {"identifiers": {(DOMAIN, self._uid)}}


class OnkyoDeviceZone(OnkyoDevice):
    """Representation of an Onkyo device's extra zone."""

    def __init__(
        self,
        zone,
        receiver,
        sources,
        unique_id,
        name,
        max_volume=SUPPORTED_MAX_VOLUME,
        receiver_max_volume=DEFAULT_RECEIVER_MAX_VOLUME,
    ):
        """Initialize the Zone with the zone identifier."""
        self._zone = zone
        self._supports_volume = True
        self._unique_id = unique_id
        super().__init__(
            receiver, sources, unique_id, name, max_volume, receiver_max_volume
        )

    def update(self):
        """Get the latest state from the device."""
        status = self.command(f"zone{self._zone}.power=query")

        if not status:
            return
        if status[1] == "on":
            self._pwstate = STATE_ON
        else:
            self._pwstate = STATE_OFF
            return

        volume_raw = self.command(f"zone{self._zone}.volume=query")
        mute_raw = self.command(f"zone{self._zone}.muting=query")
        current_source_raw = self.command(f"zone{self._zone}.selector=query")
        preset_raw = self.command(f"zone{self._zone}.preset=query")
        # If we received a source value, but not a volume value
        # it's likely this zone permanently does not support volume.
        if current_source_raw and not volume_raw:
            self._supports_volume = False

        if not (volume_raw and mute_raw and current_source_raw):
            return

        # It's possible for some players to have zones set to HDMI with
        # no sound control. In this case, the string `N/A` is returned.
        self._supports_volume = isinstance(volume_raw[1], (float, int))

        # eiscp can return string or tuple. Make everything tuples.
        if isinstance(current_source_raw[1], str):
            current_source_tuples = (current_source_raw[0], (current_source_raw[1],))
        else:
            current_source_tuples = current_source_raw

        for source in current_source_tuples[1]:
            if source in self._source_mapping:
                self._current_source = self._source_mapping[source]
                break
            self._current_source = "_".join(current_source_tuples[1])
        self._muted = bool(mute_raw[1] == "on")
        if preset_raw and self._current_source.lower() == "radio":
            self._attributes[ATTR_PRESET] = preset_raw[1]
        elif ATTR_PRESET in self._attributes:
            del self._attributes[ATTR_PRESET]
        if self._supports_volume:
            # AMP_VOL/MAX_RECEIVER_VOL*(MAX_VOL/100)
            self._volume = (
                volume_raw[1] / self._receiver_max_volume * (self._max_volume / 100)
            )

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self._name} Zone {self._zone}"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self._unique_id}_{self._zone}"

    @property
    def supported_features(self):
        """Return media player features that are supported."""
        if self._supports_volume:
            return SUPPORT_ONKYO
        return SUPPORT_ONKYO_WO_VOLUME

    def turn_off(self):
        """Turn the media player off."""
        self.command(f"zone{self._zone}.power=standby")

    def set_volume_level(self, volume):
        """Set volume level, input is range 0..1.

        However full volume on the amp is usually far too loud so allow the user to specify the upper range
        with CONF_MAX_VOLUME.  we change as per max_volume set by user. This means that if max volume is 80 then full
        volume in HA will give 80% volume on the receiver. Then we convert
        that to the correct scale for the receiver.
        """
        # HA_VOL * (MAX VOL / 100) * MAX_RECEIVER_VOL
        self.command(
            f"zone{self._zone}.volume={int(volume * (self._max_volume / 100) * self._receiver_max_volume)}"
        )

    def volume_up(self):
        """Increase volume by 1 step."""
        self.command(f"zone{self._zone}.volume=level-up")

    def volume_down(self):
        """Decrease volume by 1 step."""
        self.command(f"zone{self._zone}.volume=level-down")

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        if mute:
            self.command(f"zone{self._zone}.muting=on")
        else:
            self.command(f"zone{self._zone}.muting=off")

    def turn_on(self):
        """Turn the media player on."""
        self.command(f"zone{self._zone}.power=on")

    def select_source(self, source):
        """Set the input source."""
        if source in self._source_list:
            source = self._reverse_mapping[source]
        self.command(f"zone{self._zone}.selector={source}")
