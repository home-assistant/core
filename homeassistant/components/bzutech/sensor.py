"""Sensor for BZUTech integration."""
from datetime import date, datetime, timedelta  # noqa: D100
from decimal import Decimal
import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import BzuCloudCoordinator
from .const import CONF_CHIPID, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Do entry Setup."""
    coordinator: BzuCloudCoordinator = hass.data[DOMAIN][entry.entry_id]
    sensors = [BzuEntity(coordinator, entry)]
    async_add_entities(sensors, update_before_add=True)


tipos_sensores = {
    "TMP": SensorDeviceClass.TEMPERATURE,
    "HUM": SensorDeviceClass.HUMIDITY,
    "VOT": SensorDeviceClass.VOLTAGE,
    "CO2": SensorDeviceClass.CO2,
    "CUR": SensorDeviceClass.CURRENT,
    "LUM": SensorDeviceClass.ILLUMINANCE,
    "PIR": SensorDeviceClass.AQI,
    "DOOR": SensorDeviceClass.AQI,
    "DOR": SensorDeviceClass.AQI,
    "M10": SensorDeviceClass.PM10,
    "M25": SensorDeviceClass.PM25,
    "M40": SensorDeviceClass.PM10,
    "SND": SensorDeviceClass.SOUND_PRESSURE,
    "M01": SensorDeviceClass.PM1,
    "C01": SensorDeviceClass.CO,
    "VOC": SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
    "DOS": SensorDeviceClass.AQI,
    "VOA": SensorDeviceClass.VOLTAGE,
    "VOB": SensorDeviceClass.VOLTAGE,
    "CRA": SensorDeviceClass.CURRENT,
    "CRB": SensorDeviceClass.CURRENT,
    "CRC": SensorDeviceClass.CURRENT,
    "VRA": SensorDeviceClass.VOLTAGE,
    "VRB": SensorDeviceClass.VOLTAGE,
    "VRC": SensorDeviceClass.VOLTAGE,
    "C05": SensorDeviceClass.AQI,
    "C25": SensorDeviceClass.PM25,
    "C40": SensorDeviceClass.PM10,
    "C10": SensorDeviceClass.PM10,
    "BAT": SensorDeviceClass.BATTERY,
    "DBM": SensorDeviceClass.SIGNAL_STRENGTH,
    "MEM": SensorDeviceClass.DATA_SIZE,
    "UPT": SensorDeviceClass.DATA_SIZE,
}
units = {
    "TMP": UnitOfTemperature.CELSIUS,
    "HUM": PERCENTAGE,
    "VOT": UnitOfElectricPotential.VOLT,
    "CO2": CONCENTRATION_PARTS_PER_MILLION,
    "CUR": UnitOfElectricCurrent.AMPERE,
    "LUM": LIGHT_LUX,
    "PIR": None,
    "DOOR": None,
    "DOR": None,
    "M10": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "M25": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "M40": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "SND": SensorDeviceClass.SOUND_PRESSURE,
    "M01": CONCENTRATION_PARTS_PER_MILLION,
    "C01": CONCENTRATION_PARTS_PER_MILLION,
    "VOC": CONCENTRATION_PARTS_PER_MILLION,
    "DOS": None,
    "VOA": UnitOfElectricPotential.VOLT,
    "VOB": UnitOfElectricPotential.VOLT,
    "CRA": UnitOfElectricCurrent.AMPERE,
    "CRB": UnitOfElectricCurrent.AMPERE,
    "CRC": UnitOfElectricCurrent.AMPERE,
    "VRA": UnitOfElectricPotential.VOLT,
    "VRB": UnitOfElectricPotential.VOLT,
    "VRC": UnitOfElectricPotential.VOLT,
    "C05": None,
    "C25": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "C40": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "C10": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "BAT": PERCENTAGE,
    "DBM": SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    "MEM": UnitOfInformation.KIBIBYTES,
    "UPT": UnitOfTime.MILLISECONDS,
}


class BzuCoordinator(DataUpdateCoordinator):
    """setup entity coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        cloudcoordinator: BzuCloudCoordinator,
    ) -> None:
        """Do setup coordinator."""

        super().__init__(
            hass,
            logging.getLogger("bzutech"),
            name="bzutech",
            update_interval=timedelta(seconds=30),
        )
        self.myapi = cloudcoordinator
        self.data = None


class BzuEntity(CoordinatorEntity, SensorEntity):
    """Setup sensor entity."""

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Do Sensor configuration."""
        super().__init__(coordinator)
        self._attr_name = (
            str(entry.data[CONF_CHIPID])
            + "-"
            + entry.data["sensorname"].split("-")[1]
            + "-"
            + str(entry.data["sensorport"])
        )
        self.chipid = entry.data[CONF_CHIPID]
        self._attr_state_class = "measurement"
        self._attr_device_class = SensorDeviceClass(
            tipos_sensores[entry.data["sensorname"].split("-")[1]]
        )
        self._attr_native_unit_of_measurement = units[
            entry.data["sensorname"].split("-")[1]
        ]
        self._attr_unique_id = self._attr_name
        self._attr_is_on = True

    @property
    def device_info(self) -> DeviceInfo | None:
        """Setting basic device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, "ESP-" + self.chipid)},
            suggested_area="Room",
            name="Gateway " + self.chipid,
            entry_type=DeviceEntryType("service"),
            manufacturer="BZU Tecnologia",
            hw_version="1.0",
            model="ESP-" + self.chipid,
            serial_number=self.chipid,
            sw_version="1.0",
        )
        # return super().device_info

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return sensor value."""
        self._attr_native_value = self.coordinator.fetch_data()
        return super().native_value
