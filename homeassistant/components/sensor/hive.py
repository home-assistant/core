"""
Support for the Hive devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.hive/
"""
from homeassistant.const import TEMP_CELSIUS
from homeassistant.components.hive import DATA_HIVE
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['hive']

FRIENDLY_NAMES = {'Hub_OnlineStatus': 'Hub Status',
                  'Hive_OutsideTemperature': 'Outside Temperature'}
DEVICETYPE_ICONS = {'Hub_OnlineStatus': 'mdi:switch',
                    'Hive_OutsideTemperature': 'mdi:thermometer'}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Hive sensor devices."""
    if discovery_info is None:
        return
    session = hass.data.get(DATA_HIVE)

    if (discovery_info["HA_DeviceType"] == "Hub_OnlineStatus" or
            discovery_info["HA_DeviceType"] == "Hive_OutsideTemperature"):
        add_devices([HiveSensorEntity(session, discovery_info)])


class HiveSensorEntity(Entity):
    """Hive Sensor Entity."""

    def __init__(self, hivesession, hivedevice):
        """Initialize the sensor."""
        self.node_id = hivedevice["Hive_NodeID"]
        self.device_type = hivedevice["HA_DeviceType"]
        self.node_device_type = hivedevice["Hive_DeviceType"]
        self.session = hivesession
        self.data_updatesource = '{}.{}'.format(self.device_type,
                                                self.node_id)
        self.session.entities.append(self)

    def handle_update(self, updatesource):
        """Handle the new update request."""
        if '{}.{}'.format(self.device_type, self.node_id) not in updatesource:
            self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the sensor."""
        return FRIENDLY_NAMES.get(self.device_type)

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.device_type == "Hub_OnlineStatus":
            return self.session.sensor.hub_online_status(self.node_id)
        elif self.device_type == "Hive_OutsideTemperature":
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
        if self.session.core.update_data(self.node_id):
            for entity in self.session.entities:
                entity.handle_update(self.data_updatesource)
