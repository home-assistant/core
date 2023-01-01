"""Sensor for checking the battery level of Roomba."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
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
    roomba_cleaning_time = CleaningTime(roomba, blid)
    roomba_total_missions = TotalMissions(roomba, blid)
    roomba_success_missions = SuccessMissions(roomba, blid)
    roomba_cancelled_missions = CancelledMissions(roomba, blid)
    roomba_failed_missions = FailedMissions(roomba, blid)
    roomba_scrubs_count = ScrubsCount(roomba, blid)
    async_add_entities(
        [
            roomba_vac,
            roomba_cleaning_time,
            roomba_total_missions,
            roomba_success_missions,
            roomba_cancelled_missions,
            roomba_failed_missions,
            roomba_scrubs_count,
        ],
        True,
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


class CleaningTime(IRobotEntity, SensorEntity):
    """Class to hold Roomba Sensor basic info."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} total cleaning time"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"total_cleaning_time_{self._blid}"

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SensorDeviceClass.DURATION

    @property
    def native_unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return "hours"

    @property
    def icon(self):
        """Return the icon for the cleaning time."""
        return "mdi:clock"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        hours = self._run_stats.get("hr")
        # minutes = self._cleaning_time.get("min")

        # minutes_total = minutes + (hours * 60)

        return hours


class TotalMissions(IRobotEntity, SensorEntity):
    """Class to hold Roomba Sensor basic info."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} missions total"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"total_missions_{self._blid}"

    @property
    def icon(self):
        """Return the counter icon."""
        return "mdi:counter"

    @property
    def native_unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return ""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._mission_stats.get("nMssn")


class SuccessMissions(IRobotEntity, SensorEntity):
    """Class to hold Roomba Sensor basic info."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} missions successful"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"successful_missions_{self._blid}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return ""

    @property
    def icon(self):
        """Return the counter icon."""
        return "mdi:counter"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._mission_stats.get("nMssnOk")


class CancelledMissions(IRobotEntity, SensorEntity):
    """Class to hold Roomba Sensor basic info."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} missions cancelled"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"cancelled_missions_{self._blid}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return ""

    @property
    def icon(self):
        """Return the counter icon."""
        return "mdi:counter"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._mission_stats.get("nMssnC")


class FailedMissions(IRobotEntity, SensorEntity):
    """Class to hold Roomba Sensor basic info."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} missions failed"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"failed_missions_{self._blid}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return ""

    @property
    def icon(self):
        """Return the counter icon."""
        return "mdi:counter"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._mission_stats.get("nMssnF")


class ScrubsCount(IRobotEntity, SensorEntity):
    """Class to hold Roomba Sensor basic info."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} scrubs count"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"scrubs_count_{self._blid}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return ""

    @property
    def icon(self):
        """Return the counter icon."""
        return "mdi:counter"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._run_stats.get("nScrubs")
