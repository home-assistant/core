"""Support for OSO Energy sensors."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENERGY_KILO_WATT_HOUR, POWER_KILO_WATT, VOLUME_LITERS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OSOEnergyEntity
from .const import DOMAIN, MANUFACTURER, SENSOR, STATUS

DEVICETYPE = {
    "POWER_SAVE": {"unit": STATUS, "type": SENSOR, "postfix": "Power Save"},
    "EXTRA_ENERGY": {"unit": STATUS, "type": SENSOR, "postfix": "Extra Energy"},
    "POWER_LOAD": {"unit": POWER_KILO_WATT, "type": SENSOR, "postfix": "Power Load"},
    "TAPPING_CAPACITY_KWH": {
        "unit": ENERGY_KILO_WATT_HOUR,
        "type": SENSOR,
        "postfix": "Tapping Capacity kWh",
    },
    "CAPACITY_MIXED_WATER_40": {
        "unit": VOLUME_LITERS,
        "type": SENSOR,
        "postfix": "Capacity Mixed Water 40",
    },
    "V40_MIN": {"unit": VOLUME_LITERS, "type": SENSOR, "postfix": "V40 Min"},
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OSO Energy sensor."""
    osoenergy = hass.data[DOMAIN][entry.entry_id]
    devices = osoenergy.session.device_list.get("sensor", [])
    entities = []
    if devices:
        for dev in devices:
            entities.append(OSOEnergySensor(osoenergy, dev))
    async_add_entities(entities, True)


class OSOEnergySensor(OSOEnergyEntity, SensorEntity):
    """OSO Energy Sensor Entity."""

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        postfix = DEVICETYPE[self.device["osoEnergyType"]].get("postfix")
        return f"{self._unique_id} {postfix}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device["device_id"])},
            manufacturer=MANUFACTURER,
            model=self.device["device_type"],
            name=self.device["device_name"],
        )

    @property
    def available(self):
        """Return if the device is available."""
        return self.device.get("available", False)

    @property
    def device_class(self):
        """Device class of the entity."""
        return DEVICETYPE[self.device["osoEnergyType"]].get("type")

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return DEVICETYPE[self.device["osoEnergyType"]].get("unit")

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.device["haName"]

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.device["status"]["state"]

    async def async_update(self):
        """Update all data for OSO Energy."""
        await self.osoenergy.session.update_data()
        self.device = await self.osoenergy.sensor.get_sensor(self.device)
