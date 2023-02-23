"""This component provides support for Reolink switch entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reolink_aio.api import Host

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkCoordinatorEntity


@dataclass
class ReolinkSwitchEntityDescriptionMixin:
    """Mixin values for Reolink switch entities."""

    value: Callable[[Host, int | None], bool]
    method: Callable[[Host, int | None, bool], Any]


@dataclass
class ReolinkSwitchEntityDescription(
    SwitchEntityDescription, ReolinkSwitchEntityDescriptionMixin
):
    """A class that describes switch entities."""

    supported: Callable[[Host, int | None], bool] = lambda api, ch: True


SWITCH_ENTITIES = (
    ReolinkSwitchEntityDescription(
        key="record_audio",
        name="Record audio",
        icon="mdi:microphone",
        supported=lambda api, ch: api.supported(ch, "audio"),
        value=lambda api, ch: api.audio_record(ch),
        method=lambda api, ch, value: api.set_audio(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="siren_on_event",
        name="Siren on event",
        icon="mdi:alarm-light",
        supported=lambda api, ch: api.supported(ch, "siren"),
        value=lambda api, ch: api.audio_alarm_enabled(ch),
        method=lambda api, ch, value: api.set_audio_alarm(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="auto_tracking",
        name="Auto tracking",
        icon="mdi:target-account",
        supported=lambda api, ch: api.supported(ch, "auto_track"),
        value=lambda api, ch: api.auto_track_enabled(ch),
        method=lambda api, ch, value: api.set_auto_tracking(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="auto_focus",
        name="Auto focus",
        icon="mdi:focus-field",
        supported=lambda api, ch: api.supported(ch, "auto_focus"),
        value=lambda api, ch: api.autofocus_enabled(ch),
        method=lambda api, ch, value: api.set_autofocus(ch, value),
    ),
    ReolinkSwitchEntityDescription(
        key="gaurd_return",
        name="Guard return",
        icon="mdi:crosshairs-gps",
        supported=lambda api, ch: api.supported(ch, "ptz_guard"),
        value=lambda api, ch: api.ptz_guard_enabled(ch),
        method=lambda api, ch, value: api.set_ptz_guard(ch, enable=value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink switch entities."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        ReolinkSwitchEntity(reolink_data, channel, entity_description)
        for entity_description in SWITCH_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    )


class ReolinkSwitchEntity(ReolinkCoordinatorEntity, SwitchEntity):
    """Base switch entity class for Reolink IP cameras."""

    _attr_has_entity_name = True
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
            f"{self._host.unique_id}_{self._channel}_{entity_description.key}"
        )

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.entity_description.value(self._host.api, self._channel)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.entity_description.method(self._host.api, self._channel, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.entity_description.method(self._host.api, self._channel, False)
        self.async_write_ha_state()
