"""Support for August sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Generic, TypeVar, cast

from yalexs.activity import ActivityType, LockOperationActivity
from yalexs.doorbell import Doorbell
from yalexs.keypad import KeypadDetail
from yalexs.lock import Lock, LockDetail

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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AugustConfigEntry, AugustData
from .const import (
    ATTR_OPERATION_AUTORELOCK,
    ATTR_OPERATION_KEYPAD,
    ATTR_OPERATION_MANUAL,
    ATTR_OPERATION_METHOD,
    ATTR_OPERATION_REMOTE,
    ATTR_OPERATION_TAG,
    DOMAIN,
    OPERATION_METHOD_AUTORELOCK,
    OPERATION_METHOD_KEYPAD,
    OPERATION_METHOD_MANUAL,
    OPERATION_METHOD_MOBILE_DEVICE,
    OPERATION_METHOD_REMOTE,
    OPERATION_METHOD_TAG,
)
from .entity import AugustEntityMixin

_LOGGER = logging.getLogger(__name__)


def _retrieve_device_battery_state(detail: LockDetail) -> int:
    """Get the latest state of the sensor."""
    return detail.battery_level


def _retrieve_linked_keypad_battery_state(detail: KeypadDetail) -> int | None:
    """Get the latest state of the sensor."""
    return detail.battery_percentage


_T = TypeVar("_T", LockDetail, KeypadDetail)


@dataclass(frozen=True)
class AugustRequiredKeysMixin(Generic[_T]):
    """Mixin for required keys."""

    value_fn: Callable[[_T], int | None]


@dataclass(frozen=True)
class AugustSensorEntityDescription(
    SensorEntityDescription, AugustRequiredKeysMixin[_T]
):
    """Describes August sensor entity."""


SENSOR_TYPE_DEVICE_BATTERY = AugustSensorEntityDescription[LockDetail](
    key="device_battery",
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_retrieve_device_battery_state,
)

SENSOR_TYPE_KEYPAD_BATTERY = AugustSensorEntityDescription[KeypadDetail](
    key="linked_keypad_battery",
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_retrieve_linked_keypad_battery_state,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AugustConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the August sensors."""
    data = config_entry.runtime_data
    entities: list[SensorEntity] = []
    migrate_unique_id_devices = []
    operation_sensors = []
    batteries: dict[str, list[Doorbell | Lock]] = {
        "device_battery": [],
        "linked_keypad_battery": [],
    }
    for device in data.doorbells:
        batteries["device_battery"].append(device)
    for device in data.locks:
        batteries["device_battery"].append(device)
        batteries["linked_keypad_battery"].append(device)
        operation_sensors.append(device)

    for device in batteries["device_battery"]:
        detail = data.get_device_detail(device.device_id)
        if detail is None or SENSOR_TYPE_DEVICE_BATTERY.value_fn(detail) is None:
            _LOGGER.debug(
                "Not adding battery sensor for %s because it is not present",
                device.device_name,
            )
            continue
        _LOGGER.debug(
            "Adding battery sensor for %s",
            device.device_name,
        )
        entities.append(
            AugustBatterySensor[LockDetail](
                data, device, device, SENSOR_TYPE_DEVICE_BATTERY
            )
        )

    for device in batteries["linked_keypad_battery"]:
        detail = data.get_device_detail(device.device_id)

        if detail.keypad is None:
            _LOGGER.debug(
                "Not adding keypad battery sensor for %s because it is not present",
                device.device_name,
            )
            continue
        _LOGGER.debug(
            "Adding keypad battery sensor for %s",
            device.device_name,
        )
        keypad_battery_sensor = AugustBatterySensor[KeypadDetail](
            data, detail.keypad, device, SENSOR_TYPE_KEYPAD_BATTERY
        )
        entities.append(keypad_battery_sensor)
        migrate_unique_id_devices.append(keypad_battery_sensor)

    entities.extend(AugustOperatorSensor(data, device) for device in operation_sensors)

    await _async_migrate_old_unique_ids(hass, migrate_unique_id_devices)

    async_add_entities(entities)


async def _async_migrate_old_unique_ids(hass: HomeAssistant, devices) -> None:
    """Keypads now have their own serial number."""
    registry = er.async_get(hass)
    for device in devices:
        old_entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, device.old_unique_id
        )
        if old_entity_id is not None:
            _LOGGER.debug(
                "Migrating unique_id from [%s] to [%s]",
                device.old_unique_id,
                device.unique_id,
            )
            registry.async_update_entity(old_entity_id, new_unique_id=device.unique_id)


class AugustOperatorSensor(AugustEntityMixin, RestoreSensor):
    """Representation of an August lock operation sensor."""

    _attr_translation_key = "operator"

    def __init__(self, data: AugustData, device) -> None:
        """Initialize the sensor."""
        super().__init__(data, device)
        self._data = data
        self._device = device
        self._operated_remote: bool | None = None
        self._operated_keypad: bool | None = None
        self._operated_manual: bool | None = None
        self._operated_tag: bool | None = None
        self._operated_autorelock: bool | None = None
        self._operated_time = None
        self._attr_unique_id = f"{self._device_id}_lock_operator"
        self._update_from_data()

    @callback
    def _update_from_data(self) -> None:
        """Get the latest state of the sensor and update activity."""
        lock_activity = self._data.activity_stream.get_latest_device_activity(
            self._device_id, {ActivityType.LOCK_OPERATION}
        )

        self._attr_available = True
        if lock_activity is not None:
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
        if ATTR_ENTITY_PICTURE in last_state.attributes:
            self._attr_entity_picture = last_state.attributes[ATTR_ENTITY_PICTURE]
        if ATTR_OPERATION_REMOTE in last_state.attributes:
            self._operated_remote = last_state.attributes[ATTR_OPERATION_REMOTE]
        if ATTR_OPERATION_KEYPAD in last_state.attributes:
            self._operated_keypad = last_state.attributes[ATTR_OPERATION_KEYPAD]
        if ATTR_OPERATION_MANUAL in last_state.attributes:
            self._operated_manual = last_state.attributes[ATTR_OPERATION_MANUAL]
        if ATTR_OPERATION_TAG in last_state.attributes:
            self._operated_tag = last_state.attributes[ATTR_OPERATION_TAG]
        if ATTR_OPERATION_AUTORELOCK in last_state.attributes:
            self._operated_autorelock = last_state.attributes[ATTR_OPERATION_AUTORELOCK]


class AugustBatterySensor(AugustEntityMixin, SensorEntity, Generic[_T]):
    """Representation of an August sensor."""

    entity_description: AugustSensorEntityDescription[_T]
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        data: AugustData,
        device,
        old_device,
        description: AugustSensorEntityDescription[_T],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data, device)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}_{description.key}"
        self.old_unique_id = f"{old_device.device_id}_{description.key}"
        self._update_from_data()

    @callback
    def _update_from_data(self) -> None:
        """Get the latest state of the sensor."""
        self._attr_native_value = self.entity_description.value_fn(self._detail)
        self._attr_available = self._attr_native_value is not None
