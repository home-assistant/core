"""Support for Onkyo Receivers."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

import voluptuous as vol

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_NAME
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.hass_dict import HassKey

from . import OnkyoConfigEntry
from .const import (
    CONF_RECEIVER_MAX_VOLUME,
    CONF_RECEIVER_MAX_VOLUME_DEFAULT,
    CONF_SOURCES_DEFAULT,
    CONF_VOLUME_RESOLUTION,
    DOMAIN,
    OPTION_MAX_VOLUME,
    OPTION_MAX_VOLUME_DEFAULT,
    OPTION_SOURCES,
    ZONES,
)
from .receiver import Receiver, async_discover

_LOGGER = logging.getLogger(__name__)

DATA_MP_ENTITIES: HassKey[list[dict[str, OnkyoMediaPlayer]]] = HassKey(DOMAIN)

SUPPORT_ONKYO_WO_VOLUME = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY_MEDIA
)
SUPPORT_ONKYO = (
    SUPPORT_ONKYO_WO_VOLUME
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_STEP
)

DEFAULT_PLAYABLE_SOURCES = ("fm", "am", "tuner")

ATTR_HDMI_OUTPUT = "hdmi_output"
ATTR_PRESET = "preset"
ATTR_AUDIO_INFORMATION = "audio_information"
ATTR_VIDEO_INFORMATION = "video_information"
ATTR_VIDEO_OUT = "video_out"

AUDIO_VIDEO_INFORMATION_UPDATE_WAIT_TIME = 8

AUDIO_INFORMATION_MAPPING = [
    "audio_input_port",
    "input_signal_format",
    "input_frequency",
    "input_channels",
    "listening_mode",
    "output_channels",
    "output_frequency",
    "precision_quartz_lock_system",
    "auto_phase_control_delay",
    "auto_phase_control_phase",
]

VIDEO_INFORMATION_MAPPING = [
    "video_input_port",
    "input_resolution",
    "input_color_schema",
    "input_color_depth",
    "video_output_port",
    "output_resolution",
    "output_color_schema",
    "output_color_depth",
    "picture_mode",
]

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

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(OPTION_MAX_VOLUME, default=OPTION_MAX_VOLUME_DEFAULT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
        vol.Optional(
            CONF_RECEIVER_MAX_VOLUME, default=CONF_RECEIVER_MAX_VOLUME_DEFAULT
        ): cv.positive_int,
        vol.Optional(OPTION_SOURCES, default=CONF_SOURCES_DEFAULT): {
            cv.string: cv.string
        },
    }
)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register Onkyo services."""

    async def async_service_handle(service: ServiceCall) -> None:
        """Handle for services."""
        entity_ids = service.data[ATTR_ENTITY_ID]

        targets: list[OnkyoMediaPlayer] = []
        for receiver_entities in hass.data[DATA_MP_ENTITIES]:
            targets.extend(
                entity
                for entity in receiver_entities.values()
                if entity.entity_id in entity_ids
            )

        for target in targets:
            if service.service == SERVICE_SELECT_HDMI_OUTPUT:
                await target.async_select_output(service.data[ATTR_HDMI_OUTPUT])

    hass.services.async_register(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_HDMI_OUTPUT,
        async_service_handle,
        schema=ONKYO_SELECT_OUTPUT_SCHEMA,
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import config from yaml."""
    host = config.get(CONF_HOST)
    results = []
    if host is not None:
        _LOGGER.debug("Importing yaml single: %s", host)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
        results.append((host, result))
    else:
        for info in await async_discover():
            host = info.host

            # Migrate legacy entities.
            registry = er.async_get(hass)
            old_unique_id = f"{info.model_name}_{info.identifier}"
            new_unique_id = f"{info.identifier}_main"
            entity_id = registry.async_get_entity_id(
                "media_player", DOMAIN, old_unique_id
            )
            if entity_id is not None:
                _LOGGER.debug(
                    "Migrating unique_id from [%s] to [%s]",
                    old_unique_id,
                    new_unique_id,
                )
                registry.async_update_entity(entity_id, new_unique_id=new_unique_id)

            _LOGGER.debug("Importing yaml discover: %s", info.host)
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config | {CONF_HOST: info.host} | {CONF_NAME: info.model_name},
            )
            results.append((host, result))

    _LOGGER.debug("Importing yaml results: %s", results)
    if results:
        if all(
            result.get("type") == FlowResultType.CREATE_ENTRY
            or result.get("reason") == "already_configured"
            for _, result in results
        ):
            async_create_issue(
                hass,
                HOMEASSISTANT_DOMAIN,
                f"deprecated_yaml_{DOMAIN}",
                is_fixable=False,
                issue_domain=DOMAIN,
                breaks_in_ha_version="2025.2.0",
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "onkyo",
                },
            )
        else:
            for host, result in results:
                if error := result.get("reason"):
                    async_create_issue(
                        hass,
                        DOMAIN,
                        f"deprecated_yaml_import_issue_{host}_{error}",
                        breaks_in_ha_version="2025.2.0",
                        is_fixable=False,
                        issue_domain=DOMAIN,
                        severity=IssueSeverity.WARNING,
                        translation_key=f"deprecated_yaml_import_issue_{error}",
                        translation_placeholders={"host": f"{host}"},
                    )
    else:
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_import_issue_no_discover",
            breaks_in_ha_version="2025.2.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue_no_discover",
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OnkyoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MediaPlayer for config entry."""
    receiver = entry.runtime_data
    all_entities = hass.data.setdefault(DATA_MP_ENTITIES, [])

    entities: dict[str, OnkyoMediaPlayer] = {}
    all_entities.append(entities)

    volume_resolution = entry.data[CONF_VOLUME_RESOLUTION]
    max_volume = entry.options[OPTION_MAX_VOLUME]
    sources = entry.options[OPTION_SOURCES]

    def connect_callback(receiver: Receiver) -> None:
        if not receiver.first_connect:
            for entity in entities.values():
                if entity.enabled:
                    entity.backfill_state()

    def update_callback(receiver: Receiver, message: tuple[str, str, Any]) -> None:
        zone, _, value = message
        entity = entities.get(zone)
        if entity is not None:
            if entity.enabled:
                entity.process_update(message)
        elif zone in ZONES and value != "N/A":
            # When we receive the status for a zone, and the value is not "N/A",
            # then zone is available on the receiver, so we create the entity for it.
            _LOGGER.debug(
                "Discovered %s on %s (%s)",
                ZONES[zone],
                receiver.model_name,
                receiver.host,
            )
            zone_entity = OnkyoMediaPlayer(
                receiver,
                zone,
                volume_resolution=volume_resolution,
                max_volume=max_volume,
                sources=sources,
            )
            entities[zone] = zone_entity
            async_add_entities([zone_entity])

    receiver.callbacks.connect.append(connect_callback)
    receiver.callbacks.update.append(update_callback)


class OnkyoMediaPlayer(MediaPlayerEntity):
    """Representation of an Onkyo Receiver Media Player (one per each zone)."""

    _attr_should_poll = False

    _supports_volume: bool = False
    _supports_audio_info: bool = False
    _supports_video_info: bool = False
    _query_timer: asyncio.TimerHandle | None = None

    def __init__(
        self,
        receiver: Receiver,
        zone: str,
        *,
        volume_resolution: int,
        max_volume: int,
        sources: dict[str, str],
    ) -> None:
        """Initialize the Onkyo Receiver."""
        self._receiver = receiver
        name = receiver.model_name
        identifier = receiver.identifier
        self._attr_name = f"{name}{' ' + ZONES[zone] if zone != 'main' else ''}"
        self._attr_unique_id = f"{identifier}_{zone}"

        self._zone = zone
        self._source_mapping = sources
        self._reverse_mapping = {value: key for key, value in sources.items()}
        self._max_volume = max_volume
        self._volume_resolution = volume_resolution

        self._attr_source_list = list(sources.values())
        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        """Entity has been added to hass."""
        self.backfill_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the query timer when the entity is removed."""
        if self._query_timer:
            self._query_timer.cancel()
            self._query_timer = None

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return media player features that are supported."""
        if self._supports_volume:
            return SUPPORT_ONKYO
        return SUPPORT_ONKYO_WO_VOLUME

    @callback
    def _update_receiver(self, propname: str, value: Any) -> None:
        """Update a property in the receiver."""
        self._receiver.conn.update_property(self._zone, propname, value)

    @callback
    def _query_receiver(self, propname: str) -> None:
        """Cause the receiver to send an update about a property."""
        self._receiver.conn.query_property(self._zone, propname)

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        self._update_receiver("power", "on")

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        self._update_receiver("power", "standby")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1.

        However full volume on the amp is usually far too loud so allow the user to
        specify the upper range with CONF_MAX_VOLUME. We change as per max_volume
        set by user. This means that if max volume is 80 then full volume in HA
        will give 80% volume on the receiver. Then we convert that to the correct
        scale for the receiver.
        """
        # HA_VOL * (MAX VOL / 100) * VOL_RESOLUTION
        self._update_receiver(
            "volume", int(volume * (self._max_volume / 100) * self._volume_resolution)
        )

    async def async_volume_up(self) -> None:
        """Increase volume by 1 step."""
        self._update_receiver("volume", "level-up")

    async def async_volume_down(self) -> None:
        """Decrease volume by 1 step."""
        self._update_receiver("volume", "level-down")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        self._update_receiver(
            "audio-muting" if self._zone == "main" else "muting",
            "on" if mute else "off",
        )

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if self.source_list and source in self.source_list:
            source = self._reverse_mapping[source]
        self._update_receiver(
            "input-selector" if self._zone == "main" else "selector", source
        )

    async def async_select_output(self, hdmi_output: str) -> None:
        """Set hdmi-out."""
        self._update_receiver("hdmi-output-selector", hdmi_output)

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play radio station by preset number."""
        if self.source is not None:
            source = self._reverse_mapping[self.source]
            if media_type.lower() == "radio" and source in DEFAULT_PLAYABLE_SOURCES:
                self._update_receiver("preset", media_id)

    @callback
    def backfill_state(self) -> None:
        """Get the receiver to send all the info we care about.

        Usually run only on connect, as we can otherwise rely on the
        receiver to keep us informed of changes.
        """
        self._query_receiver("power")
        self._query_receiver("volume")
        self._query_receiver("preset")
        if self._zone == "main":
            self._query_receiver("hdmi-output-selector")
            self._query_receiver("audio-muting")
            self._query_receiver("input-selector")
            self._query_receiver("listening-mode")
            self._query_receiver("audio-information")
            self._query_receiver("video-information")
        else:
            self._query_receiver("muting")
            self._query_receiver("selector")

    @callback
    def process_update(self, update: tuple[str, str, Any]) -> None:
        """Store relevant updates so they can be queried later."""
        zone, command, value = update
        if zone != self._zone:
            return

        if command in ["system-power", "power"]:
            if value == "on":
                self._attr_state = MediaPlayerState.ON
            else:
                self._attr_state = MediaPlayerState.OFF
                self._attr_extra_state_attributes.pop(ATTR_AUDIO_INFORMATION, None)
                self._attr_extra_state_attributes.pop(ATTR_VIDEO_INFORMATION, None)
                self._attr_extra_state_attributes.pop(ATTR_PRESET, None)
                self._attr_extra_state_attributes.pop(ATTR_VIDEO_OUT, None)
        elif command in ["volume", "master-volume"] and value != "N/A":
            self._supports_volume = True
            # AMP_VOL / (VOL_RESOLUTION * (MAX_VOL / 100))
            self._attr_volume_level = value / (
                self._volume_resolution * self._max_volume / 100
            )
        elif command in ["muting", "audio-muting"]:
            self._attr_is_volume_muted = bool(value == "on")
        elif command in ["selector", "input-selector"]:
            self._parse_source(value)
            self._query_av_info_delayed()
        elif command == "hdmi-output-selector":
            self._attr_extra_state_attributes[ATTR_VIDEO_OUT] = ",".join(value)
        elif command == "preset":
            if self.source is not None and self.source.lower() == "radio":
                self._attr_extra_state_attributes[ATTR_PRESET] = value
            elif ATTR_PRESET in self._attr_extra_state_attributes:
                del self._attr_extra_state_attributes[ATTR_PRESET]
        elif command == "audio-information":
            self._supports_audio_info = True
            self._parse_audio_information(value)
        elif command == "video-information":
            self._supports_video_info = True
            self._parse_video_information(value)
        elif command == "fl-display-information":
            self._query_av_info_delayed()

        self.async_write_ha_state()

    @callback
    def _parse_source(self, source_raw: str | int | tuple[str]) -> None:
        # source is either a tuple of values or a single value,
        # so we convert to a tuple, when it is a single value.
        if isinstance(source_raw, str | int):
            source = (str(source_raw),)
        else:
            source = source_raw
        for value in source:
            if value in self._source_mapping:
                self._attr_source = self._source_mapping[value]
                return
        self._attr_source = "_".join(source)

    @callback
    def _parse_audio_information(
        self, audio_information: tuple[str] | Literal["N/A"]
    ) -> None:
        # If audio information is not available, N/A is returned,
        # so only update the audio information, when it is not N/A.
        if audio_information == "N/A":
            self._attr_extra_state_attributes.pop(ATTR_AUDIO_INFORMATION, None)
            return

        self._attr_extra_state_attributes[ATTR_AUDIO_INFORMATION] = {
            name: value
            for name, value in zip(
                AUDIO_INFORMATION_MAPPING, audio_information, strict=False
            )
            if len(value) > 0
        }

    @callback
    def _parse_video_information(
        self, video_information: tuple[str] | Literal["N/A"]
    ) -> None:
        # If video information is not available, N/A is returned,
        # so only update the video information, when it is not N/A.
        if video_information == "N/A":
            self._attr_extra_state_attributes.pop(ATTR_VIDEO_INFORMATION, None)
            return

        self._attr_extra_state_attributes[ATTR_VIDEO_INFORMATION] = {
            name: value
            for name, value in zip(
                VIDEO_INFORMATION_MAPPING, video_information, strict=False
            )
            if len(value) > 0
        }

    def _query_av_info_delayed(self) -> None:
        if self._zone == "main" and not self._query_timer:

            @callback
            def _query_av_info() -> None:
                if self._supports_audio_info:
                    self._query_receiver("audio-information")
                if self._supports_video_info:
                    self._query_receiver("video-information")
                self._query_timer = None

            self._query_timer = self.hass.loop.call_later(
                AUDIO_VIDEO_INFORMATION_UPDATE_WAIT_TIME, _query_av_info
            )
