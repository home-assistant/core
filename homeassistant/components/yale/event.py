"""Support for yale events."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from yalexs.activity import Activity
from yalexs.doorbell import DoorbellDetail
from yalexs.lock import LockDetail

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YaleConfigEntry, YaleData
from .entity import YaleDescriptionEntity
from .util import (
    retrieve_ding_activity,
    retrieve_doorbell_motion_activity,
    retrieve_online_state,
)


@dataclass(kw_only=True, frozen=True)
class YaleEventEntityDescription(EventEntityDescription):
    """Describe yale event entities."""

    value_fn: Callable[[YaleData, DoorbellDetail | LockDetail], Activity | None]


TYPES_VIDEO_DOORBELL: tuple[YaleEventEntityDescription, ...] = (
    YaleEventEntityDescription(
        key="motion",
        translation_key="motion",
        device_class=EventDeviceClass.MOTION,
        event_types=["motion"],
        value_fn=retrieve_doorbell_motion_activity,
    ),
)


TYPES_DOORBELL: tuple[YaleEventEntityDescription, ...] = (
    YaleEventEntityDescription(
        key="doorbell",
        translation_key="doorbell",
        device_class=EventDeviceClass.DOORBELL,
        event_types=["ring"],
        value_fn=retrieve_ding_activity,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: YaleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the yale event platform."""
    data = config_entry.runtime_data
    entities: list[YaleEventEntity] = [
        YaleEventEntity(data, lock, description)
        for description in TYPES_DOORBELL
        for lock in data.locks
        if (detail := data.get_device_detail(lock.device_id)) and detail.doorbell
    ]
    entities.extend(
        YaleEventEntity(data, doorbell, description)
        for description in TYPES_DOORBELL + TYPES_VIDEO_DOORBELL
        for doorbell in data.doorbells
    )
    async_add_entities(entities)


class YaleEventEntity(YaleDescriptionEntity, EventEntity):
    """An yale event entity."""

    entity_description: YaleEventEntityDescription
    _last_activity: Activity | None = None

    @callback
    def _update_from_data(self) -> None:
        """Update from data."""
        self._attr_available = retrieve_online_state(self._data, self._detail)
        current_activity = self.entity_description.value_fn(self._data, self._detail)
        if not current_activity or current_activity == self._last_activity:
            return
        self._last_activity = current_activity
        event_types = self.entity_description.event_types
        if TYPE_CHECKING:
            assert event_types is not None
        self._trigger_event(event_type=event_types[0])
        self.async_write_ha_state()
