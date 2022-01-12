"""Sensor for checking the battery level of Roomba."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.components.vacuum import STATE_DOCKED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level

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
    async_add_entities([roomba_vac], True)


class RoombaBattery(IRobotEntity, SensorEntity):
    """Class to hold Roomba Sensor basic info."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} Battery Level"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"battery_{self._blid}"

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SensorDeviceClass.BATTERY

    @property
    def native_unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return PERCENTAGE

    @property
    def icon(self):
        """Return the icon for the battery."""
        charging = bool(self._robot_state == STATE_DOCKED)

        return icon_for_battery_level(
            battery_level=self._battery_level, charging=charging
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._battery_level
