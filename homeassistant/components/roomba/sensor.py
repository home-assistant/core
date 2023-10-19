"""Sensor for checking the battery level of Roomba."""
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BLID, DOMAIN, ROOMBA_SESSION
from .irobot_base import IRobotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iRobot Roomba vacuum cleaner."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    roomba = domain_data[ROOMBA_SESSION]
    blid = domain_data[BLID]

    roomba_vac = RoombaBattery(roomba, blid)
    roomba_battery_cycles = BatteryCycles(roomba, blid)
    roomba_cleaning_time = CleaningTime(roomba, blid)
    roomba_average_mission_time = AverageMissionTime(roomba, blid)
    roomba_total_missions = MissionSensor(roomba, blid, "total", "nMssn")
    roomba_success_missions = MissionSensor(roomba, blid, "successful", "nMssnOk")
    roomba_canceled_missions = MissionSensor(roomba, blid, "canceled", "nMssnC")
    roomba_failed_missions = MissionSensor(roomba, blid, "failed", "nMssnF")
    roomba_scrubs_count = ScrubsCount(roomba, blid)

    async_add_entities(
        [
            roomba_vac,
            roomba_battery_cycles,
            roomba_cleaning_time,
            roomba_average_mission_time,
            roomba_total_missions,
            roomba_success_missions,
            roomba_canceled_missions,
            roomba_failed_missions,
            roomba_scrubs_count,
        ],
    )


class RoombaBattery(IRobotEntity, SensorEntity):
    """Class to hold Roomba Sensor basic info."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"battery_{self._blid}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._battery_level


class BatteryCycles(IRobotEntity, SensorEntity):
    """Class to hold Roomba Sensor basic info."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:counter"

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Battery cycles"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"battery_cycles_{self._blid}"

    @property
    def state_class(self):
        """Return the state class of this entity, from STATE_CLASSES, if any."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._battery_stats.get("nLithChrg") or self._battery_stats.get(
            "nNimhChrg"
        )


class CleaningTime(IRobotEntity, SensorEntity):
    """Class to hold Roomba Sensor basic info."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clock"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} cleaning time total"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"total_cleaning_time_{self._blid}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._run_stats.get("hr")


class AverageMissionTime(IRobotEntity, SensorEntity):
    """Class to hold Roomba Sensor basic info."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clock"

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Average mission time"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"average_mission_time_{self._blid}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return UnitOfTime.MINUTES

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._mission_stats.get("aMssnM")


class MissionSensor(IRobotEntity, SensorEntity):
    """Class to hold the Roomba missions info."""

    def __init__(self, roomba, blid, mission_type, mission_value_string):
        """Initialise iRobot sensor with mission details."""
        super().__init__(roomba, blid)
        self._mission_type = mission_type
        self._mission_value_string = mission_value_string

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:counter"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Missions {self._mission_type}"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"{self._mission_type}_missions_{self._blid}"

    @property
    def state_class(self):
        """Return the state class of this entity, from STATE_CLASSES, if any."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._mission_stats.get(self._mission_value_string)


class ScrubsCount(IRobotEntity, SensorEntity):
    """Class to hold Roomba Sensor basic info."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:counter"

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Scrubs count"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"scrubs_count_{self._blid}"

    @property
    def state_class(self):
        """Return the state class of this entity, from STATE_CLASSES, if any."""
        return SensorStateClass.MEASUREMENT

    @property
    def entity_registry_enabled_default(self):
        """Disable sensor by default."""
        return False

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._run_stats.get("nScrubs")
