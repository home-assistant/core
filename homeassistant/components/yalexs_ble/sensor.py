"""Support for yalexs ble sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime as dt
from typing import Any

from yalexs_ble import ConnectionInfo, DoorActivity, LockActivity, LockInfo, LockState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YALEXSBLEConfigEntry
from .const import ATTR_REMOTE_TYPE, ATTR_SLOT, ATTR_SOURCE, ATTR_TIMESTAMP
from .entity import YALEXSBLEEntity
from .models import YaleXSBLEData


@dataclass(frozen=True, kw_only=True)
class YaleXSBLESensorEntityDescription(SensorEntityDescription):
    """Describes Yale Access Bluetooth sensor entity."""

    value_fn: Callable[[LockState, LockInfo, ConnectionInfo], int | float | None]


SENSORS: tuple[YaleXSBLESensorEntityDescription, ...] = (
    YaleXSBLESensorEntityDescription(
        key="",  # No key for the original RSSI sensor unique id
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_registry_enabled_default=False,
        value_fn=lambda state, info, connection: connection.rssi,
    ),
    YaleXSBLESensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda state, info, connection: state.battery.percentage
        if state.battery
        else None,
    ),
    YaleXSBLESensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda state, info, connection: state.battery.voltage
        if state.battery
        else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YALEXSBLEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up YALE XS Bluetooth sensors."""
    data = entry.runtime_data
    async_add_entities(
        (
            YaleXSBLEOperationSensor(data),
            *(YaleXSBLESensor(description, data) for description in SENSORS),
        )
    )


# RestoreSensor
class YaleXSBLEOperationSensor(YALEXSBLEEntity, SensorEntity):
    """Representation of an YaleXSBLE lock operation sensor."""

    _attr_translation_key = "operation"
    _attr_icon = "mdi:lock-clock"
    _attr_timestamp: dt.datetime | None = None
    _attr_source: str | None = None
    _attr_remote_type: str | None = None
    _attr_slot: int | None = None

    def __init__(
        self,
        data: YaleXSBLEData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data)
        self._attr_unique_id = f"{data.lock.address}operation"

    @callback
    def _async_activity_update(
        self,
        activity: DoorActivity | LockActivity,
        lock_info: LockInfo,
        connection_info: ConnectionInfo,
    ) -> None:
        """Handle activity update."""

        self._attr_native_value = None
        self._attr_timestamp = None
        self._attr_source = None
        self._attr_remote_type = None
        self._attr_slot = None

        if isinstance(activity, DoorActivity):
            self._attr_native_value = f"door_{activity.status.name.lower()}"
            self._attr_timestamp = activity.timestamp
        elif isinstance(activity, LockActivity):
            self._attr_native_value = f"lock_{activity.status.name.lower()}"
            self._attr_timestamp = activity.timestamp
            self._attr_source = activity.source.name.lower()
            self._attr_remote_type = (
                activity.remote_type.name.lower()
                if activity.remote_type is not None
                else None
            )
            self._attr_slot = activity.slot if activity.slot is not None else None

        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device specific state attributes."""
        attributes: dict[str, Any] = {}

        if self._attr_timestamp is not None:
            attributes[ATTR_TIMESTAMP] = self._attr_timestamp
        if self._attr_source is not None:
            attributes[ATTR_SOURCE] = self._attr_source
        if self._attr_remote_type is not None:
            attributes[ATTR_REMOTE_TYPE] = self._attr_remote_type
        if self._attr_slot is not None:
            attributes[ATTR_SLOT] = self._attr_slot

        return attributes

    async def async_added_to_hass(self) -> None:
        """Register callbacks & perform initial updates."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self._device.register_activity_callback(
                self._async_activity_update, request_update=True
            )
        )


class YaleXSBLESensor(YALEXSBLEEntity, SensorEntity):
    """Yale XS Bluetooth sensor."""

    entity_description: YaleXSBLESensorEntityDescription

    def __init__(
        self,
        description: YaleXSBLESensorEntityDescription,
        data: YaleXSBLEData,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(data)
        self._attr_unique_id = f"{data.lock.address}{description.key}"

    @callback
    def _async_update_state(
        self, new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Update the state."""
        self._attr_native_value = self.entity_description.value_fn(
            new_state, lock_info, connection_info
        )
        super()._async_update_state(new_state, lock_info, connection_info)
