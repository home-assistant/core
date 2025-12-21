"""Component providing support for Reolink switch entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reolink_aio.api import Chime, Host

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import (
    ReolinkChannelCoordinatorEntity,
    ReolinkChannelEntityDescription,
    ReolinkChimeCoordinatorEntity,
    ReolinkChimeEntityDescription,
    ReolinkHostChimeCoordinatorEntity,
    ReolinkHostCoordinatorEntity,
    ReolinkHostEntityDescription,
)
from .util import ReolinkConfigEntry, ReolinkData, raise_translated_error

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ReolinkSwitchEntityDescription(
    SwitchEntityDescription,
    ReolinkChannelEntityDescription,
):
    """A class that describes switch entities."""

    method: Callable[[Host, int, bool], Any]
    value: Callable[[Host, int], bool | None]


@dataclass(frozen=True, kw_only=True)
class ReolinkHostSwitchEntityDescription(
    SwitchEntityDescription,
    ReolinkHostEntityDescription,
):
    """A class that describes host switch entities."""

    method: Callable[[Host, bool], Any]
    value: Callable[[Host], bool]


@dataclass(frozen=True, kw_only=True)
class ReolinkChimeSwitchEntityDescription(
    SwitchEntityDescription,
    ReolinkChimeEntityDescription,
):
    """A class that describes switch entities for a chime."""

    method: Callable[[Chime, bool], Any]
    value: Callable[[Chime], bool | None]


@dataclass(frozen=True, kw_only=True)
class ReolinkSwitchIndexEntityDescription(
    SwitchEntityDescription,
    ReolinkChannelEntityDescription,
):
    """A class that describes switch entities with an extra index."""

    method: Callable[[Host, int, int, bool], Any]
    value: Callable[[Host, int, int], bool | None]
    placeholder: Callable[[Host, int, int], str]


SWITCH_ENTITIES = (
    ReolinkSwitchEntityDescription(
        key="ir_lights",
        cmd_key="GetIrLights",
        translation_key="ir_lights",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "ir_lights"),
        value=lambda api, ch: api.ir_enabled(ch),
        method=lambda api, ch, value: api.set_ir_lights(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="record_audio",
        cmd_key="GetEnc",
        translation_key="record_audio",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "audio"),
        value=lambda api, ch: api.audio_record(ch),
        method=lambda api, ch, value: api.set_audio(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="siren_on_event",
        cmd_key="GetAudioAlarm",
        translation_key="siren_on_event",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "siren"),
        value=lambda api, ch: api.audio_alarm_enabled(ch),
        method=lambda api, ch, value: api.set_audio_alarm(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="auto_tracking",
        cmd_key="GetAiCfg",
        translation_key="auto_tracking",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "auto_track"),
        value=lambda api, ch: api.auto_track_enabled(ch),
        method=lambda api, ch, value: api.set_auto_tracking(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="auto_focus",
        cmd_key="GetAutoFocus",
        translation_key="auto_focus",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "auto_focus"),
        value=lambda api, ch: api.autofocus_enabled(ch),
        method=lambda api, ch, value: api.set_autofocus(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="gaurd_return",
        cmd_key="GetPtzGuard",
        translation_key="guard_return",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "ptz_guard"),
        value=lambda api, ch: api.ptz_guard_enabled(ch),
        method=lambda api, ch, value: api.set_ptz_guard(ch, enable=value),
    ),
    ReolinkSwitchEntityDescription(
        key="ptz_patrol",
        translation_key="ptz_patrol",
        supported=lambda api, ch: api.supported(ch, "ptz_patrol"),
        value=lambda api, ch: None,
        method=lambda api, ch, value: api.ctrl_ptz_patrol(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="email",
        cmd_key="GetEmail",
        translation_key="email",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "email") and api.is_nvr,
        value=lambda api, ch: api.email_enabled(ch),
        method=lambda api, ch, value: api.set_email(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="ftp_upload",
        cmd_key="GetFtp",
        translation_key="ftp_upload",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "ftp") and api.is_nvr,
        value=lambda api, ch: api.ftp_enabled(ch),
        method=lambda api, ch, value: api.set_ftp(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="push_notifications",
        cmd_key="GetPush",
        translation_key="push_notifications",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "push") and api.is_nvr,
        value=lambda api, ch: api.push_enabled(ch),
        method=lambda api, ch, value: api.set_push(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="record",
        cmd_key="GetRec",
        translation_key="record",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "rec_enable") and api.is_nvr,
        value=lambda api, ch: api.recording_enabled(ch),
        method=lambda api, ch, value: api.set_recording(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="manual_record",
        cmd_key="GetManualRec",
        cmd_id=588,
        translation_key="manual_record",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "manual_record"),
        value=lambda api, ch: api.manual_record_enabled(ch),
        method=lambda api, ch, value: api.set_manual_record(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="pre_record",
        cmd_key="594",
        translation_key="pre_record",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "pre_record"),
        value=lambda api, ch: api.baichuan.pre_record_enabled(ch),
        method=lambda api, ch, value: api.baichuan.set_pre_recording(ch, enabled=value),
    ),
    ReolinkSwitchEntityDescription(
        key="buzzer",
        cmd_key="GetBuzzerAlarmV20",
        translation_key="hub_ringtone_on_event",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "buzzer") and api.is_nvr,
        value=lambda api, ch: api.buzzer_enabled(ch),
        method=lambda api, ch, value: api.set_buzzer(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="doorbell_button_sound",
        cmd_key="GetAudioCfg",
        translation_key="doorbell_button_sound",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "doorbell_button_sound"),
        value=lambda api, ch: api.doorbell_button_sound(ch),
        method=lambda api, ch, value: api.set_volume(ch, doorbell_button_sound=value),
    ),
    ReolinkSwitchEntityDescription(
        key="pir_enabled",
        cmd_key="GetPirInfo",
        translation_key="pir_enabled",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        supported=lambda api, ch: api.supported(ch, "PIR"),
        value=lambda api, ch: api.pir_enabled(ch) is True,
        method=lambda api, ch, value: api.set_pir(ch, enable=value),
    ),
    ReolinkSwitchEntityDescription(
        key="pir_reduce_alarm",
        cmd_key="GetPirInfo",
        translation_key="pir_reduce_alarm",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        supported=lambda api, ch: api.supported(ch, "PIR"),
        value=lambda api, ch: api.pir_reduce_alarm(ch) is True,
        method=lambda api, ch, value: api.set_pir(ch, reduce_alarm=value),
    ),
    ReolinkSwitchEntityDescription(
        key="privacy_mode",
        always_available=True,
        translation_key="privacy_mode",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "privacy_mode"),
        value=lambda api, ch: api.baichuan.privacy_mode(ch),
        method=lambda api, ch, value: api.baichuan.set_privacy_mode(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="privacy_mask",
        cmd_key="GetMask",
        translation_key="privacy_mask",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "privacy_mask"),
        value=lambda api, ch: api.privacy_mask_enabled(ch),
        method=lambda api, ch, value: api.set_privacy_mask(ch, enable=value),
    ),
    ReolinkSwitchEntityDescription(
        key="hardwired_chime_enabled",
        cmd_key="483",
        translation_key="hardwired_chime_enabled",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        supported=lambda api, ch: api.supported(ch, "hardwired_chime"),
        value=lambda api, ch: api.baichuan.hardwired_chime_enabled(ch),
        method=lambda api, ch, value: api.baichuan.set_ding_dong_ctrl(ch, enable=value),
    ),
)

HOST_SWITCH_ENTITIES = (
    ReolinkHostSwitchEntityDescription(
        key="email",
        cmd_key="GetEmail",
        translation_key="email",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api: api.supported(None, "email") and not api.is_hub,
        value=lambda api: api.email_enabled(),
        method=lambda api, value: api.set_email(None, value),
    ),
    ReolinkHostSwitchEntityDescription(
        key="ftp_upload",
        cmd_key="GetFtp",
        translation_key="ftp_upload",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api: api.supported(None, "ftp") and not api.is_hub,
        value=lambda api: api.ftp_enabled(),
        method=lambda api, value: api.set_ftp(None, value),
    ),
    ReolinkHostSwitchEntityDescription(
        key="push_notifications",
        cmd_key="GetPush",
        translation_key="push_notifications",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api: api.supported(None, "push") and not api.is_hub,
        value=lambda api: api.push_enabled(),
        method=lambda api, value: api.set_push(None, value),
    ),
    ReolinkHostSwitchEntityDescription(
        key="record",
        cmd_key="GetRec",
        translation_key="record",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api: api.supported(None, "rec_enable") and not api.is_hub,
        value=lambda api: api.recording_enabled(),
        method=lambda api, value: api.set_recording(None, value),
    ),
    ReolinkHostSwitchEntityDescription(
        key="buzzer",
        cmd_key="GetBuzzerAlarmV20",
        translation_key="hub_ringtone_on_event",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api: api.supported(None, "buzzer") and not api.is_hub,
        value=lambda api: api.buzzer_enabled(),
        method=lambda api, value: api.set_buzzer(None, value),
    ),
)

CHIME_SWITCH_ENTITIES = (
    ReolinkChimeSwitchEntityDescription(
        key="chime_led",
        cmd_key="DingDongOpt",
        translation_key="led",
        entity_category=EntityCategory.CONFIG,
        value=lambda chime: chime.led_state,
        method=lambda chime, value: chime.set_option(led=value),
    ),
)

RULE_SWITCH_ENTITY = ReolinkSwitchIndexEntityDescription(
    key="rule",
    cmd_key="rules",
    translation_key="rule",
    placeholder=lambda api, ch, idx: api.baichuan.rule_name(ch, idx),
    value=lambda api, ch, idx: api.baichuan.rule_enabled(ch, idx),
    method=lambda api, ch, idx, value: (api.baichuan.set_rule_enabled(ch, idx, value)),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ReolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Reolink switch entities."""
    reolink_data: ReolinkData = config_entry.runtime_data

    entities: list[SwitchEntity] = [
        ReolinkSwitchEntity(reolink_data, channel, entity_description)
        for entity_description in SWITCH_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    ]
    entities.extend(
        ReolinkHostSwitchEntity(reolink_data, entity_description)
        for entity_description in HOST_SWITCH_ENTITIES
        if entity_description.supported(reolink_data.host.api)
    )
    entities.extend(
        ReolinkChimeSwitchEntity(reolink_data, chime, entity_description)
        for entity_description in CHIME_SWITCH_ENTITIES
        for chime in reolink_data.host.api.chime_list
        if chime.channel is not None
    )
    entities.extend(
        ReolinkHostChimeSwitchEntity(reolink_data, chime, entity_description)
        for entity_description in CHIME_SWITCH_ENTITIES
        for chime in reolink_data.host.api.chime_list
        if chime.channel is None
    )
    entities.extend(
        ReolinkIndexSwitchEntity(reolink_data, channel, rule_id, RULE_SWITCH_ENTITY)
        for channel in reolink_data.host.api.channels
        for rule_id in reolink_data.host.api.baichuan.rule_ids(channel)
    )

    async_add_entities(entities)


class ReolinkSwitchEntity(ReolinkChannelCoordinatorEntity, SwitchEntity):
    """Base switch entity class for Reolink IP cameras."""

    entity_description: ReolinkSwitchEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkSwitchEntityDescription,
    ) -> None:
        """Initialize Reolink switch entity."""
        self.entity_description = entity_description
        super().__init__(reolink_data, channel)

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.entity_description.value(self._host.api, self._channel)

    @raise_translated_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_description.method(self._host.api, self._channel, True)
        self.async_write_ha_state()

    @raise_translated_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_description.method(self._host.api, self._channel, False)
        self.async_write_ha_state()


class ReolinkHostSwitchEntity(ReolinkHostCoordinatorEntity, SwitchEntity):
    """Switch entity class for Reolink host features."""

    entity_description: ReolinkHostSwitchEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        entity_description: ReolinkHostSwitchEntityDescription,
    ) -> None:
        """Initialize Reolink switch entity."""
        self.entity_description = entity_description
        super().__init__(reolink_data)

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.entity_description.value(self._host.api)

    @raise_translated_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_description.method(self._host.api, True)
        self.async_write_ha_state()

    @raise_translated_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_description.method(self._host.api, False)
        self.async_write_ha_state()


class ReolinkChimeSwitchEntity(ReolinkChimeCoordinatorEntity, SwitchEntity):
    """Base switch entity class for a chime."""

    entity_description: ReolinkChimeSwitchEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        chime: Chime,
        entity_description: ReolinkChimeSwitchEntityDescription,
    ) -> None:
        """Initialize Reolink switch entity."""
        self.entity_description = entity_description
        super().__init__(reolink_data, chime)

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.entity_description.value(self._chime)

    @raise_translated_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_description.method(self._chime, True)
        self.async_write_ha_state()

    @raise_translated_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_description.method(self._chime, False)
        self.async_write_ha_state()


class ReolinkHostChimeSwitchEntity(ReolinkHostChimeCoordinatorEntity, SwitchEntity):
    """Base switch entity class for a chime."""

    entity_description: ReolinkChimeSwitchEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        chime: Chime,
        entity_description: ReolinkChimeSwitchEntityDescription,
    ) -> None:
        """Initialize Reolink switch entity."""
        self.entity_description = entity_description
        super().__init__(reolink_data, chime)

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.entity_description.value(self._chime)

    @raise_translated_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_description.method(self._chime, True)
        self.async_write_ha_state()

    @raise_translated_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_description.method(self._chime, False)
        self.async_write_ha_state()


class ReolinkIndexSwitchEntity(ReolinkChannelCoordinatorEntity, SwitchEntity):
    """Base switch entity class for Reolink IP camera with an extra index."""

    entity_description: ReolinkSwitchIndexEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        index: int,
        entity_description: ReolinkSwitchIndexEntityDescription,
    ) -> None:
        """Initialize Reolink switch entity."""
        self.entity_description = entity_description
        super().__init__(reolink_data, channel)
        self._index = index
        self._attr_translation_placeholders = {
            "name": entity_description.placeholder(self._host.api, self._channel, index)
        }
        self._attr_unique_id = f"{self._attr_unique_id}_{index}"

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.entity_description.value(self._host.api, self._channel, self._index)

    @raise_translated_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_description.method(
            self._host.api, self._channel, self._index, True
        )
        self.async_write_ha_state()

    @raise_translated_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_description.method(
            self._host.api, self._channel, self._index, False
        )
        self.async_write_ha_state()
