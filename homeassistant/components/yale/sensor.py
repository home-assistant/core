"""Support for Yale sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from yalexs.activity import ActivityType, LockOperationActivity
from yalexs.doorbell import Doorbell
from yalexs.keypad import KeypadDetail
from yalexs.lock import LockDetail

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import YaleConfigEntry
from .const import (
    ATTR_OPERATION_AUTORELOCK,
    ATTR_OPERATION_KEYPAD,
    ATTR_OPERATION_MANUAL,
    ATTR_OPERATION_METHOD,
    ATTR_OPERATION_REMOTE,
    ATTR_OPERATION_TAG,
    OPERATION_METHOD_AUTORELOCK,
    OPERATION_METHOD_KEYPAD,
    OPERATION_METHOD_MANUAL,
    OPERATION_METHOD_MOBILE_DEVICE,
    OPERATION_METHOD_REMOTE,
    OPERATION_METHOD_TAG,
)
from .entity import YaleDescriptionEntity, YaleEntity


def _retrieve_device_battery_state(detail: LockDetail) -> int:
    """Get the latest state of the sensor."""
    return detail.battery_level


def _retrieve_linked_keypad_battery_state(detail: KeypadDetail) -> int | None:
    """Get the latest state of the sensor."""
    return detail.battery_percentage


@dataclass(frozen=True, kw_only=True)
class YaleSensorEntityDescription[T: LockDetail | KeypadDetail](
    SensorEntityDescription
):
    """Mixin for required keys."""

    value_fn: Callable[[T], int | None]


SENSOR_TYPE_DEVICE_BATTERY = YaleSensorEntityDescription[LockDetail](
    key="device_battery",
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_retrieve_device_battery_state,
)

SENSOR_TYPE_KEYPAD_BATTERY = YaleSensorEntityDescription[KeypadDetail](
    key="linked_keypad_battery",
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_retrieve_linked_keypad_battery_state,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: YaleConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Yale sensors."""
    data = config_entry.runtime_data
    entities: list[SensorEntity] = []

    for device in data.locks:
        detail = data.get_device_detail(device.device_id)
        entities.append(YaleOperatorSensor(data, device, "lock_operator"))
        if SENSOR_TYPE_DEVICE_BATTERY.value_fn(detail):
            entities.append(
                YaleBatterySensor[LockDetail](data, device, SENSOR_TYPE_DEVICE_BATTERY)
            )
        if keypad := detail.keypad:
            entities.append(
                YaleBatterySensor[KeypadDetail](
                    data, keypad, SENSOR_TYPE_KEYPAD_BATTERY
                )
            )

    entities.extend(
        YaleBatterySensor[Doorbell](data, device, SENSOR_TYPE_DEVICE_BATTERY)
        for device in data.doorbells
        if SENSOR_TYPE_DEVICE_BATTERY.value_fn(data.get_device_detail(device.device_id))
    )

    async_add_entities(entities)


class YaleOperatorSensor(YaleEntity, RestoreSensor):
    """Representation of an Yale lock operation sensor."""

    _attr_translation_key = "operator"
    _operated_remote: bool | None = None
    _operated_keypad: bool | None = None
    _operated_manual: bool | None = None
    _operated_tag: bool | None = None
    _operated_autorelock: bool | None = None

    @callback
    def _update_from_data(self) -> None:
        """Get the latest state of the sensor and update activity."""
        self._attr_available = True
        if lock_activity := self._get_latest({ActivityType.LOCK_OPERATION}):
            lock_activity = cast(LockOperationActivity, lock_activity)
            self._attr_native_value = lock_activity.operated_by
            self._operated_remote = lock_activity.operated_remote
            self._operated_keypad = lock_activity.operated_keypad
            self._operated_manual = lock_activity.operated_manual
            self._operated_tag = lock_activity.operated_tag
            self._operated_autorelock = lock_activity.operated_autorelock
            self._attr_entity_picture = lock_activity.operator_thumbnail_url

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device specific state attributes."""
        attributes: dict[str, Any] = {}

        if self._operated_remote is not None:
            attributes[ATTR_OPERATION_REMOTE] = self._operated_remote
        if self._operated_keypad is not None:
            attributes[ATTR_OPERATION_KEYPAD] = self._operated_keypad
        if self._operated_manual is not None:
            attributes[ATTR_OPERATION_MANUAL] = self._operated_manual
        if self._operated_tag is not None:
            attributes[ATTR_OPERATION_TAG] = self._operated_tag
        if self._operated_autorelock is not None:
            attributes[ATTR_OPERATION_AUTORELOCK] = self._operated_autorelock

        if self._operated_remote:
            attributes[ATTR_OPERATION_METHOD] = OPERATION_METHOD_REMOTE
        elif self._operated_keypad:
            attributes[ATTR_OPERATION_METHOD] = OPERATION_METHOD_KEYPAD
        elif self._operated_manual:
            attributes[ATTR_OPERATION_METHOD] = OPERATION_METHOD_MANUAL
        elif self._operated_tag:
            attributes[ATTR_OPERATION_METHOD] = OPERATION_METHOD_TAG
        elif self._operated_autorelock:
            attributes[ATTR_OPERATION_METHOD] = OPERATION_METHOD_AUTORELOCK
        else:
            attributes[ATTR_OPERATION_METHOD] = OPERATION_METHOD_MOBILE_DEVICE

        return attributes

    async def async_added_to_hass(self) -> None:
        """Restore ATTR_CHANGED_BY on startup since it is likely no longer in the activity log."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        last_sensor_state = await self.async_get_last_sensor_data()
        if (
            not last_state
            or not last_sensor_state
            or last_state.state == STATE_UNAVAILABLE
        ):
            return

        self._attr_native_value = last_sensor_state.native_value
        last_attrs = last_state.attributes
        if ATTR_ENTITY_PICTURE in last_attrs:
            self._attr_entity_picture = last_attrs[ATTR_ENTITY_PICTURE]
        if ATTR_OPERATION_REMOTE in last_attrs:
            self._operated_remote = last_attrs[ATTR_OPERATION_REMOTE]
        if ATTR_OPERATION_KEYPAD in last_attrs:
            self._operated_keypad = last_attrs[ATTR_OPERATION_KEYPAD]
        if ATTR_OPERATION_MANUAL in last_attrs:
            self._operated_manual = last_attrs[ATTR_OPERATION_MANUAL]
        if ATTR_OPERATION_TAG in last_attrs:
            self._operated_tag = last_attrs[ATTR_OPERATION_TAG]
        if ATTR_OPERATION_AUTORELOCK in last_attrs:
            self._operated_autorelock = last_attrs[ATTR_OPERATION_AUTORELOCK]


class YaleBatterySensor[T: LockDetail | KeypadDetail](
    YaleDescriptionEntity, SensorEntity
):
    """Representation of an Yale sensor."""

    entity_description: YaleSensorEntityDescription[T]
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    @callback
    def _update_from_data(self) -> None:
        """Get the latest state of the sensor."""
        self._attr_native_value = self.entity_description.value_fn(self._detail)
        self._attr_available = self._attr_native_value is not None
