"""Support for Honeywell Lyric sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiolyric import Lyric
from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation
from aiolyric.objects.priority import LyricRoom

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import LyricDeviceEntity, LyricRoomEntity
from .const import (
    DOMAIN,
    PRESET_HOLD_UNTIL,
    PRESET_NO_HOLD,
    PRESET_PERMANENT_HOLD,
    PRESET_TEMPORARY_HOLD,
    PRESET_VACATION_HOLD,
)

LYRIC_SETPOINT_STATUS_NAMES = {
    PRESET_NO_HOLD: "Following Schedule",
    PRESET_PERMANENT_HOLD: "Held Permanently",
    PRESET_TEMPORARY_HOLD: "Held Temporarily",
    PRESET_VACATION_HOLD: "Holiday",
}


@dataclass(frozen=True, kw_only=True)
class LyricSensorEntityDescription(SensorEntityDescription):
    """Class describing Honeywell Lyric sensor entities."""

    value_fn: Callable[[LyricDevice], StateType | datetime]
    suitable_fn: Callable[[LyricDevice], bool]


DEVICE_SENSORS: list[LyricSensorEntityDescription] = [
    LyricSensorEntityDescription(
        key="indoor_temperature",
        translation_key="indoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.indoorTemperature,
        suitable_fn=lambda device: device.indoorTemperature,
    ),
    LyricSensorEntityDescription(
        key="indoor_humidity",
        translation_key="indoor_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.indoorHumidity,
        suitable_fn=lambda device: device.indoorHumidity,
    ),
    LyricSensorEntityDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.outdoorTemperature,
        suitable_fn=lambda device: device.outdoorTemperature,
    ),
    LyricSensorEntityDescription(
        key="outdoor_humidity",
        translation_key="outdoor_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.displayedOutdoorHumidity,
        suitable_fn=lambda device: device.displayedOutdoorHumidity,
    ),
    LyricSensorEntityDescription(
        key="next_period_time",
        translation_key="next_period_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda device: get_datetime_from_future_time(
            device.changeableValues.nextPeriodTime
        ),
        suitable_fn=lambda device: (
            device.changeableValues and device.changeableValues.nextPeriodTime
        ),
    ),
    LyricSensorEntityDescription(
        key="setpoint_status",
        translation_key="setpoint_status",
        value_fn=lambda device: get_setpoint_status(
            device.changeableValues.thermostatSetpointStatus,
            device.changeableValues.nextPeriodTime,
        ),
        suitable_fn=lambda device: (
            device.changeableValues and device.changeableValues.thermostatSetpointStatus
        ),
    ),
]


@dataclass(frozen=True)
class LyricRoomSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[LyricRoom], StateType]
    suitable_fn: Callable[[LyricRoom], bool]


@dataclass(frozen=True)
class LyricRoomSensorEntityDescription(
    SensorEntityDescription, LyricRoomSensorEntityDescriptionMixin
):
    """Class describing Honeywell Lyric room sensor entities."""


ROOM_SENSORS = [
    LyricRoomSensorEntityDescription(
        key="avg_temperature",
        translation_key="avg_temperature",
        name="average temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda room: round(room.roomAvgTemp, 1),
        suitable_fn=lambda room: room.roomAvgTemp is not None,
    ),
    LyricRoomSensorEntityDescription(
        key="avg_humidity",
        translation_key="avg_humidity",
        name="average humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda room: round(room.roomAvgHumidity, 1),
        suitable_fn=lambda room: room.roomAvgHumidity is not None,
    ),
]


def get_setpoint_status(status: str, time: str) -> str | None:
    """Get status of the setpoint."""
    if status == PRESET_HOLD_UNTIL:
        return f"Held until {time}"
    return LYRIC_SETPOINT_STATUS_NAMES.get(status)


def get_datetime_from_future_time(time_str: str) -> datetime:
    """Get datetime from future time provided."""
    time = dt_util.parse_time(time_str)
    if time is None:
        raise ValueError(f"Unable to parse time {time_str}")
    now = dt_util.utcnow()
    if time <= now.time():
        now = now + timedelta(days=1)
    return dt_util.as_utc(datetime.combine(now.date(), time))


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Honeywell Lyric sensor platform based on a config entry."""
    coordinator: DataUpdateCoordinator[Lyric] = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        LyricSensor(
            coordinator,
            device_sensor,
            location,
            device,
        )
        for location in coordinator.data.locations
        for device in location.devices
        for device_sensor in DEVICE_SENSORS
        if device_sensor.suitable_fn(device)
    )

    async_add_entities(
        LyricRoomSensor(
            coordinator,
            room_sensor,
            location,
            device,
            room,
        )
        for location in coordinator.data.locations
        for device in location.devices
        for room in coordinator.data.rooms_dict[device.macID].values()
        for room_sensor in ROOM_SENSORS
        if room_sensor.suitable_fn(room)
    )


class LyricSensor(LyricDeviceEntity, SensorEntity):
    """Define a Honeywell Lyric sensor."""

    entity_description: LyricSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Lyric],
        description: LyricSensorEntityDescription,
        location: LyricLocation,
        device: LyricDevice,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            location,
            device,
            f"{device.macID}_{description.key}",
        )
        self.entity_description = description
        if description.device_class == SensorDeviceClass.TEMPERATURE:
            self._attr_native_unit_of_measurement = _get_lyric_device_temperature_units(
                device
            )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state."""
        return self.entity_description.value_fn(self.device)


def _get_lyric_device_temperature_units(device: LyricDevice) -> UnitOfTemperature:
    return (
        UnitOfTemperature.FAHRENHEIT
        if device.units == "Fahrenheit"
        else UnitOfTemperature.CELSIUS
    )


class LyricRoomSensor(LyricRoomEntity, SensorEntity):
    """Define a Honeywell Lyric room sensor."""

    entity_description: LyricRoomSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Lyric],
        description: LyricRoomSensorEntityDescription,
        location: LyricLocation,
        device: LyricDevice,
        room: LyricRoom,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            location,
            device,
            room,
            f"{device.macID}_room_{room.id}_{description.key}",
        )
        self.entity_description = description
        room_name = room.roomName or f"Room {room.id}"
        self._attr_name = f"{room_name} {description.name}"
        if description.device_class == SensorDeviceClass.TEMPERATURE:
            self._attr_native_unit_of_measurement = _get_lyric_device_temperature_units(
                device
            )

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.entity_description.value_fn(self.room)
