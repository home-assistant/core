"""Support for Honeywell Lyric sensor platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
)
from homeassistant.core import HomeAssistant
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
class LyricSensorEntityDescription(SensorEntityDescription):
    """Class describing Honeywell Lyric sensor entities."""

    value: Callable[[LyricDevice], StateType] = round


def get_datetime_from_future_time(time: str) -> datetime:
    """Get datetime from future time provided."""
    time = dt_util.parse_time(time)
    now = dt_util.utcnow()
    if time <= now.time():
        now = now + timedelta(days=1)
    return dt_util.as_utc(datetime.combine(now.date(), time))


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Honeywell Lyric sensor platform based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    def get_setpoint_status(status: str, time: str) -> str:
        if status == PRESET_HOLD_UNTIL:
            return f"Held until {time}"
        return LYRIC_SETPOINT_STATUS_NAMES.get(status, None)

    for location in coordinator.data.locations:
        for device in location.devices:
            if device.indoorTemperature:
                entities.append(
                    LyricSensor(
                        coordinator,
                        LyricSensorEntityDescription(
                            key=f"{device.macID}_indoor_temperature",
                            name="Indoor Temperature",
                            device_class=DEVICE_CLASS_TEMPERATURE,
                            state_class=STATE_CLASS_MEASUREMENT,
                            native_unit_of_measurement=hass.config.units.temperature_unit,
                            value=lambda device: device.indoorTemperature,
                        ),
                        location,
                        device,
                    )
                )
            if device.outdoorTemperature:
                entities.append(
                    LyricSensor(
                        coordinator,
                        LyricSensorEntityDescription(
                            key=f"{device.macID}_outdoor_temperature",
                            name="Outdoor Temperature",
                            device_class=DEVICE_CLASS_TEMPERATURE,
                            state_class=STATE_CLASS_MEASUREMENT,
                            native_unit_of_measurement=hass.config.units.temperature_unit,
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
                            name="Outdoor Humidity",
                            device_class=DEVICE_CLASS_HUMIDITY,
                            state_class=STATE_CLASS_MEASUREMENT,
                            native_unit_of_measurement="%",
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
                                name="Next Period Time",
                                device_class=DEVICE_CLASS_TIMESTAMP,
                                value=lambda device: get_datetime_from_future_time(
                                    device.changeableValues.nextPeriodTime
                                ).isoformat(),
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
                                name="Setpoint Status",
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

    async_add_entities(entities, True)


class LyricSensor(LyricDeviceEntity, SensorEntity):
    """Define a Honeywell Lyric sensor."""

    coordinator: DataUpdateCoordinator
    entity_description: LyricSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
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
