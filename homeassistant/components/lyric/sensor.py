"""Support for Honeywell Lyric sensor platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

from aiolyric import Lyric
from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation
from aiolyric.objects.priority import LyricRoom

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
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


@dataclass
class LyricSensorEntityDescription(SensorEntityDescription):
    """Class describing Honeywell Lyric sensor entities."""

    value: Callable[[LyricDevice], StateType | datetime] = round


@dataclass
class LyricRoomSensorEntityDescription(SensorEntityDescription):
    """Class describing Honeywell Lyric sensor entities."""

    value: Callable[[LyricRoom], StateType | datetime] = round


@dataclass
class LyricRoomBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Honeywell Lyric sensor entities."""

    is_on: Callable[[LyricRoom], StateType | datetime] = round


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

    entities: list[Entity] = []

    def get_setpoint_status(status: str, time: str) -> str | None:
        if status == PRESET_HOLD_UNTIL:
            return f"Held until {time}"
        return LYRIC_SETPOINT_STATUS_NAMES.get(status, None)

    for location in coordinator.data.locations:
        for device in location.devices:
            if device.indoorTemperature:
                if device.units == "Fahrenheit":
                    native_temperature_unit = UnitOfTemperature.FAHRENHEIT
                else:
                    native_temperature_unit = UnitOfTemperature.CELSIUS

                entities.append(
                    LyricSensor(
                        coordinator,
                        LyricSensorEntityDescription(
                            key=f"{device.macID}_indoor_temperature",
                            translation_key="indoor_temperature",
                            device_class=SensorDeviceClass.TEMPERATURE,
                            state_class=SensorStateClass.MEASUREMENT,
                            native_unit_of_measurement=native_temperature_unit,
                            value=lambda device: device.indoorTemperature,
                        ),
                        location,
                        device,
                    )
                )
            if device.indoorHumidity:
                entities.append(
                    LyricSensor(
                        coordinator,
                        LyricSensorEntityDescription(
                            key=f"{device.macID}_indoor_humidity",
                            translation_key="indoor_humidity",
                            device_class=SensorDeviceClass.HUMIDITY,
                            state_class=SensorStateClass.MEASUREMENT,
                            native_unit_of_measurement=PERCENTAGE,
                            value=lambda device: device.indoorHumidity,
                        ),
                        location,
                        device,
                    )
                )

            if device.outdoorTemperature:
                if device.units == "Fahrenheit":
                    native_temperature_unit = UnitOfTemperature.FAHRENHEIT
                else:
                    native_temperature_unit = UnitOfTemperature.CELSIUS

                entities.append(
                    LyricSensor(
                        coordinator,
                        LyricSensorEntityDescription(
                            key=f"{device.macID}_outdoor_temperature",
                            translation_key="outdoor_temperature",
                            device_class=SensorDeviceClass.TEMPERATURE,
                            state_class=SensorStateClass.MEASUREMENT,
                            native_unit_of_measurement=native_temperature_unit,
                            value=lambda device: device.outdoorTemperature,
                        ),
                        location,
                        device,
                    )
                )
            if device.displayedOutdoorHumidity:
                entities.append(
                    LyricSensor(
                        coordinator,
                        LyricSensorEntityDescription(
                            key=f"{device.macID}_outdoor_humidity",
                            translation_key="outdoor_humidity",
                            device_class=SensorDeviceClass.HUMIDITY,
                            state_class=SensorStateClass.MEASUREMENT,
                            native_unit_of_measurement=PERCENTAGE,
                            value=lambda device: device.displayedOutdoorHumidity,
                        ),
                        location,
                        device,
                    )
                )
            if device.changeableValues:
                if device.changeableValues.nextPeriodTime:
                    entities.append(
                        LyricSensor(
                            coordinator,
                            LyricSensorEntityDescription(
                                key=f"{device.macID}_next_period_time",
                                translation_key="next_period_time",
                                device_class=SensorDeviceClass.TIMESTAMP,
                                value=lambda device: get_datetime_from_future_time(
                                    device.changeableValues.nextPeriodTime
                                ),
                            ),
                            location,
                            device,
                        )
                    )
                if device.changeableValues.thermostatSetpointStatus:
                    entities.append(
                        LyricSensor(
                            coordinator,
                            LyricSensorEntityDescription(
                                key=f"{device.macID}_setpoint_status",
                                translation_key="setpoint_status",
                                icon="mdi:thermostat",
                                value=lambda device: get_setpoint_status(
                                    device.changeableValues.thermostatSetpointStatus,
                                    device.changeableValues.nextPeriodTime,
                                ),
                            ),
                            location,
                            device,
                        )
                    )

            if device.macID in coordinator.data.rooms_dict:
                for room in coordinator.data.rooms_dict[device.macID].values():
                    if hasattr(room, "roomAvgTemp"):
                        entities.append(
                            LyricRoomSensor(
                                coordinator,
                                LyricRoomSensorEntityDescription(
                                    key=f"{device.macID}_room{room.id}_temperature",
                                    name=f"{room.roomName} Average Temperature",
                                    device_class=SensorDeviceClass.TEMPERATURE,
                                    state_class=SensorStateClass.MEASUREMENT,
                                    native_unit_of_measurement=hass.config.units.temperature_unit,
                                    value=lambda room: room.roomAvgTemp,
                                ),
                                location,
                                device,
                                room,
                            )
                        )
                    if hasattr(room, "roomAvgHumidity"):
                        entities.append(
                            LyricRoomSensor(
                                coordinator,
                                LyricRoomSensorEntityDescription(
                                    key=f"{device.macID}_room{room.id}_humidity",
                                    name=f"{room.roomName} Average Humidity",
                                    device_class=SensorDeviceClass.HUMIDITY,
                                    state_class=SensorStateClass.MEASUREMENT,
                                    native_unit_of_measurement=PERCENTAGE,
                                    value=lambda room: room.roomAvgHumidity,
                                ),
                                location,
                                device,
                                room,
                            )
                        )
                    if hasattr(room, "overallMotion"):
                        entities.append(
                            LyricRoomBinarySensor(
                                coordinator,
                                LyricRoomBinarySensorEntityDescription(
                                    key=f"{device.macID}_room{room.id}_motion",
                                    name=f"{room.roomName} Overall Motion",
                                    device_class=BinarySensorDeviceClass.MOTION,
                                    is_on=lambda room: room.overallMotion,
                                ),
                                location,
                                device,
                                room,
                            )
                        )

    async_add_entities(entities, True)


class LyricSensor(LyricDeviceEntity, SensorEntity):
    """Define a Honeywell Lyric sensor."""

    coordinator: DataUpdateCoordinator[Lyric]
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
            description.key,
        )
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        device: LyricDevice = self.device
        try:
            return cast(StateType, self.entity_description.value(device))
        except TypeError:
            return None


class LyricRoomSensor(LyricRoomEntity, SensorEntity):
    """Define a Honeywell Lyric sensor."""

    coordinator: DataUpdateCoordinator[Lyric]
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
            description.key,
        )
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        room: LyricRoom = self.room
        try:
            return cast(StateType, self.entity_description.value(room))
        except TypeError:
            return None


class LyricRoomBinarySensor(LyricRoomEntity, BinarySensorEntity):
    """Define a Honeywell Lyric sensor."""

    coordinator: DataUpdateCoordinator[Lyric]
    entity_description: LyricRoomBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Lyric],
        description: LyricRoomBinarySensorEntityDescription,
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
            description.key,
        )
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the state."""
        room: LyricRoom = self.room
        try:
            return cast(bool, self.entity_description.is_on(room))
        except TypeError:
            return None
