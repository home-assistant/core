"""Component providing support for Reolink select entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from reolink_aio.api import (
    BinningModeEnum,
    Chime,
    ChimeToneEnum,
    DayNightEnum,
    HDREnum,
    Host,
    HubToneEnum,
    SpotlightModeEnum,
    StatusLedEnum,
    TrackMethodEnum,
)
from reolink_aio.exceptions import InvalidParameterError, ReolinkError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory, UnitOfDataRate, UnitOfFrequency
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import (
    ReolinkChannelCoordinatorEntity,
    ReolinkChannelEntityDescription,
    ReolinkChimeCoordinatorEntity,
    ReolinkChimeEntityDescription,
)
from .util import ReolinkConfigEntry, ReolinkData

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ReolinkSelectEntityDescription(
    SelectEntityDescription,
    ReolinkChannelEntityDescription,
):
    """A class that describes select entities."""

    get_options: list[str] | Callable[[Host, int], list[str]]
    method: Callable[[Host, int, str], Any]
    value: Callable[[Host, int], str] | None = None


@dataclass(frozen=True, kw_only=True)
class ReolinkChimeSelectEntityDescription(
    SelectEntityDescription,
    ReolinkChimeEntityDescription,
):
    """A class that describes select entities for a chime."""

    get_options: list[str]
    method: Callable[[Chime, str], Any]
    value: Callable[[Chime], str]


def _get_quick_reply_id(api: Host, ch: int, mess: str) -> int:
    """Get the quick reply file id from the message string."""
    return [k for k, v in api.quick_reply_dict(ch).items() if v == mess][0]


SELECT_ENTITIES = (
    ReolinkSelectEntityDescription(
        key="floodlight_mode",
        cmd_key="GetWhiteLed",
        translation_key="floodlight_mode",
        entity_category=EntityCategory.CONFIG,
        get_options=lambda api, ch: api.whiteled_mode_list(ch),
        supported=lambda api, ch: api.supported(ch, "floodLight"),
        value=lambda api, ch: SpotlightModeEnum(api.whiteled_mode(ch)).name,
        method=lambda api, ch, name: api.set_whiteled(ch, mode=name),
    ),
    ReolinkSelectEntityDescription(
        key="day_night_mode",
        cmd_key="GetIsp",
        translation_key="day_night_mode",
        entity_category=EntityCategory.CONFIG,
        get_options=[mode.name for mode in DayNightEnum],
        supported=lambda api, ch: api.supported(ch, "dayNight"),
        value=lambda api, ch: DayNightEnum(api.daynight_state(ch)).name,
        method=lambda api, ch, name: api.set_daynight(ch, DayNightEnum[name].value),
    ),
    ReolinkSelectEntityDescription(
        key="ptz_preset",
        translation_key="ptz_preset",
        get_options=lambda api, ch: list(api.ptz_presets(ch)),
        supported=lambda api, ch: api.supported(ch, "ptz_presets"),
        method=lambda api, ch, name: api.set_ptz_command(ch, preset=name),
    ),
    ReolinkSelectEntityDescription(
        key="play_quick_reply_message",
        translation_key="play_quick_reply_message",
        get_options=lambda api, ch: list(api.quick_reply_dict(ch).values())[1:],
        supported=lambda api, ch: api.supported(ch, "play_quick_reply"),
        method=lambda api, ch, mess: (
            api.play_quick_reply(ch, file_id=_get_quick_reply_id(api, ch, mess))
        ),
    ),
    ReolinkSelectEntityDescription(
        key="auto_quick_reply_message",
        cmd_key="GetAutoReply",
        translation_key="auto_quick_reply_message",
        entity_category=EntityCategory.CONFIG,
        get_options=lambda api, ch: list(api.quick_reply_dict(ch).values()),
        supported=lambda api, ch: api.supported(ch, "quick_reply"),
        value=lambda api, ch: api.quick_reply_dict(ch)[api.quick_reply_file(ch)],
        method=lambda api, ch, mess: (
            api.set_quick_reply(ch, file_id=_get_quick_reply_id(api, ch, mess))
        ),
    ),
    ReolinkSelectEntityDescription(
        key="hub_alarm_ringtone",
        cmd_key="GetDeviceAudioCfg",
        translation_key="hub_alarm_ringtone",
        entity_category=EntityCategory.CONFIG,
        get_options=[mode.name for mode in HubToneEnum],
        supported=lambda api, ch: api.supported(ch, "hub_audio"),
        value=lambda api, ch: HubToneEnum(api.hub_alarm_tone_id(ch)).name,
        method=lambda api, ch, name: (
            api.set_hub_audio(ch, alarm_tone_id=HubToneEnum[name].value)
        ),
    ),
    ReolinkSelectEntityDescription(
        key="hub_visitor_ringtone",
        cmd_key="GetDeviceAudioCfg",
        translation_key="hub_visitor_ringtone",
        entity_category=EntityCategory.CONFIG,
        get_options=[mode.name for mode in HubToneEnum],
        supported=lambda api, ch: (
            api.supported(ch, "hub_audio") and api.is_doorbell(ch)
        ),
        value=lambda api, ch: HubToneEnum(api.hub_visitor_tone_id(ch)).name,
        method=lambda api, ch, name: (
            api.set_hub_audio(ch, visitor_tone_id=HubToneEnum[name].value)
        ),
    ),
    ReolinkSelectEntityDescription(
        key="auto_track_method",
        cmd_key="GetAiCfg",
        translation_key="auto_track_method",
        entity_category=EntityCategory.CONFIG,
        get_options=[method.name for method in TrackMethodEnum],
        supported=lambda api, ch: api.supported(ch, "auto_track_method"),
        value=lambda api, ch: TrackMethodEnum(api.auto_track_method(ch)).name,
        method=lambda api, ch, name: api.set_auto_tracking(ch, method=name),
    ),
    ReolinkSelectEntityDescription(
        key="status_led",
        cmd_key="GetPowerLed",
        translation_key="doorbell_led",
        entity_category=EntityCategory.CONFIG,
        get_options=lambda api, ch: api.doorbell_led_list(ch),
        supported=lambda api, ch: api.supported(ch, "doorbell_led"),
        value=lambda api, ch: StatusLedEnum(api.doorbell_led(ch)).name,
        method=lambda api, ch, name: (
            api.set_status_led(ch, StatusLedEnum[name].value, doorbell=True)
        ),
    ),
    ReolinkSelectEntityDescription(
        key="hdr",
        cmd_key="GetIsp",
        translation_key="hdr",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        get_options=[method.name for method in HDREnum],
        supported=lambda api, ch: api.supported(ch, "HDR"),
        value=lambda api, ch: HDREnum(api.HDR_state(ch)).name,
        method=lambda api, ch, name: api.set_HDR(ch, HDREnum[name].value),
    ),
    ReolinkSelectEntityDescription(
        key="binning_mode",
        cmd_key="GetIsp",
        translation_key="binning_mode",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        get_options=[method.name for method in BinningModeEnum],
        supported=lambda api, ch: api.supported(ch, "binning_mode"),
        value=lambda api, ch: BinningModeEnum(api.binning_mode(ch)).name,
        method=lambda api, ch, name: api.set_binning_mode(
            ch, BinningModeEnum[name].value
        ),
    ),
    ReolinkSelectEntityDescription(
        key="main_frame_rate",
        cmd_key="GetEnc",
        translation_key="main_frame_rate",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        unit_of_measurement=UnitOfFrequency.HERTZ,
        get_options=lambda api, ch: [str(v) for v in api.frame_rate_list(ch, "main")],
        supported=lambda api, ch: api.supported(ch, "frame_rate"),
        value=lambda api, ch: str(api.frame_rate(ch, "main")),
        method=lambda api, ch, value: api.set_frame_rate(ch, int(value), "main"),
    ),
    ReolinkSelectEntityDescription(
        key="sub_frame_rate",
        cmd_key="GetEnc",
        translation_key="sub_frame_rate",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        unit_of_measurement=UnitOfFrequency.HERTZ,
        get_options=lambda api, ch: [str(v) for v in api.frame_rate_list(ch, "sub")],
        supported=lambda api, ch: api.supported(ch, "frame_rate"),
        value=lambda api, ch: str(api.frame_rate(ch, "sub")),
        method=lambda api, ch, value: api.set_frame_rate(ch, int(value), "sub"),
    ),
    ReolinkSelectEntityDescription(
        key="main_bit_rate",
        cmd_key="GetEnc",
        translation_key="main_bit_rate",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        get_options=lambda api, ch: [str(v) for v in api.bit_rate_list(ch, "main")],
        supported=lambda api, ch: api.supported(ch, "bit_rate"),
        value=lambda api, ch: str(api.bit_rate(ch, "main")),
        method=lambda api, ch, value: api.set_bit_rate(ch, int(value), "main"),
    ),
    ReolinkSelectEntityDescription(
        key="sub_bit_rate",
        cmd_key="GetEnc",
        translation_key="sub_bit_rate",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        get_options=lambda api, ch: [str(v) for v in api.bit_rate_list(ch, "sub")],
        supported=lambda api, ch: api.supported(ch, "bit_rate"),
        value=lambda api, ch: str(api.bit_rate(ch, "sub")),
        method=lambda api, ch, value: api.set_bit_rate(ch, int(value), "sub"),
    ),
)

CHIME_SELECT_ENTITIES = (
    ReolinkChimeSelectEntityDescription(
        key="motion_tone",
        cmd_key="GetDingDongCfg",
        translation_key="motion_tone",
        entity_category=EntityCategory.CONFIG,
        supported=lambda chime: "md" in chime.chime_event_types,
        get_options=[method.name for method in ChimeToneEnum],
        value=lambda chime: ChimeToneEnum(chime.tone("md")).name,
        method=lambda chime, name: chime.set_tone("md", ChimeToneEnum[name].value),
    ),
    ReolinkChimeSelectEntityDescription(
        key="people_tone",
        cmd_key="GetDingDongCfg",
        translation_key="people_tone",
        entity_category=EntityCategory.CONFIG,
        get_options=[method.name for method in ChimeToneEnum],
        supported=lambda chime: "people" in chime.chime_event_types,
        value=lambda chime: ChimeToneEnum(chime.tone("people")).name,
        method=lambda chime, name: chime.set_tone("people", ChimeToneEnum[name].value),
    ),
    ReolinkChimeSelectEntityDescription(
        key="vehicle_tone",
        cmd_key="GetDingDongCfg",
        translation_key="vehicle_tone",
        entity_category=EntityCategory.CONFIG,
        get_options=[method.name for method in ChimeToneEnum],
        supported=lambda chime: "vehicle" in chime.chime_event_types,
        value=lambda chime: ChimeToneEnum(chime.tone("vehicle")).name,
        method=lambda chime, name: chime.set_tone("vehicle", ChimeToneEnum[name].value),
    ),
    ReolinkChimeSelectEntityDescription(
        key="visitor_tone",
        cmd_key="GetDingDongCfg",
        translation_key="visitor_tone",
        entity_category=EntityCategory.CONFIG,
        get_options=[method.name for method in ChimeToneEnum],
        supported=lambda chime: "visitor" in chime.chime_event_types,
        value=lambda chime: ChimeToneEnum(chime.tone("visitor")).name,
        method=lambda chime, name: chime.set_tone("visitor", ChimeToneEnum[name].value),
    ),
    ReolinkChimeSelectEntityDescription(
        key="package_tone",
        cmd_key="GetDingDongCfg",
        translation_key="package_tone",
        entity_category=EntityCategory.CONFIG,
        get_options=[method.name for method in ChimeToneEnum],
        supported=lambda chime: "package" in chime.chime_event_types,
        value=lambda chime: ChimeToneEnum(chime.tone("package")).name,
        method=lambda chime, name: chime.set_tone("package", ChimeToneEnum[name].value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ReolinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink select entities."""
    reolink_data: ReolinkData = config_entry.runtime_data

    entities: list[ReolinkSelectEntity | ReolinkChimeSelectEntity] = [
        ReolinkSelectEntity(reolink_data, channel, entity_description)
        for entity_description in SELECT_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    ]
    entities.extend(
        ReolinkChimeSelectEntity(reolink_data, chime, entity_description)
        for entity_description in CHIME_SELECT_ENTITIES
        for chime in reolink_data.host.api.chime_list
        if entity_description.supported(chime)
    )
    async_add_entities(entities)


class ReolinkSelectEntity(ReolinkChannelCoordinatorEntity, SelectEntity):
    """Base select entity class for Reolink IP cameras."""

    entity_description: ReolinkSelectEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkSelectEntityDescription,
    ) -> None:
        """Initialize Reolink select entity."""
        self.entity_description = entity_description
        super().__init__(reolink_data, channel)
        self._log_error = True

        if callable(entity_description.get_options):
            self._attr_options = entity_description.get_options(self._host.api, channel)
        else:
            self._attr_options = entity_description.get_options

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        if self.entity_description.value is None:
            return None

        try:
            option = self.entity_description.value(self._host.api, self._channel)
        except (ValueError, KeyError):
            if self._log_error:
                _LOGGER.exception("Reolink '%s' has an unknown value", self.name)
                self._log_error = False
            return None

        self._log_error = True
        return option

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            await self.entity_description.method(self._host.api, self._channel, option)
        except InvalidParameterError as err:
            raise ServiceValidationError(err) from err
        except ReolinkError as err:
            raise HomeAssistantError(err) from err
        self.async_write_ha_state()


class ReolinkChimeSelectEntity(ReolinkChimeCoordinatorEntity, SelectEntity):
    """Base select entity class for Reolink IP cameras."""

    entity_description: ReolinkChimeSelectEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        chime: Chime,
        entity_description: ReolinkChimeSelectEntityDescription,
    ) -> None:
        """Initialize Reolink select entity for a chime."""
        self.entity_description = entity_description
        super().__init__(reolink_data, chime)
        self._log_error = True
        self._attr_options = entity_description.get_options

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        try:
            option = self.entity_description.value(self._chime)
        except (ValueError, KeyError):
            if self._log_error:
                _LOGGER.exception("Reolink '%s' has an unknown value", self.name)
                self._log_error = False
            return None

        self._log_error = True
        return option

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            await self.entity_description.method(self._chime, option)
        except InvalidParameterError as err:
            raise ServiceValidationError(err) from err
        except ReolinkError as err:
            raise HomeAssistantError(err) from err
        self.async_write_ha_state()
