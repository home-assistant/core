"""Component providing support for Reolink switch entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reolink_aio.api import Host

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkChannelCoordinatorEntity, ReolinkHostCoordinatorEntity


@dataclass
class ReolinkSwitchEntityDescriptionMixin:
    """Mixin values for Reolink switch entities."""

    value: Callable[[Host, int], bool]
    method: Callable[[Host, int, bool], Any]


@dataclass
class ReolinkSwitchEntityDescription(
    SwitchEntityDescription, ReolinkSwitchEntityDescriptionMixin
):
    """A class that describes switch entities."""

    supported: Callable[[Host, int], bool] = lambda api, ch: True


@dataclass
class ReolinkNVRSwitchEntityDescriptionMixin:
    """Mixin values for Reolink NVR switch entities."""

    value: Callable[[Host], bool]
    method: Callable[[Host, bool], Any]


@dataclass
class ReolinkNVRSwitchEntityDescription(
    SwitchEntityDescription, ReolinkNVRSwitchEntityDescriptionMixin
):
    """A class that describes NVR switch entities."""

    supported: Callable[[Host], bool] = lambda api: True


SWITCH_ENTITIES = (
    ReolinkSwitchEntityDescription(
        key="record_audio",
        name="Record audio",
        icon="mdi:microphone",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "audio"),
        value=lambda api, ch: api.audio_record(ch),
        method=lambda api, ch, value: api.set_audio(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="siren_on_event",
        name="Siren on event",
        icon="mdi:alarm-light",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "siren"),
        value=lambda api, ch: api.audio_alarm_enabled(ch),
        method=lambda api, ch, value: api.set_audio_alarm(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="auto_tracking",
        name="Auto tracking",
        icon="mdi:target-account",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "auto_track"),
        value=lambda api, ch: api.auto_track_enabled(ch),
        method=lambda api, ch, value: api.set_auto_tracking(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="auto_focus",
        name="Auto focus",
        icon="mdi:focus-field",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "auto_focus"),
        value=lambda api, ch: api.autofocus_enabled(ch),
        method=lambda api, ch, value: api.set_autofocus(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="gaurd_return",
        name="Guard return",
        icon="mdi:crosshairs-gps",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "ptz_guard"),
        value=lambda api, ch: api.ptz_guard_enabled(ch),
        method=lambda api, ch, value: api.set_ptz_guard(ch, enable=value),
    ),
)

NVR_SWITCH_ENTITIES = (
    ReolinkNVRSwitchEntityDescription(
        key="email",
        name="Email on event",
        icon="mdi:email",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api: api.supported(None, "email"),
        value=lambda api: api.email_enabled(),
        method=lambda api, value: api.set_email(None, value),
    ),
    ReolinkNVRSwitchEntityDescription(
        key="ftp_upload",
        name="FTP upload",
        icon="mdi:swap-horizontal",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api: api.supported(None, "ftp"),
        value=lambda api: api.ftp_enabled(),
        method=lambda api, value: api.set_ftp(None, value),
    ),
    ReolinkNVRSwitchEntityDescription(
        key="push_notifications",
        name="Push notifications",
        icon="mdi:message-badge",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api: api.supported(None, "push"),
        value=lambda api: api.push_enabled(),
        method=lambda api, value: api.set_push(None, value),
    ),
    ReolinkNVRSwitchEntityDescription(
        key="record",
        name="Record",
        icon="mdi:record-rec",
        supported=lambda api: api.supported(None, "recording"),
        value=lambda api: api.recording_enabled(),
        method=lambda api, value: api.set_recording(None, value),
    ),
    ReolinkNVRSwitchEntityDescription(
        key="buzzer",
        name="Buzzer on event",
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
        super().__init__(reolink_data, channel)
        self.entity_description = entity_description

        self._attr_unique_id = (
            f"{self._host.unique_id}_{channel}_{entity_description.key}"
        )

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.entity_description.value(self._host.api, self._channel)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_description.method(self._host.api, self._channel, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_description.method(self._host.api, self._channel, False)
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
        super().__init__(reolink_data)
        self.entity_description = entity_description

        self._attr_unique_id = f"{self._host.unique_id}_{entity_description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.entity_description.value(self._host.api)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_description.method(self._host.api, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_description.method(self._host.api, False)
        self.async_write_ha_state()
