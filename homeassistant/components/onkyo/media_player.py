"""Support for Onkyo Receivers."""

from __future__ import annotations

import logging
from typing import Any

import eiscp
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_MODEL
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_AUDIO_INFORMATION,
    ATTR_HDMI_OUTPUT,
    ATTR_PRESET,
    ATTR_VIDEO_INFORMATION,
    ATTR_VIDEO_OUT,
    CONF_MAXIMUM_VOLUME,
    CONF_MAXIMUM_VOLUME_DEFAULT,
    CONF_RECEIVER_MAXIMUM_VOLUME,
    CONF_RECEIVER_MAXIMUM_VOLUME_DEFAULT,
    CONF_SOUND_MODE_LIST,
    CONF_SOUND_MODE_LIST_DEFAULT,
    CONF_SOURCES,
    CONF_SOURCES_DEFAULT,
    DEFAULT_PLAYABLE_SOURCES,
    HDMI_OUTPUT_ACCEPTED_VALUES,
    MAXIMUM_UPDATE_RETRIES,
    SERVICE_EISCP_COMMAND,
    SERVICE_SELECT_HDMI_OUTPUT,
    TIMEOUT_MESSAGE,
)
from .entity import OnkyoEntity

_LOGGER = logging.getLogger(__name__)

ONKYO_SELECT_OUTPUT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_HDMI_OUTPUT): vol.In(HDMI_OUTPUT_ACCEPTED_VALUES),
    }
)
ONKYO_EISCP_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required("command"): str,
    }
)

SUPPORT_ONKYO_WO_VOLUME = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY_MEDIA
)
SUPPORT_ONKYO = (
    SUPPORT_ONKYO_WO_VOLUME
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_STEP
)


def _parse_onkyo_payload(payload):
    """Parse a payload returned from the eiscp library."""
    if isinstance(payload, bool):
        # command not supported by the device
        return False

    if len(payload) < 2:
        # no value
        return None

    if isinstance(payload[1], str):
        return payload[1].split(",")

    return payload[1]


def _tuple_get(tup, index, default=None):
    """Return a tuple item at index or a default value if it doesn't exist."""
    return (tup[index : index + 1] or [default])[0]


def determine_zones(receiver):
    """Determine what zones are available for the receiver."""
    out = {"zone2": False, "zone3": False}
    try:
        _LOGGER.debug("Checking for zone 2 capability")
        response = receiver.raw("ZPWQSTN")
        if response != "ZPWN/A":  # Zone 2 Available
            out["zone2"] = True
        else:
            _LOGGER.debug("Zone 2 not available")
    except ValueError as error:
        if str(error) != TIMEOUT_MESSAGE:
            raise
        _LOGGER.debug("Zone 2 timed out, assuming no functionality")
    try:
        _LOGGER.debug("Checking for zone 3 capability")
        response = receiver.raw("PW3QSTN")
        if response != "PW3N/A":  # Zone 3 Available
            out["zone3"] = True
        else:
            _LOGGER.debug("Zone 3 not available")
    except ValueError as error:
        if str(error) != TIMEOUT_MESSAGE:
            raise
        _LOGGER.debug("Zone 3 timed out, assuming no functionality")
    except AssertionError:
        _LOGGER.error("Zone 3 detection failed")

    return out


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Onkyo Platform from config_flow."""

    hosts: list[OnkyoDevice] = []
    platform = entity_platform.async_get_current_platform()

    def select_output_service(
        entity: OnkyoDevice, call: ServiceCall
    ) -> ServiceResponse:
        """Handle for services."""
        entity.select_output(call.data[ATTR_HDMI_OUTPUT])
        return None

    platform.async_register_entity_service(
        name=SERVICE_SELECT_HDMI_OUTPUT,
        schema=ONKYO_SELECT_OUTPUT_SCHEMA,
        func=select_output_service,
    )

    def command_service(entity: OnkyoDevice, call: ServiceCall) -> ServiceResponse:
        """Handle for services."""

        raw_response = entity.command(call.data["command"])
        if not raw_response:
            raise HomeAssistantError("Request failed")

        key, _ = raw_response
        value = _parse_onkyo_payload(raw_response)

        if len(value) == 1:
            value = value[0]

        return {key: value}

    platform.async_register_entity_service(
        name=SERVICE_EISCP_COMMAND,
        schema=ONKYO_EISCP_COMMAND_SCHEMA,
        func=command_service,
        supports_response=SupportsResponse.ONLY,
    )

    host = entry.data[CONF_HOST]
    try:
        receiver = eiscp.eISCP(host)
        hosts.append(
            OnkyoDevice(
                entry,
                receiver,
            )
        )

        zones = determine_zones(receiver)

        # Add Zone2 if available
        if zones["zone2"]:
            _LOGGER.debug("Setting up zone 2")
            hosts.append(
                OnkyoDeviceZone(
                    entry,
                    receiver,
                    2,
                )
            )
        # Add Zone3 if available
        if zones["zone3"]:
            _LOGGER.debug("Setting up zone 3")
            hosts.append(
                OnkyoDeviceZone(
                    entry,
                    receiver,
                    3,
                )
            )
    except OSError:
        _LOGGER.error("Unable to connect to receiver at %s", host)
        raise

    async_add_entities(hosts, update_before_add=True)


class OnkyoDevice(OnkyoEntity, MediaPlayerEntity):
    """Representation of an Onkyo device."""

    _attr_supported_features = SUPPORT_ONKYO
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER

    _attr_name = None

    def __init__(self, entry: ConfigEntry, receiver: eiscp.eISCP) -> None:
        """Initialize the Onkyo Receiver."""
        super().__init__(entry.data)

        self._receiver = receiver
        self._failed_updates = 0

        self._model_name = entry.data[CONF_MODEL]
        self._attr_is_volume_muted = False
        self._attr_volume_level = 0
        self._attr_state = MediaPlayerState.OFF

        self._max_volume = (
            entry.options.get(CONF_MAXIMUM_VOLUME) or CONF_MAXIMUM_VOLUME_DEFAULT
        )
        self._receiver_max_volume = (
            entry.options.get(CONF_RECEIVER_MAXIMUM_VOLUME)
            or CONF_RECEIVER_MAXIMUM_VOLUME_DEFAULT
        )
        self._source_mapping = entry.options.get(CONF_SOURCES) or CONF_SOURCES_DEFAULT
        self._attr_source_list = list(self._source_mapping.values())
        self._reverse_source_mapping = {
            value: key for key, value in self._source_mapping.items()
        }
        self._sound_mode_list_mapping = (
            entry.options.get(CONF_SOUND_MODE_LIST) or CONF_SOUND_MODE_LIST_DEFAULT
        )
        self._attr_sound_mode_list = list(self._sound_mode_list_mapping.values())
        self._reverse_sound_mode_list_mapping = {
            value: key for key, value in self._sound_mode_list_mapping.items()
        }
        self._attr_extra_state_attributes = {}
        self._hdmi_out_supported = True
        self._audio_info_supported = True
        self._video_info_supported = True

    def command(self, command):
        """Run an eiscp command and catch connection errors."""
        try:
            result = self._receiver.command(command)
        except (ValueError, OSError, AttributeError, AssertionError, TypeError):
            if self._receiver.command_socket:
                self._receiver.command_socket = None
                _LOGGER.debug("Resetting connection to %s", self.unique_id)
            else:
                _LOGGER.info(
                    "%s is disconnected. Attempting to reconnect", self.unique_id
                )
            return False
        _LOGGER.debug("Result for %s: %s", command, result)
        return result

    def update(self) -> None:
        """Get the latest state from the device."""
        status = self.command("system-power query")

        if not status:
            self._failed_updates += 1
            if self._failed_updates > MAXIMUM_UPDATE_RETRIES:
                self._attr_available = False
            return

        self._failed_updates = 0
        self._attr_available = True
        if status[1] == "on":
            self._attr_state = MediaPlayerState.ON
        else:
            self._attr_state = MediaPlayerState.OFF
            self._attr_extra_state_attributes.pop(ATTR_AUDIO_INFORMATION, None)
            self._attr_extra_state_attributes.pop(ATTR_VIDEO_INFORMATION, None)
            self._attr_extra_state_attributes.pop(ATTR_PRESET, None)
            self._attr_extra_state_attributes.pop(ATTR_VIDEO_OUT, None)
            return

        volume_raw = self.command("volume query")
        mute_raw = self.command("audio-muting query")
        current_source_raw = self.command("input-selector query")
        current_sound_mode_raw = self.command("listening-mode query")
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
            self._parse_audio_information(audio_information_raw)
        if self._video_info_supported:
            video_information_raw = self.command("video-information query")
            self._parse_video_information(video_information_raw)
        if not (volume_raw and mute_raw and current_source_raw):
            return

        sources = _parse_onkyo_payload(current_source_raw)
        if sources:
            for source in sources:
                if source in self._source_mapping:
                    self._attr_source = self._source_mapping[source]
                    break
                self._attr_source = "_".join(sources)

        sound_modes = _parse_onkyo_payload(current_sound_mode_raw)
        if sound_modes:
            for sound_mode in sound_modes:
                if sound_mode in self._sound_mode_list_mapping:
                    self._attr_sound_mode = self._sound_mode_list_mapping[sound_mode]
                    break
                self._attr_sound_mode = "_".join(sound_modes)

        if preset_raw and self.source and self.source.lower() == "radio":
            self._attr_extra_state_attributes[ATTR_PRESET] = preset_raw[1]
        elif ATTR_PRESET in self._attr_extra_state_attributes:
            del self._attr_extra_state_attributes[ATTR_PRESET]

        self._attr_is_volume_muted = bool(mute_raw[1] == "on")
        #   AMP_VOL/MAX_RECEIVER_VOL*(MAX_VOL/100)
        self._attr_volume_level = volume_raw[1] / (
            self._receiver_max_volume * self._max_volume / 100
        )

        if not hdmi_out_raw:
            self._hdmi_out_supported = False
            return
        self._attr_extra_state_attributes[ATTR_VIDEO_OUT] = ",".join(hdmi_out_raw[1])
        if hdmi_out_raw[1] == "N/A":
            self._hdmi_out_supported = False

    def turn_on(self) -> None:
        """Turn the media player on."""
        self.command("system-power on")

    def turn_off(self) -> None:
        """Turn the media player off."""
        self.command("system-power standby")

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, input is range 0..1.

        However full volume on the amp is usually far too loud so allow the user to
        specify the upper range with CONF_MAX_VOLUME. We change as per max_volume
        set by user. This means that if max volume is 80 then full volume in HA will
        give 80% volume on the receiver. Then we convert that to the correct scale
        for the receiver.
        """
        #        HA_VOL * (MAX VOL / 100) * MAX_RECEIVER_VOL
        self.command(
            "volume"
            f" {int(volume * (self._max_volume / 100) * self._receiver_max_volume)}"
        )

    def volume_up(self) -> None:
        """Increase volume by 1 step."""
        self.command("volume level-up")

    def volume_down(self) -> None:
        """Decrease volume by 1 step."""
        self.command("volume level-down")

    def mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        if mute:
            self.command("audio-muting on")
        else:
            self.command("audio-muting off")

    def select_source(self, source: str) -> None:
        """Set the input source."""
        if self.source_list and source in self.source_list:
            source = self._reverse_source_mapping[source]
        self.command(f"input-selector {source}")

    def select_sound_mode(self, sound_mode: str) -> None:
        """Set the sound mode."""
        if self.sound_mode_list and sound_mode in self.sound_mode_list:
            sound_mode = self._reverse_sound_mode_list_mapping[sound_mode]
        self.command(f"listening-mode {sound_mode}")

    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play radio station by preset number."""
        source = self._reverse_source_mapping[self._attr_source]
        if media_type.lower() == "radio" and source in DEFAULT_PLAYABLE_SOURCES:
            self.command(f"preset {media_id}")

    def select_output(self, output):
        """Set hdmi-out."""
        self.command(f"hdmi-output-selector={output}")

    def _parse_audio_information(self, audio_information_raw):
        values = _parse_onkyo_payload(audio_information_raw)
        if values is False:
            self._audio_info_supported = False
            return

        if values:
            info = {
                "format": _tuple_get(values, 1),
                "input_frequency": _tuple_get(values, 2),
                "input_channels": _tuple_get(values, 3),
                "listening_mode": _tuple_get(values, 4),
                "output_channels": _tuple_get(values, 5),
                "output_frequency": _tuple_get(values, 6),
            }
            self._attr_extra_state_attributes[ATTR_AUDIO_INFORMATION] = info
        else:
            self._attr_extra_state_attributes.pop(ATTR_AUDIO_INFORMATION, None)

    def _parse_video_information(self, video_information_raw):
        values = _parse_onkyo_payload(video_information_raw)
        if values is False:
            self._video_info_supported = False
            return

        if values:
            info = {
                "input_resolution": _tuple_get(values, 1),
                "input_color_schema": _tuple_get(values, 2),
                "input_color_depth": _tuple_get(values, 3),
                "output_resolution": _tuple_get(values, 5),
                "output_color_schema": _tuple_get(values, 6),
                "output_color_depth": _tuple_get(values, 7),
                "picture_mode": _tuple_get(values, 8),
            }
            self._attr_extra_state_attributes[ATTR_VIDEO_INFORMATION] = info
        else:
            self._attr_extra_state_attributes.pop(ATTR_VIDEO_INFORMATION, None)


class OnkyoDeviceZone(OnkyoDevice):
    """Representation of an Onkyo device's extra zone."""

    def __init__(self, entry: ConfigEntry, receiver: eiscp.eISCP, zone: int) -> None:
        """Initialize the Zone with the zone identifier."""
        self._zone: int = zone
        self._supports_volume: bool = True
        super().__init__(entry, receiver)

        self._attr_unique_id = f"{self._attr_unique_id}_zone{self._zone}"

    @property
    def name(self):
        """Name of the zone with its number."""
        return f"Zone {self._zone}"

    def update(self) -> None:
        """Get the latest state from the device."""
        status = self.command(f"zone{self._zone}.power=query")

        if not status:
            return
        if status[1] == "on":
            self._attr_state = MediaPlayerState.ON
        else:
            self._attr_state = MediaPlayerState.OFF
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
                self._attr_source = self._source_mapping[source]
                break
            self._attr_source = "_".join(current_source_tuples[1])
        self._attr_is_volume_muted = bool(mute_raw[1] == "on")
        if preset_raw and self.source and self.source.lower() == "radio":
            self._attr_extra_state_attributes[ATTR_PRESET] = preset_raw[1]
        elif ATTR_PRESET in self._attr_extra_state_attributes:
            del self._attr_extra_state_attributes[ATTR_PRESET]
        if self._supports_volume:
            # AMP_VOL/MAX_RECEIVER_VOL*(MAX_VOL/100)
            self._attr_volume_level = (
                volume_raw[1] / self._receiver_max_volume * (self._max_volume / 100)
            )

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return media player features that are supported."""
        if self._supports_volume:
            return SUPPORT_ONKYO
        return SUPPORT_ONKYO_WO_VOLUME

    def turn_off(self) -> None:
        """Turn the media player off."""
        self.command(f"zone{self._zone}.power=standby")

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, input is range 0..1.

        However full volume on the amp is usually far too loud so allow the user to
        specify the upper range with CONF_MAX_VOLUME. We change as per max_volume
        set by user. This means that if max volume is 80 then full volume in HA
        will give 80% volume on the receiver. Then we convert that to the correct
        scale for the receiver.
        """
        # HA_VOL * (MAX VOL / 100) * MAX_RECEIVER_VOL
        self.command(
            f"zone{self._zone}.volume={int(volume * (self._max_volume / 100) * self._receiver_max_volume)}"
        )

    def volume_up(self) -> None:
        """Increase volume by 1 step."""
        self.command(f"zone{self._zone}.volume=level-up")

    def volume_down(self) -> None:
        """Decrease volume by 1 step."""
        self.command(f"zone{self._zone}.volume=level-down")

    def mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        if mute:
            self.command(f"zone{self._zone}.muting=on")
        else:
            self.command(f"zone{self._zone}.muting=off")

    def turn_on(self) -> None:
        """Turn the media player on."""
        self.command(f"zone{self._zone}.power=on")

    def select_source(self, source: str) -> None:
        """Set the input source."""
        if self.source_list and source in self.source_list:
            source = self._reverse_source_mapping[source]
        self.command(f"zone{self._zone}.selector={source}")
