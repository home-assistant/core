"""Media player platform for the Denon RS-232 integration."""

import re
from typing import Any, Literal, cast, override

from denon_rs232 import (
    MIN_VOLUME_DB,
    VOLUME_DB_RANGE,
    DenonReceiver,
    InputSource,
    MainPlayer,
    ReceiverState,
    ZonePlayer,
)

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_flow import CONF_MODEL_NAME
from .const import DOMAIN, DenonRS232ConfigEntry

INPUT_SOURCE_DENON_TO_HA: dict[InputSource, str] = {
    InputSource.PHONO: "phono",
    InputSource.CD: "cd",
    InputSource.TUNER: "tuner",
    InputSource.DVD: "dvd",
    InputSource.VDP: "vdp",
    InputSource.TV: "tv",
    InputSource.DBS_SAT: "dbs_sat",
    InputSource.VCR_1: "vcr_1",
    InputSource.VCR_2: "vcr_2",
    InputSource.VCR_3: "vcr_3",
    InputSource.V_AUX: "v_aux",
    InputSource.CDR_TAPE1: "cdr_tape1",
    InputSource.MD_TAPE2: "md_tape2",
    InputSource.HDP: "hdp",
    InputSource.DVR: "dvr",
    InputSource.TV_CBL: "tv_cbl",
    InputSource.SAT: "sat",
    InputSource.NET_USB: "net_usb",
    InputSource.DOCK: "dock",
    InputSource.IPOD: "ipod",
    InputSource.BD: "bd",
    InputSource.SAT_CBL: "sat_cbl",
    InputSource.MPLAY: "mplay",
    InputSource.GAME: "game",
    InputSource.AUX1: "aux1",
    InputSource.AUX2: "aux2",
    InputSource.NET: "net",
    InputSource.BT: "bt",
    InputSource.USB_IPOD: "usb_ipod",
    InputSource.EIGHT_K: "eight_k",
    InputSource.PANDORA: "pandora",
    InputSource.SIRIUSXM: "siriusxm",
    InputSource.SPOTIFY: "spotify",
    InputSource.FLICKR: "flickr",
    InputSource.IRADIO: "iradio",
    InputSource.SERVER: "server",
    InputSource.FAVORITES: "favorites",
    InputSource.LASTFM: "lastfm",
    InputSource.XM: "xm",
    InputSource.SIRIUS: "sirius",
    InputSource.HDRADIO: "hdradio",
    InputSource.DAB: "dab",
}

TUNER_PRESETS_ROOT = "presets"
TUNER_FREQUENCY_MIN = 8750
TUNER_FREQUENCY_MAX = 10800
TUNER_FREQUENCY_LENGTH = 6
#: Reported frequencies at or above this value are AM, which is not supported.
TUNER_FREQUENCY_FM_MAX = 50000


def _tuner_frequency_to_mhz(frequency: str | None) -> str | None:
    """Convert a reported tuner frequency to MHz, or None if it is not FM."""
    if frequency is None or not frequency.isdigit():
        return None

    value = int(frequency)
    if value >= TUNER_FREQUENCY_FM_MAX:
        return None

    return f"{value / 100:.2f}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DenonRS232ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Denon RS-232 media player."""
    receiver = config_entry.runtime_data
    entities = [DenonRS232MediaPlayer(receiver, receiver.main, config_entry, "main")]

    if receiver.zone_2.power is not None:
        entities.append(
            DenonRS232MediaPlayer(receiver, receiver.zone_2, config_entry, "zone_2")
        )
    if receiver.zone_3.power is not None:
        entities.append(
            DenonRS232MediaPlayer(receiver, receiver.zone_3, config_entry, "zone_3")
        )

    async_add_entities(entities)


class DenonRS232MediaPlayer(MediaPlayerEntity):
    """Representation of a Denon receiver controlled over RS-232."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_has_entity_name = True
    _attr_translation_key = "receiver"
    _attr_should_poll = False

    _volume_min = MIN_VOLUME_DB
    _volume_range = VOLUME_DB_RANGE

    def __init__(
        self,
        receiver: DenonReceiver,
        player: MainPlayer | ZonePlayer,
        config_entry: DenonRS232ConfigEntry,
        zone: Literal["main", "zone_2", "zone_3"],
    ) -> None:
        """Initialize the media player."""
        self._receiver = receiver
        self._player = player
        self._is_main = zone == "main"

        model = receiver.model
        assert model is not None  # We always set this
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Denon",
            model_id=config_entry.data.get(CONF_MODEL_NAME),
        )
        self._attr_unique_id = f"{config_entry.entry_id}_{zone}"

        self._attr_source_list = sorted(
            INPUT_SOURCE_DENON_TO_HA[source] for source in model.input_sources
        )
        self._attr_supported_features = (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.SELECT_SOURCE
        )

        if zone == "main":
            self._attr_name = None
            self._attr_supported_features |= (
                MediaPlayerEntityFeature.VOLUME_MUTE
                | MediaPlayerEntityFeature.PLAY_MEDIA
                | MediaPlayerEntityFeature.BROWSE_MEDIA
            )
        else:
            self._attr_name = "Zone 2" if zone == "zone_2" else "Zone 3"

        self._async_update_from_player()

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to receiver state updates."""
        self.async_on_remove(self._receiver.subscribe(self._async_on_state_update))

    @callback
    def _async_on_state_update(self, state: ReceiverState | None) -> None:
        """Handle a state update from the receiver."""
        if state is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._async_update_from_player()
        self.async_write_ha_state()

    @callback
    def _async_update_from_player(self) -> None:
        """Update entity attributes from the shared player object."""
        if self._player.power is None:
            self._attr_state = None
        else:
            self._attr_state = (
                MediaPlayerState.ON if self._player.power else MediaPlayerState.OFF
            )

        source = self._player.input_source
        self._attr_source = INPUT_SOURCE_DENON_TO_HA.get(source) if source else None

        if source is InputSource.TUNER:
            self._attr_media_channel = _tuner_frequency_to_mhz(
                self._receiver.state.main_zone.tuner_frequency
            )
        else:
            self._attr_media_channel = None

        volume_min = self._player.volume_min
        volume_max = self._player.volume_max
        if volume_min is not None:
            self._volume_min = volume_min

            if volume_max is not None and volume_max > volume_min:
                self._volume_range = volume_max - volume_min

        volume = self._player.volume
        if volume is not None:
            self._attr_volume_level = (volume - self._volume_min) / self._volume_range
        else:
            self._attr_volume_level = None

        if self._is_main:
            self._attr_is_volume_muted = cast(MainPlayer, self._player).mute

    @override
    async def async_turn_on(self) -> None:
        """Turn the receiver on."""
        await self._player.power_on()

    @override
    async def async_turn_off(self) -> None:
        """Turn the receiver off."""
        await self._player.power_standby()

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        db = volume * self._volume_range + self._volume_min
        await self._player.set_volume(db)

    @override
    async def async_volume_up(self) -> None:
        """Volume up."""
        await self._player.volume_up()

    @override
    async def async_volume_down(self) -> None:
        """Volume down."""
        await self._player.volume_down()

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        player = cast(MainPlayer, self._player)
        if mute:
            await player.mute_on()
        else:
            await player.mute_off()

    @override
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        input_source = next(
            (
                input_source
                for input_source, ha_source in INPUT_SOURCE_DENON_TO_HA.items()
                if ha_source == source
            ),
            None,
        )
        if input_source is None:
            raise HomeAssistantError("Invalid source")

        await self._player.select_input_source(input_source)

    @override
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Tune to a tuner preset or an FM frequency."""
        if media_type != MediaType.CHANNEL:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_media_type",
                translation_placeholders={"media_type": str(media_type)},
            )

        player = cast(MainPlayer, self._player)
        if re.fullmatch(r"[A-G][1-8]", media_id):
            await player.set_tuner_preset(media_id)
        elif (match := re.fullmatch(r"0*([0-9]{1,5})", media_id)) and (
            TUNER_FREQUENCY_MIN <= (frequency := int(match[1])) <= TUNER_FREQUENCY_MAX
        ):
            await player.set_tuner_frequency(f"{frequency:0{TUNER_FREQUENCY_LENGTH}d}")
        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_tuner_channel",
                translation_placeholders={"media_id": media_id},
            )

    @override
    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """List the tuner presets as playable channels."""
        if media_content_id not in (None, TUNER_PRESETS_ROOT):
            raise BrowseError(f"Media not found: {media_content_id}")

        return BrowseMedia(
            title="Tuner presets",
            media_class=MediaClass.DIRECTORY,
            media_content_id=TUNER_PRESETS_ROOT,
            media_content_type=MediaType.CHANNELS,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.CHANNEL,
            children=[
                BrowseMedia(
                    title=preset,
                    media_class=MediaClass.CHANNEL,
                    media_content_id=preset,
                    media_content_type=MediaType.CHANNEL,
                    can_play=True,
                    can_expand=False,
                )
                for preset in (
                    f"{bank}{number}" for bank in "ABCDEFG" for number in range(1, 9)
                )
            ],
        )
