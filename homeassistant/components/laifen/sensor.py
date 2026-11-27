"""Sensor platform for the Laifen integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import override

from laifen_ble import LaifenToothbrush

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .coordinator import LaifenConfigEntry
from .entity import LaifenEntity

PARALLEL_UPDATES = 0

CURRENT_DURATION_INTERVAL = timedelta(seconds=1)


@dataclass(frozen=True, kw_only=True)
class LaifenSensorEntityDescription(SensorEntityDescription):
    """Describes a Laifen sensor."""

    value_fn: Callable[[LaifenToothbrush], int | None]


SENSORS: tuple[LaifenSensorEntityDescription, ...] = (
    LaifenSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda toothbrush: (
            toothbrush.state.battery_level if toothbrush.state else None
        ),
    ),
    LaifenSensorEntityDescription(
        key="last_brushing_duration",
        translation_key="last_brushing_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        value_fn=lambda toothbrush: (
            toothbrush.last_session.duration if toothbrush.last_session else None
        ),
    ),
)

CURRENT_BRUSHING_DURATION = SensorEntityDescription(
    key="current_brushing_duration",
    translation_key="current_brushing_duration",
    device_class=SensorDeviceClass.DURATION,
    native_unit_of_measurement=UnitOfTime.SECONDS,
    suggested_display_precision=0,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaifenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Laifen sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            *(LaifenSensor(coordinator, description) for description in SENSORS),
            LaifenCurrentBrushingDurationSensor(coordinator, CURRENT_BRUSHING_DURATION),
        ]
    )


class LaifenSensor(LaifenEntity, RestoreSensor):
    """A Laifen sensor that keeps its last value while the toothbrush sleeps."""

    entity_description: LaifenSensorEntityDescription

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last value."""
        await super().async_added_to_hass()
        if (last_sensor_data := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = last_sensor_data.native_value
        self._update_native_value()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the toothbrush."""
        self._update_native_value()
        super()._handle_coordinator_update()

    def _update_native_value(self) -> None:
        """Update the value from the toothbrush."""
        if (value := self.entity_description.value_fn(self.toothbrush)) is not None:
            self._attr_native_value = value

    @property
    @override
    def available(self) -> bool:
        """Return whether the sensor is available."""
        return super().available and (
            self.toothbrush.connected or self.native_value is not None
        )


class LaifenCurrentBrushingDurationSensor(LaifenEntity, SensorEntity):
    """The duration of the brushing session in progress, updated every second."""

    _unsubscribe_interval: CALLBACK_TYPE | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Start following a session that is already in progress."""
        await super().async_added_to_hass()
        self.async_on_remove(self._async_stop_interval)
        self._async_update_interval()
        self._update_native_value()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the toothbrush."""
        self._async_update_interval()
        self._update_native_value()
        super()._handle_coordinator_update()

    @callback
    def _async_update_interval(self) -> None:
        """Update the duration every second while the motor runs."""
        state = self.toothbrush.state
        if self.toothbrush.connected and state is not None and state.running:
            if self._unsubscribe_interval is None:
                self._unsubscribe_interval = async_track_time_interval(
                    self.hass, self._async_handle_interval, CURRENT_DURATION_INTERVAL
                )
        else:
            self._async_stop_interval()

    @callback
    def _async_stop_interval(self) -> None:
        """Stop updating the duration."""
        if self._unsubscribe_interval is not None:
            self._unsubscribe_interval()
            self._unsubscribe_interval = None

    @callback
    def _async_handle_interval(self, now: datetime) -> None:
        """Update the duration of the session in progress."""
        self._update_native_value()
        self.async_write_ha_state()

    def _update_native_value(self) -> None:
        """Update the value from the toothbrush."""
        session = self.toothbrush.current_session
        self._attr_native_value = session.duration if session else 0
