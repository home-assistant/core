"""Binary sensors for Yale Alarm."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import YaleConfigEntry
from .const import ALARM_TRIGGER_WINDOW
from .coordinator import YaleDataUpdateCoordinator
from .entity import YaleAlarmEntity, YaleEntity

SENSOR_TYPES = (
    BinarySensorEntityDescription(
        key="acfail",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="power_loss",
    ),
    BinarySensorEntityDescription(
        key="battery",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="battery",
    ),
    BinarySensorEntityDescription(
        key="tamper",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="tamper",
    ),
    BinarySensorEntityDescription(
        key="jam",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="jam",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YaleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Yale binary sensor entry."""

    coordinator = entry.runtime_data
    sensors: list[
        YaleDoorSensor
        | YaleDoorBatterySensor
        | YaleProblemSensor
        | YaleAlarmTriggeredSensor
    ] = [YaleDoorSensor(coordinator, data) for data in coordinator.data["door_windows"]]
    sensors.extend(
        YaleDoorBatterySensor(coordinator, data)
        for data in coordinator.data["door_windows"]
    )
    sensors.extend(
        YaleProblemSensor(coordinator, description) for description in SENSOR_TYPES
    )
    sensors.append(YaleAlarmTriggeredSensor(coordinator))

    async_add_entities(sensors)


class YaleDoorSensor(YaleEntity, BinarySensorEntity):
    """Representation of a Yale door sensor."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return bool(self.coordinator.data["sensor_map"][self._attr_unique_id] == "open")


class YaleDoorBatterySensor(YaleEntity, BinarySensorEntity):
    """Representation of a Yale door sensor battery status."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(
        self,
        coordinator: YaleDataUpdateCoordinator,
        data: dict,
    ) -> None:
        """Initiate Yale door battery Sensor."""
        super().__init__(coordinator, data)
        self._attr_unique_id = f"{data['address']}-battery"

    @property
    def is_on(self) -> bool:
        """Return true if the battery is low."""
        state: bool = self.coordinator.data["sensor_battery_map"][self._attr_unique_id]
        return state


class YaleProblemSensor(YaleAlarmEntity, BinarySensorEntity):
    """Representation of a Yale problem sensor."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: YaleDataUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initiate Yale Problem Sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{entity_description.key}"
        )

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return bool(
            self.coordinator.data["status"][self.entity_description.key]
            != "main.normal"
        )


class YaleAlarmTriggeredSensor(YaleAlarmEntity, BinarySensorEntity):
    """Binary sensor that indicates the latest alarm event is a recent trigger event."""

    _attr_device_class = None
    _attr_name = "Alarm Triggered"
    _attr_translation_key = None
    _attr_icon = "mdi:alarm-light-outline"

    _WINDOW = timedelta(minutes=ALARM_TRIGGER_WINDOW)

    def __init__(self, coordinator: YaleDataUpdateCoordinator) -> None:
        """Initialize the alarm-triggered entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-alarm_triggered"

    def _latest_event(self) -> dict:
        return self.coordinator.data.get("alarm_event_latest") or {}

    def _event_dt(self) -> datetime | None:
        raw_time = self._latest_event().get("time")
        try:
            if raw_time is None:
                return None
            return dt_util.utc_from_timestamp(int(raw_time))
        except TypeError, ValueError:
            return None

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        event_dt = self._event_dt()
        if event_dt is None:
            return False

        return (dt_util.utcnow() - event_dt) <= self._WINDOW

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra attributes for the sensor."""
        latest = self._latest_event()
        if not latest:
            return None

        event_dt = self._event_dt()

        # "age" is nice for automations / debugging
        age_seconds: int | None = None
        if event_dt is not None:
            age_seconds = int((dt_util.utcnow() - event_dt).total_seconds())

        window_seconds = int(self._WINDOW.total_seconds())

        return {
            # raw fields from Yale
            "cid_code": latest.get("cid_code"),
            "report_id": latest.get("report_id"),
            "event_id": latest.get("id"),
            "utc_event_time": latest.get("utc_event_time"),
            "event_time": latest.get("event_time"),
            "time_raw": latest.get("time"),
            # derived / helpful fields
            "trigger_window_seconds": window_seconds,
            "event_datetime_utc": event_dt.isoformat() if event_dt else None,
            "event_age_seconds": age_seconds,
            "is_recent": age_seconds is not None and age_seconds <= window_seconds,
        }
