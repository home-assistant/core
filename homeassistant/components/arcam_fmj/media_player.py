"""Arcam media player."""
import logging

from arcam.fmj import DecodeMode2CH, DecodeModeMCH, IncomingAudioFormat, SourceCodes
from arcam.fmj.state import State

from homeassistant import config_entries
from homeassistant.components.media_player import BrowseMedia, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_MUSIC,
    MEDIA_TYPE_MUSIC,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback

from .config_flow import get_entry_client
from .const import (
    DOMAIN,
    EVENT_TURN_ON,
    SIGNAL_CLIENT_DATA,
    SIGNAL_CLIENT_STARTED,
    SIGNAL_CLIENT_STOPPED,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Set up the configuration entry."""

    client = get_entry_client(hass, config_entry)

    async_add_entities(
        [
            ArcamFmj(
                config_entry.title,
                State(client, zone),
                config_entry.unique_id or config_entry.entry_id,
            )
            for zone in [1, 2]
        ],
        True,
    )

    return True


class ArcamFmj(MediaPlayerEntity):
    """Representation of a media device."""

    _attr_should_poll = False
    _attr_supported_features = (
        SUPPORT_SELECT_SOURCE
        | SUPPORT_PLAY_MEDIA
        | SUPPORT_BROWSE_MEDIA
        | SUPPORT_VOLUME_SET
        | SUPPORT_VOLUME_MUTE
        | SUPPORT_VOLUME_STEP
        | SUPPORT_TURN_OFF
        | SUPPORT_TURN_ON
    )

    def __init__(
        self,
        device_name,
        state: State,
        uuid: str,
    ):
        """Initialize device."""
        self._state = state
        self._device_name = device_name
        self._uuid = uuid
        if state.zn == 1:
            self._attr_supported_features |= SUPPORT_SELECT_SOUND_MODE
        self._attr_entity_registry_enabled_default = self._state.zn == 1
        self._attr_unique_id = f"{self._uuid}-{self._state.zn}"
        self._attr_name = f"{device_name} - Zone: {state.zn}"

    def _get_2ch(self):
        """Return if source is 2 channel or not."""
        audio_format, _ = self._state.get_incoming_audio_format()
        return bool(
            audio_format
            in (
                IncomingAudioFormat.PCM,
                IncomingAudioFormat.ANALOGUE_DIRECT,
                IncomingAudioFormat.UNDETECTED,
                None,
            )
        )

    async def async_added_to_hass(self):
        """Once registered, add listener for events."""
        await self._state.start()

        @callback
        def _data(host):
            if host == self._state.client.host:
                self.async_write_ha_state()

        @callback
        def _started(host):
            if host == self._state.client.host:
                self.async_schedule_update_ha_state(force_refresh=True)

        @callback
        def _stopped(host):
            if host == self._state.client.host:
                self.async_schedule_update_ha_state(force_refresh=True)

        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_CLIENT_DATA, _data
            )
        )

        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_CLIENT_STARTED, _started
            )
        )

        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_CLIENT_STOPPED, _stopped
            )
        )

    async def async_update(self):
        """Force update of state."""
        _LOGGER.debug("Update state %s", self.name)
        await self._state.update()
        self._attr_state = STATE_ON if self._state.get_power() else STATE_OFF
        self._attr_device_info = {
            "name": self._device_name,
            "identifiers": {
                (DOMAIN, self._uuid),
                (DOMAIN, self._state.client.host, self._state.client.port),
            },
            "model": "Arcam FMJ AVR",
            "manufacturer": "Arcam",
        }
        source = self._state.get_source()
        self._attr_source = source.name if source else None
        self._attr_source_list = [x.name for x in self._state.get_source_list()]
        if self._state.zn == 1:
            if self._get_2ch():
                value = self._state.get_decode_mode_2ch()
                self._attr_sound_mode_list = [x.name for x in DecodeMode2CH]
            else:
                value = self._state.get_decode_mode_mch()
                self._attr_sound_mode_list = [x.name for x in DecodeModeMCH]
            self._attr_sound_mode = value.name if value else None
        else:
            self._attr_sound_mode = self._attr_sound_mode_list = None
        value = self._state.get_mute()
        self._attr_is_volume_muted = value if value else None
        value = self._state.get_volume()
        self._attr_volume_level = value / 99.0 if value else None
        if source == SourceCodes.DAB:
            self._attr_media_content_type = MEDIA_TYPE_MUSIC
            self._attr_media_channel = self._state.get_dab_station()
            self._attr_media_artist = self._state.get_dls_pdt()
        elif source == SourceCodes.FM:
            self._attr_media_content_type = MEDIA_TYPE_MUSIC
            self._attr_media_channel = self._state.get_rds_information()
        else:
            self._attr_media_content_type = (
                self._attr_media_channel
            ) = self._attr_media_artist = None
        if source in (SourceCodes.DAB, SourceCodes.FM):
            preset = self._state.get_tuner_preset()
            self._attr_media_content_id = f"preset:{preset}" if preset else None
        else:
            self._attr_media_content_id = None
        if source:
            channel = self._attr_media_channel
            if channel:
                self._attr_media_title = f"{source.name} - {channel}"
            else:
                self._attr_media_title = source.name
        else:
            self._attr_media_title = None

    async def async_mute_volume(self, mute):
        """Send mute command."""
        await self._state.set_mute(mute)
        self.async_write_ha_state()

    async def async_select_source(self, source):
        """Select a specific source."""
        try:
            value = SourceCodes[source]
        except KeyError:
            _LOGGER.error("Unsupported source %s", source)
            return

        await self._state.set_source(value)
        self.async_write_ha_state()

    async def async_select_sound_mode(self, sound_mode):
        """Select a specific source."""
        try:
            if self._get_2ch():
                await self._state.set_decode_mode_2ch(DecodeMode2CH[sound_mode])
            else:
                await self._state.set_decode_mode_mch(DecodeModeMCH[sound_mode])
        except KeyError:
            _LOGGER.error("Unsupported sound_mode %s", sound_mode)
            return

        self.async_write_ha_state()

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self._state.set_volume(round(volume * 99.0))
        self.async_write_ha_state()

    async def async_volume_up(self):
        """Turn volume up for media player."""
        await self._state.inc_volume()
        self.async_write_ha_state()

    async def async_volume_down(self):
        """Turn volume up for media player."""
        await self._state.dec_volume()
        self.async_write_ha_state()

    async def async_turn_on(self):
        """Turn the media player on."""
        if self._state.get_power() is not None:
            _LOGGER.debug("Turning on device using connection")
            await self._state.set_power(True)
        else:
            _LOGGER.debug("Firing event to turn on device")
            self.hass.bus.async_fire(EVENT_TURN_ON, {ATTR_ENTITY_ID: self.entity_id})

    async def async_turn_off(self):
        """Turn the media player off."""
        await self._state.set_power(False)

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""
        if media_content_id not in (None, "root"):
            raise BrowseError(
                f"Media not found: {media_content_type} / {media_content_id}"
            )

        presets = self._state.get_preset_details()

        radio = [
            BrowseMedia(
                title=preset.name,
                media_class=MEDIA_CLASS_MUSIC,
                media_content_id=f"preset:{preset.index}",
                media_content_type=MEDIA_TYPE_MUSIC,
                can_play=True,
                can_expand=False,
            )
            for preset in presets.values()
        ]

        root = BrowseMedia(
            title="Root",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="root",
            media_content_type="library",
            can_play=False,
            can_expand=True,
            children=radio,
        )

        return root

    async def async_play_media(self, media_type: str, media_id: str, **kwargs) -> None:
        """Play media."""

        if media_id.startswith("preset:"):
            preset = int(media_id[7:])
            await self._state.set_tuner_preset(preset)
        else:
            _LOGGER.error("Media %s is not supported", media_id)
            return
