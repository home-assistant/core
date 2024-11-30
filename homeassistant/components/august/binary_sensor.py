"""Support for August binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
import logging

from yalexs.activity import Activity, ActivityType
from yalexs.doorbell import DoorbellDetail
from yalexs.lock import LockDetail, LockDoorStatus
from yalexs.manager.const import ACTIVITY_UPDATE_INTERVAL
from yalexs.util import update_lock_detail_from_activity

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import AugustConfigEntry, AugustData
from .entity import AugustDescriptionEntity
from .util import (
    retrieve_ding_activity,
    retrieve_doorbell_motion_activity,
    retrieve_online_state,
    retrieve_time_based_activity,
)

_LOGGER = logging.getLogger(__name__)

TIME_TO_RECHECK_DETECTION = timedelta(
    seconds=ACTIVITY_UPDATE_INTERVAL.total_seconds() * 3
)


@dataclass(frozen=True, kw_only=True)
class AugustDoorbellBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes August binary_sensor entity."""

    value_fn: Callable[[AugustData, DoorbellDetail | LockDetail], Activity | None]
    is_time_based: bool


SENSOR_TYPE_DOOR = BinarySensorEntityDescription(
    key="open",
    device_class=BinarySensorDeviceClass.DOOR,
)

SENSOR_TYPES_VIDEO_DOORBELL = (
    AugustDoorbellBinarySensorEntityDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        value_fn=retrieve_doorbell_motion_activity,
        is_time_based=True,
    ),
    AugustDoorbellBinarySensorEntityDescription(
        key="image capture",
        translation_key="image_capture",
        value_fn=partial(
            retrieve_time_based_activity, {ActivityType.DOORBELL_IMAGE_CAPTURE}
        ),
        is_time_based=True,
    ),
    AugustDoorbellBinarySensorEntityDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=retrieve_online_state,
        is_time_based=False,
    ),
)


SENSOR_TYPES_DOORBELL: tuple[AugustDoorbellBinarySensorEntityDescription, ...] = (
    AugustDoorbellBinarySensorEntityDescription(
        key="ding",
        translation_key="ding",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        value_fn=retrieve_ding_activity,
        is_time_based=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AugustConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the August binary sensors."""
    data = config_entry.runtime_data
    entities: list[BinarySensorEntity] = []

    for lock in data.locks:
        detail = data.get_device_detail(lock.device_id)
        if detail.doorsense:
            entities.append(AugustDoorBinarySensor(data, lock, SENSOR_TYPE_DOOR))

        if detail.doorbell:
            entities.extend(
                AugustDoorbellBinarySensor(data, lock, description)
                for description in SENSOR_TYPES_DOORBELL
            )

    entities.extend(
        AugustDoorbellBinarySensor(data, doorbell, description)
        for description in SENSOR_TYPES_DOORBELL + SENSOR_TYPES_VIDEO_DOORBELL
        for doorbell in data.doorbells
    )
    async_add_entities(entities)


class AugustDoorBinarySensor(AugustDescriptionEntity, BinarySensorEntity):
    """Representation of an August Door binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.DOOR
    description: BinarySensorEntityDescription

    @callback
    def _update_from_data(self) -> None:
        """Get the latest state of the sensor and update activity."""
        if door_activity := self._get_latest({ActivityType.DOOR_OPERATION}):
            update_lock_detail_from_activity(self._detail, door_activity)
            if door_activity.was_pushed:
                self._detail.set_online(True)

        if bridge_activity := self._get_latest({ActivityType.BRIDGE_OPERATION}):
            update_lock_detail_from_activity(self._detail, bridge_activity)
        self._attr_available = self._detail.bridge_is_online
        self._attr_is_on = self._detail.door_state == LockDoorStatus.OPEN


class AugustDoorbellBinarySensor(AugustDescriptionEntity, BinarySensorEntity):
    """Representation of an August binary sensor."""

    entity_description: AugustDoorbellBinarySensorEntityDescription
    _check_for_off_update_listener: Callable[[], None] | None = None

    @callback
    def _update_from_data(self) -> None:
        """Get the latest state of the sensor."""
        self._cancel_any_pending_updates()
        self._attr_is_on = bool(
            self.entity_description.value_fn(self._data, self._detail)
        )

        if self.entity_description.is_time_based:
            self._attr_available = retrieve_online_state(self._data, self._detail)
            self._schedule_update_to_recheck_turn_off_sensor()
        else:
            self._attr_available = True

    @callback
    def _async_scheduled_update(self, now: datetime) -> None:
        """Timer callback for sensor update."""
        self._check_for_off_update_listener = None
        self._update_from_data()
        if not self.is_on:
            self.async_write_ha_state()

    def _schedule_update_to_recheck_turn_off_sensor(self) -> None:
        """Schedule an update to recheck the sensor to see if it is ready to turn off."""
        # If the sensor is already off there is nothing to do
        if not self.is_on:
            return
        self._check_for_off_update_listener = async_call_later(
            self.hass, TIME_TO_RECHECK_DETECTION, self._async_scheduled_update
        )

    def _cancel_any_pending_updates(self) -> None:
        """Cancel any updates to recheck a sensor to see if it is ready to turn off."""
        if not self._check_for_off_update_listener:
            return
        _LOGGER.debug("%s: canceled pending update", self.entity_id)
        self._check_for_off_update_listener()
        self._check_for_off_update_listener = None

    async def async_will_remove_from_hass(self) -> None:
        """When removing cancel any scheduled updates."""
        self._cancel_any_pending_updates()
        await super().async_will_remove_from_hass()
