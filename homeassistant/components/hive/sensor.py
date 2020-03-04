"""Support for the Hive sensors."""
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

from . import DATA_HIVE, DOMAIN, HiveEntity

FRIENDLY_NAMES = {
    "Hub_OnlineStatus": "Hive Hub Status",
    "Hive_OutsideTemperature": "Outside Temperature",
}

DEVICETYPE_ICONS = {
    "Hub_OnlineStatus": "mdi:switch",
    "Hive_OutsideTemperature": "mdi:thermometer",
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Hive sensor devices."""
    if discovery_info is None:
        return

    session = hass.data.get(DATA_HIVE)
    devs = []
    for dev in discovery_info:
        if dev["HA_DeviceType"] in FRIENDLY_NAMES:
            devs.append(HiveSensorEntity(session, dev))
    add_entities(devs)


class HiveSensorEntity(HiveEntity, Entity):
    """Hive Sensor Entity."""

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        return {"identifiers": {(DOMAIN, self.unique_id)}, "name": self.name}

    @property
    def name(self):
        """Return the name of the sensor."""
        return FRIENDLY_NAMES.get(self.device_type)

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.device_type == "Hub_OnlineStatus":
            return self.session.sensor.hub_online_status(self.node_id)
        if self.device_type == "Hive_OutsideTemperature":
            return self.session.weather.temperature()

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.device_type == "Hive_OutsideTemperature":
            return TEMP_CELSIUS

    @property
    def icon(self):
        """Return the icon to use."""
        return DEVICETYPE_ICONS.get(self.device_type)

    def update(self):
        """Update all Node data from Hive."""
        self.session.core.update_data(self.node_id)
