"""Media player platform for the Marantz RS-232 integration."""

import math
from typing import cast

from marantz_rs232 import (
    V2015_MIN_VOLUME_DB,
    V2015_VOLUME_DB_RANGE,
    MarantzV2003Receiver,
    MarantzV2007Receiver,
    MarantzV2015Receiver,
    V2003MainPlayer,
    V2003MultiRoomPlayer,
    V2003ReceiverState,
    V2003Source,
    V2007MainPlayer,
    V2007MultiRoomPlayer,
    V2007ReceiverState,
    V2007Source,
    V2015InputSource,
    V2015MainPlayer,
    V2015ReceiverState,
    V2015ZonePlayer,
)

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_flow import MODEL_NAMES
from .const import DOMAIN, MarantzRS232ConfigEntry

V2003_MIN_VOLUME_DB = -90.0
V2003_VOLUME_DB_RANGE = 189.0  # -90..+99

INPUT_SOURCE_V2015_TO_HA: dict[V2015InputSource, str] = {
    V2015InputSource.PHONO: "phono",
    V2015InputSource.CD: "cd",
    V2015InputSource.TUNER: "tuner",
    V2015InputSource.DVD: "dvd",
    V2015InputSource.BD: "bd",
    V2015InputSource.TV: "tv",
    V2015InputSource.SAT_CBL: "sat_cbl",
    V2015InputSource.SAT: "sat",
    V2015InputSource.MPLAY: "mplay",
    V2015InputSource.VCR: "vcr",
    V2015InputSource.GAME: "game",
    V2015InputSource.V_AUX: "v_aux",
    V2015InputSource.HDRADIO: "hdradio",
    V2015InputSource.SIRIUS: "sirius",
    V2015InputSource.SPOTIFY: "spotify",
    V2015InputSource.SIRIUSXM: "siriusxm",
    V2015InputSource.RHAPSODY: "rhapsody",
    V2015InputSource.PANDORA: "pandora",
    V2015InputSource.NAPSTER: "napster",
    V2015InputSource.LASTFM: "lastfm",
    V2015InputSource.FLICKR: "flickr",
    V2015InputSource.IRADIO: "iradio",
    V2015InputSource.SERVER: "server",
    V2015InputSource.FAVORITES: "favorites",
    V2015InputSource.CDR: "cdr",
    V2015InputSource.AUX1: "aux1",
    V2015InputSource.AUX2: "aux2",
    V2015InputSource.AUX3: "aux3",
    V2015InputSource.AUX4: "aux4",
    V2015InputSource.AUX5: "aux5",
    V2015InputSource.AUX6: "aux6",
    V2015InputSource.AUX7: "aux7",
    V2015InputSource.NET: "net",
    V2015InputSource.NET_USB: "net_usb",
    V2015InputSource.BT: "bt",
    V2015InputSource.M_XPORT: "m_xport",
    V2015InputSource.USB_IPOD: "usb_ipod",
}

INPUT_SOURCE_V2007_TO_HA: dict[V2007Source, str] = {
    V2007Source.TV: "tv",
    V2007Source.DVD: "dvd",
    V2007Source.VCR1: "vcr1",
    V2007Source.DSS_VCR2: "dss_vcr2",
    V2007Source.AUX1: "aux1",
    V2007Source.AUX2: "aux2",
    V2007Source.CD_CDR: "cd_cdr",
    V2007Source.TAPE: "tape",
    V2007Source.TUNER1: "tuner",
    V2007Source.FM1: "fm",
    V2007Source.AM1: "am",
    V2007Source.XM1: "xm",
}

INPUT_SOURCE_V2003_TO_HA: dict[V2003Source, str] = {
    V2003Source.DSS: "dss",
    V2003Source.TV: "tv",
    V2003Source.LD: "ld",
    V2003Source.DVD: "dvd",
    V2003Source.VCR1: "vcr1",
    V2003Source.VCR2_DVDR: "vcr2_dvdr",
    V2003Source.AUX1: "aux1",
    V2003Source.AUX2: "aux2",
    V2003Source.DVDR: "dvdr",
    V2003Source.CD: "cd",
    V2003Source.TAPE: "tape",
    V2003Source.CDR: "cdr",
    V2003Source.FM: "fm",
    V2003Source.AM: "am",
    V2003Source.MW: "mw",
    V2003Source.LW: "lw",
    V2003Source.TUNER: "tuner",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MarantzRS232ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Marantz RS-232 media player."""
    receiver = config_entry.runtime_data

    entities: list[MediaPlayerEntity]
    if isinstance(receiver, MarantzV2015Receiver):
        entities = [
            MarantzV2015MediaPlayer(receiver, receiver.main, config_entry, "main")
        ]
        if receiver.zone_2.power is not None:
            entities.append(
                MarantzV2015MediaPlayer(
                    receiver, receiver.zone_2, config_entry, "zone_2"
                )
            )
        if receiver.zone_3.power is not None:
            entities.append(
                MarantzV2015MediaPlayer(
                    receiver, receiver.zone_3, config_entry, "zone_3"
                )
            )
    elif isinstance(receiver, MarantzV2003Receiver):
        entities = [
            MarantzV2003MediaPlayer(receiver, receiver.main, config_entry, "main")
        ]
        if receiver.multi_room.power is not None:
            entities.append(
                MarantzV2003MediaPlayer(
                    receiver, receiver.multi_room, config_entry, "multi_room"
                )
            )
    else:
        entities = [
            MarantzV2007MediaPlayer(receiver, receiver.main, config_entry, "main")
        ]
        if receiver.multi_room_a.power is not None:
            entities.append(
                MarantzV2007MediaPlayer(
                    receiver, receiver.multi_room_a, config_entry, "multi_room_a"
                )
            )

    async_add_entities(entities)


class MarantzV2015MediaPlayer(MediaPlayerEntity):
    """Representation of a modern Marantz receiver controlled over RS-232."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_has_entity_name = True
    _attr_translation_key = "receiver"
    _attr_should_poll = False

    _volume_min = V2015_MIN_VOLUME_DB
    _volume_range = V2015_VOLUME_DB_RANGE

    def __init__(
        self,
        receiver: MarantzV2015Receiver,
        player: V2015MainPlayer | V2015ZonePlayer,
        config_entry: MarantzRS232ConfigEntry,
        zone: str,
    ) -> None:
        """Initialize the media player."""
        self._receiver = receiver
        self._player = player
        self._is_main = zone == "main"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Marantz",
            model_id=MODEL_NAMES.get(config_entry.data["model"]),
        )
        self._attr_unique_id = f"{config_entry.entry_id}_{zone}"

        self._attr_source_list = sorted(INPUT_SOURCE_V2015_TO_HA.values())
        self._attr_supported_features = (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.SELECT_SOURCE
        )

        if zone == "main":
            self._attr_name = None
            self._attr_supported_features |= MediaPlayerEntityFeature.VOLUME_MUTE
        elif zone == "zone_2":
            self._attr_name = "Zone 2"
        else:
            self._attr_name = "Zone 3"

        self._async_update_from_player()

    async def async_added_to_hass(self) -> None:
        """Subscribe to receiver state updates."""
        self.async_on_remove(self._receiver.subscribe(self._async_on_state_update))

    @callback
    def _async_on_state_update(self, state: V2015ReceiverState | None) -> None:
        if state is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._async_update_from_player()
        self.async_write_ha_state()

    @callback
    def _async_update_from_player(self) -> None:
        if self._player.power is None:
            self._attr_state = None
        else:
            self._attr_state = (
                MediaPlayerState.ON if self._player.power else MediaPlayerState.OFF
            )

        source = self._player.input_source
        self._attr_source = INPUT_SOURCE_V2015_TO_HA.get(source) if source else None

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
            self._attr_is_volume_muted = cast(V2015MainPlayer, self._player).mute

    async def async_turn_on(self) -> None:
        """Turn the receiver on."""
        await self._player.power_on()

    async def async_turn_off(self) -> None:
        """Turn the receiver off."""
        await self._player.power_off()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        db = volume * self._volume_range + self._volume_min
        await self._player.set_volume(db)

    async def async_volume_up(self) -> None:
        """Volume up."""
        await self._player.volume_up()

    async def async_volume_down(self) -> None:
        """Volume down."""
        await self._player.volume_down()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        player = cast(V2015MainPlayer, self._player)
        if mute:
            await player.mute_on()
        else:
            await player.mute_off()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        input_source = next(
            (
                input_source
                for input_source, ha_source in INPUT_SOURCE_V2015_TO_HA.items()
                if ha_source == source
            ),
            None,
        )
        if input_source is None:
            raise HomeAssistantError("Invalid source")

        await self._player.select_source(input_source)


class MarantzV2007MediaPlayer(MediaPlayerEntity):
    """Representation of a 2007-era Marantz receiver controlled over RS-232."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_has_entity_name = True
    _attr_translation_key = "receiver"
    _attr_should_poll = False

    _volume_min = V2015_MIN_VOLUME_DB
    _volume_range = V2015_VOLUME_DB_RANGE

    def __init__(
        self,
        receiver: MarantzV2007Receiver,
        player: V2007MainPlayer | V2007MultiRoomPlayer,
        config_entry: MarantzRS232ConfigEntry,
        zone: str,
    ) -> None:
        """Initialize the v2007 media player."""
        self._receiver = receiver
        self._player = player

        if isinstance(player, V2007MainPlayer):
            self._set_volume = player.set_volume
            self._volume_up = player.volume_up
            self._volume_down = player.volume_down
        else:
            self._set_volume = player.set_line_volume
            self._volume_up = player.line_volume_up
            self._volume_down = player.line_volume_down

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Marantz",
            model_id=MODEL_NAMES.get(config_entry.data["model"]),
        )
        self._attr_unique_id = f"{config_entry.entry_id}_{zone}"

        self._attr_source_list = sorted(INPUT_SOURCE_V2007_TO_HA.values())
        self._attr_supported_features = (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.SELECT_SOURCE
        )

        if zone == "main":
            self._attr_name = None
        else:
            self._attr_name = "Multi Room"

        self._async_update_from_player()

    async def async_added_to_hass(self) -> None:
        """Subscribe to receiver state updates."""
        self.async_on_remove(self._receiver.subscribe(self._async_on_state_update))

    @callback
    def _async_on_state_update(self, state: V2007ReceiverState | None) -> None:
        if state is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._async_update_from_player()
        self.async_write_ha_state()

    @callback
    def _async_update_from_player(self) -> None:
        if self._player.power is None:
            self._attr_state = None
        else:
            self._attr_state = (
                MediaPlayerState.ON if self._player.power else MediaPlayerState.OFF
            )

        source = self._player.input_source
        self._attr_source = INPUT_SOURCE_V2007_TO_HA.get(source) if source else None

        if isinstance(self._player, V2007MainPlayer):
            volume = self._player.volume
        else:
            volume = self._player.line_volume

        if volume is not None:
            self._attr_volume_level = (volume - self._volume_min) / self._volume_range
        else:
            self._attr_volume_level = None

        self._attr_is_volume_muted = self._player.mute

    async def async_turn_on(self) -> None:
        """Turn the receiver on."""
        await self._player.power_on()

    async def async_turn_off(self) -> None:
        """Turn the receiver off."""
        await self._player.power_off()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        db = volume * self._volume_range + self._volume_min
        await self._set_volume(db)

    async def async_volume_up(self) -> None:
        """Volume up."""
        await self._volume_up()

    async def async_volume_down(self) -> None:
        """Volume down."""
        await self._volume_down()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        if mute:
            await self._player.mute_on()
        else:
            await self._player.mute_off()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        v2007_source = next(
            (
                ls
                for ls, ha_source in INPUT_SOURCE_V2007_TO_HA.items()
                if ha_source == source
            ),
            None,
        )
        if v2007_source is None:
            raise HomeAssistantError("Invalid source")

        await self._player.select_source(v2007_source)


class MarantzV2003MediaPlayer(MediaPlayerEntity):
    """Representation of a 2003-era Marantz receiver controlled over RS-232."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_has_entity_name = True
    _attr_translation_key = "receiver"
    _attr_should_poll = False

    _volume_min = V2003_MIN_VOLUME_DB
    _volume_range = V2003_VOLUME_DB_RANGE

    def __init__(
        self,
        receiver: MarantzV2003Receiver,
        player: V2003MainPlayer | V2003MultiRoomPlayer,
        config_entry: MarantzRS232ConfigEntry,
        zone: str,
    ) -> None:
        """Initialize the v2003 media player."""
        self._receiver = receiver
        self._player = player

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Marantz",
            model_id=MODEL_NAMES.get(config_entry.data["model"]),
        )
        self._attr_unique_id = f"{config_entry.entry_id}_{zone}"

        self._attr_source_list = sorted(INPUT_SOURCE_V2003_TO_HA.values())
        if zone == "main":
            self._attr_name = None
            self._attr_supported_features = (
                MediaPlayerEntityFeature.TURN_ON
                | MediaPlayerEntityFeature.TURN_OFF
                | MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
                | MediaPlayerEntityFeature.VOLUME_MUTE
                | MediaPlayerEntityFeature.SELECT_SOURCE
            )
        else:
            self._attr_name = "Multi Room"
            self._attr_supported_features = (
                MediaPlayerEntityFeature.TURN_ON
                | MediaPlayerEntityFeature.TURN_OFF
                | MediaPlayerEntityFeature.VOLUME_STEP
                | MediaPlayerEntityFeature.SELECT_SOURCE
            )

        self._async_update_from_player()

    async def async_added_to_hass(self) -> None:
        """Subscribe to receiver state updates."""
        self.async_on_remove(self._receiver.subscribe(self._async_on_state_update))

    @callback
    def _async_on_state_update(self, state: V2003ReceiverState | None) -> None:
        if state is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._async_update_from_player()
        self.async_write_ha_state()

    @callback
    def _async_update_from_player(self) -> None:
        power = self._player.power
        if power is None:
            self._attr_state = None
        else:
            self._attr_state = MediaPlayerState.ON if power else MediaPlayerState.OFF

        source = self._player.input_source
        self._attr_source = (
            INPUT_SOURCE_V2003_TO_HA.get(source) if source is not None else None
        )

        volume = self._player.volume
        if volume is not None and volume != -math.inf:
            self._attr_volume_level = (volume - self._volume_min) / self._volume_range
        else:
            self._attr_volume_level = None

        if isinstance(self._player, V2003MainPlayer):
            self._attr_is_volume_muted = self._player.mute

    async def async_turn_on(self) -> None:
        """Turn the receiver on."""
        await self._player.power_on()

    async def async_turn_off(self) -> None:
        """Turn the receiver off."""
        await self._player.power_off()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1. Main zone only."""
        db = round(volume * self._volume_range + self._volume_min)
        await cast(V2003MainPlayer, self._player).set_volume(db)

    async def async_volume_up(self) -> None:
        """Volume up."""
        await self._player.volume_up()

    async def async_volume_down(self) -> None:
        """Volume down."""
        await self._player.volume_down()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute. Main zone only."""
        player = cast(V2003MainPlayer, self._player)
        if mute:
            await player.mute_on()
        else:
            await player.mute_off()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        v2003_source = next(
            (
                vs
                for vs, ha_source in INPUT_SOURCE_V2003_TO_HA.items()
                if ha_source == source
            ),
            None,
        )
        if v2003_source is None:
            raise HomeAssistantError("Invalid source")

        await self._player.select_source(v2003_source)
