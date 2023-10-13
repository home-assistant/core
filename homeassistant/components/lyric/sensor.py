"""Support for Honeywell Lyric sensor platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiolyric import Lyric
from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation

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

from . import LyricDeviceEntity
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
class LyricSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[LyricDevice], StateType | datetime]
    suitable_fn: Callable[[LyricDevice], bool]


@dataclass
class LyricSensorEntityDescription(
    SensorEntityDescription, LyricSensorEntityDescriptionMixin
):
    """Class describing Honeywell Lyric sensor entities."""


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
        icon="mdi:thermostat",
        value_fn=lambda device: get_setpoint_status(
            device.changeableValues.thermostatSetpointStatus,
            device.changeableValues.nextPeriodTime,
        ),
        suitable_fn=lambda device: (
            device.changeableValues and device.changeableValues.thermostatSetpointStatus
        ),
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

    entities = []

    for location in coordinator.data.locations:
        for device in location.devices:
            for device_sensor in DEVICE_SENSORS:
                if device_sensor.suitable_fn(device):
                    entities.append(
                        LyricSensor(
                            coordinator,
                            device_sensor,
                            location,
                            device,
                        )
                    )

    async_add_entities(entities)


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
            if device.units == "Fahrenheit":
                self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
            else:
                self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state."""
        return self.entity_description.value_fn(self.device)
