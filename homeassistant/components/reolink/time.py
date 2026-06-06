"""Component providing support for Reolink time entities."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import time
from typing import Any

from reolink_aio.api import Host
from reolink_aio.enums import SpotlightModeEnum

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ReolinkChannelCoordinatorEntity, ReolinkChannelEntityDescription
from .util import ReolinkConfigEntry, ReolinkData, raise_translated_error

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ReolinkTimeEntityDescription(
    TimeEntityDescription,
    ReolinkChannelEntityDescription,
):
    """A class that describes time entities."""

    method: Callable[[Host, int, time], Any]
    value: Callable[[Host, int], time | None]


def _schedule_time(api: Host, ch: int, start: bool) -> time | None:
    """Return the start or end time of the floodlight schedule."""
    schedule = api.whiteled_schedule(ch)
    if not schedule:
        return None
    if start:
        return time(hour=schedule["StartHour"], minute=schedule["StartMin"])
    return time(hour=schedule["EndHour"], minute=schedule["EndMin"])


def _set_start(api: Host, ch: int, value: time) -> Any:
    """Set the start time of the floodlight schedule."""
    schedule = api.whiteled_schedule(ch) or {}
    return api.set_spotlight_lighting_schedule(
        ch,
        schedule.get("EndHour", 0),
        schedule.get("EndMin", 0),
        value.hour,
        value.minute,
    )


def _set_end(api: Host, ch: int, value: time) -> Any:
    """Set the end time of the floodlight schedule."""
    schedule = api.whiteled_schedule(ch) or {}
    return api.set_spotlight_lighting_schedule(
        ch,
        value.hour,
        value.minute,
        schedule.get("StartHour", 0),
        schedule.get("StartMin", 0),
    )


TIME_ENTITIES = (
    ReolinkTimeEntityDescription(
        key="floodlight_schedule_start",
        cmd_key="GetWhiteLed",
        cmd_id=[289, 438],
        translation_key="floodlight_schedule_start",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        supported=lambda api, ch: (
            SpotlightModeEnum.schedule.name in api.whiteled_mode_list(ch)
        ),
        value=lambda api, ch: _schedule_time(api, ch, True),
        method=_set_start,
    ),
    ReolinkTimeEntityDescription(
        key="floodlight_schedule_end",
        cmd_key="GetWhiteLed",
        cmd_id=[289, 438],
        translation_key="floodlight_schedule_end",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        supported=lambda api, ch: (
            SpotlightModeEnum.schedule.name in api.whiteled_mode_list(ch)
        ),
        value=lambda api, ch: _schedule_time(api, ch, False),
        method=_set_end,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ReolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Reolink time entities."""
    reolink_data: ReolinkData = config_entry.runtime_data
    api = reolink_data.host.api

    async_add_entities(
        ReolinkTimeEntity(reolink_data, channel, entity_description)
        for entity_description in TIME_ENTITIES
        for channel in api.channels
        if entity_description.supported(api, channel)
    )


class ReolinkTimeEntity(ReolinkChannelCoordinatorEntity, TimeEntity):
    """Base time entity class for Reolink IP cameras."""

    entity_description: ReolinkTimeEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkTimeEntityDescription,
    ) -> None:
        """Initialize Reolink time entity."""
        self.entity_description = entity_description
        super().__init__(reolink_data, channel)

    @property
    def native_value(self) -> time | None:
        """Return the current value."""
        return self.entity_description.value(self._host.api, self._channel)

    @raise_translated_error
    async def async_set_value(self, value: time) -> None:
        """Update the current value."""
        await self.entity_description.method(self._host.api, self._channel, value)
        self.async_write_ha_state()
