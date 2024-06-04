"""Component providing support for Reolink switch entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reolink_aio.api import Host
from reolink_aio.exceptions import ReolinkError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import (
    ReolinkChannelCoordinatorEntity,
    ReolinkChannelEntityDescription,
    ReolinkHostCoordinatorEntity,
    ReolinkHostEntityDescription,
)


@dataclass(frozen=True, kw_only=True)
class ReolinkSwitchEntityDescription(
    SwitchEntityDescription,
    ReolinkChannelEntityDescription,
):
    """A class that describes switch entities."""

    method: Callable[[Host, int, bool], Any]
    value: Callable[[Host, int], bool | None]


@dataclass(frozen=True, kw_only=True)
class ReolinkNVRSwitchEntityDescription(
    SwitchEntityDescription,
    ReolinkHostEntityDescription,
):
    """A class that describes NVR switch entities."""

    method: Callable[[Host, bool], Any]
    value: Callable[[Host], bool]


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
        supported=lambda api, ch: api.supported(ch, "recording") and api.is_nvr,
        value=lambda api, ch: api.recording_enabled(ch),
        method=lambda api, ch, value: api.set_recording(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="buzzer",
        cmd_key="GetBuzzerAlarmV20",
        translation_key="buzzer",
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
        key="hdr",
        cmd_key="GetIsp",
        translation_key="hdr",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        supported=lambda api, ch: api.supported(ch, "HDR"),
        value=lambda api, ch: api.HDR_on(ch) is True,
        method=lambda api, ch, value: api.set_HDR(ch, value),
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
)

NVR_SWITCH_ENTITIES = (
    ReolinkNVRSwitchEntityDescription(
        key="email",
        cmd_key="GetEmail",
        translation_key="email",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api: api.supported(None, "email"),
        value=lambda api: api.email_enabled(),
        method=lambda api, value: api.set_email(None, value),
    ),
    ReolinkNVRSwitchEntityDescription(
        key="ftp_upload",
        cmd_key="GetFtp",
        translation_key="ftp_upload",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api: api.supported(None, "ftp"),
        value=lambda api: api.ftp_enabled(),
        method=lambda api, value: api.set_ftp(None, value),
    ),
    ReolinkNVRSwitchEntityDescription(
        key="push_notifications",
        cmd_key="GetPush",
        translation_key="push_notifications",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api: api.supported(None, "push"),
        value=lambda api: api.push_enabled(),
        method=lambda api, value: api.set_push(None, value),
    ),
    ReolinkNVRSwitchEntityDescription(
        key="record",
        cmd_key="GetRec",
        translation_key="record",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api: api.supported(None, "recording"),
        value=lambda api: api.recording_enabled(),
        method=lambda api, value: api.set_recording(None, value),
    ),
    ReolinkNVRSwitchEntityDescription(
        key="buzzer",
        cmd_key="GetBuzzerAlarmV20",
        translation_key="buzzer",
        icon="mdi:room-service",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api: api.supported(None, "buzzer"),
        value=lambda api: api.buzzer_enabled(),
        method=lambda api, value: api.set_buzzer(None, value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink switch entities."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[ReolinkSwitchEntity | ReolinkNVRSwitchEntity] = [
        ReolinkSwitchEntity(reolink_data, channel, entity_description)
        for entity_description in SWITCH_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    ]
    entities.extend(
        [
            ReolinkNVRSwitchEntity(reolink_data, entity_description)
            for entity_description in NVR_SWITCH_ENTITIES
            if entity_description.supported(reolink_data.host.api)
        ]
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        try:
            await self.entity_description.method(self._host.api, self._channel, True)
        except ReolinkError as err:
            raise HomeAssistantError(err) from err
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        try:
            await self.entity_description.method(self._host.api, self._channel, False)
        except ReolinkError as err:
            raise HomeAssistantError(err) from err
        self.async_write_ha_state()


class ReolinkNVRSwitchEntity(ReolinkHostCoordinatorEntity, SwitchEntity):
    """Switch entity class for Reolink NVR features."""

    entity_description: ReolinkNVRSwitchEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        entity_description: ReolinkNVRSwitchEntityDescription,
    ) -> None:
        """Initialize Reolink switch entity."""
        self.entity_description = entity_description
        super().__init__(reolink_data)

        self._attr_unique_id = f"{self._host.unique_id}_{entity_description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.entity_description.value(self._host.api)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        try:
            await self.entity_description.method(self._host.api, True)
        except ReolinkError as err:
            raise HomeAssistantError(err) from err
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        try:
            await self.entity_description.method(self._host.api, False)
        except ReolinkError as err:
            raise HomeAssistantError(err) from err
        self.async_write_ha_state()
