"""Support for Honeywell Lyric sensor platform."""
from datetime import datetime, timedelta

from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
)
from homeassistant.core import HomeAssistant
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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Honeywell Lyric sensor platform based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    for location in coordinator.data.locations:
        for device in location.devices:
            cls_list = []
            if device.indoorTemperature:
                cls_list.append(LyricIndoorTemperatureSensor)
            if device.outdoorTemperature:
                cls_list.append(LyricOutdoorTemperatureSensor)
            if device.displayedOutdoorHumidity:
                cls_list.append(LyricOutdoorHumiditySensor)
            if device.changeableValues:
                if device.changeableValues.nextPeriodTime:
                    cls_list.append(LyricNextPeriodSensor)
                if device.changeableValues.thermostatSetpointStatus:
                    cls_list.append(LyricSetpointStatusSensor)
            for cls in cls_list:
                entities.append(
                    cls(
                        coordinator,
                        location,
                        device,
                        hass.config.units.temperature_unit,
                    )
                )

    async_add_entities(entities, True)


class LyricSensor(LyricDeviceEntity, SensorEntity):
    """Defines a Honeywell Lyric sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
        key: str,
        name: str,
        icon: str,
        device_class: str = None,
        unit_of_measurement: str = None,
    ) -> None:
        """Initialize Honeywell Lyric sensor."""
        self._device_class = device_class
        self._unit_of_measurement = unit_of_measurement

        super().__init__(coordinator, location, device, key, name, icon)

    @property
    def device_class(self) -> str:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class LyricIndoorTemperatureSensor(LyricSensor):
    """Defines a Honeywell Lyric sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
        unit_of_measurement: str = None,
    ) -> None:
        """Initialize Honeywell Lyric sensor."""

        super().__init__(
            coordinator,
            location,
            device,
            f"{device.macID}_indoor_temperature",
            "Indoor Temperature",
            None,
            DEVICE_CLASS_TEMPERATURE,
            unit_of_measurement,
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self.device.indoorTemperature


class LyricOutdoorTemperatureSensor(LyricSensor):
    """Defines a Honeywell Lyric sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
        unit_of_measurement: str = None,
    ) -> None:
        """Initialize Honeywell Lyric sensor."""

        super().__init__(
            coordinator,
            location,
            device,
            f"{device.macID}_outdoor_temperature",
            "Outdoor Temperature",
            None,
            DEVICE_CLASS_TEMPERATURE,
            unit_of_measurement,
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self.device.outdoorTemperature


class LyricOutdoorHumiditySensor(LyricSensor):
    """Defines a Honeywell Lyric sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
        unit_of_measurement: str = None,
    ) -> None:
        """Initialize Honeywell Lyric sensor."""

        super().__init__(
            coordinator,
            location,
            device,
            f"{device.macID}_outdoor_humidity",
            "Outdoor Humidity",
            None,
            DEVICE_CLASS_HUMIDITY,
            "%",
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self.device.displayedOutdoorHumidity


class LyricNextPeriodSensor(LyricSensor):
    """Defines a Honeywell Lyric sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
        unit_of_measurement: str = None,
    ) -> None:
        """Initialize Honeywell Lyric sensor."""

        super().__init__(
            coordinator,
            location,
            device,
            f"{device.macID}_next_period_time",
            "Next Period Time",
            None,
            DEVICE_CLASS_TIMESTAMP,
        )

    @property
    def state(self) -> datetime:
        """Return the state of the sensor."""
        device = self.device
        time = dt_util.parse_time(device.changeableValues.nextPeriodTime)
        now = dt_util.utcnow()
        if time <= now.time():
            now = now + timedelta(days=1)
        return dt_util.as_utc(datetime.combine(now.date(), time))


class LyricSetpointStatusSensor(LyricSensor):
    """Defines a Honeywell Lyric sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
        unit_of_measurement: str = None,
    ) -> None:
        """Initialize Honeywell Lyric sensor."""

        super().__init__(
            coordinator,
            location,
            device,
            f"{device.macID}_setpoint_status",
            "Setpoint Status",
            "mdi:thermostat",
            None,
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        device = self.device
        if device.changeableValues.thermostatSetpointStatus == PRESET_HOLD_UNTIL:
            return f"Held until {device.changeableValues.nextPeriodTime}"
        return LYRIC_SETPOINT_STATUS_NAMES.get(
            device.changeableValues.thermostatSetpointStatus, "Unknown"
        )
