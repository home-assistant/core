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
    async_add_entities([roomba_vac], True)


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
