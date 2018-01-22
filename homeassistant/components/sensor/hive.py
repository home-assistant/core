"""
Support for the Hive devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.hive/
"""
from homeassistant.components.hive import DATA_HIVE
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['hive']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Hive sensor devices."""
    if discovery_info is None:
        return
    session = hass.data.get(DATA_HIVE)

    if discovery_info["HA_DeviceType"] == "Hub_OnlineStatus":
        add_devices([HiveSensorEntity(session, discovery_info)])


class HiveSensorEntity(Entity):
    """Hive Sensor Entity."""

    def __init__(self, hivesession, hivedevice):
        """Initialize the sensor."""
        self.node_id = hivedevice["Hive_NodeID"]
        self.device_type = hivedevice["HA_DeviceType"]
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
        return "Hive hub status"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.session.sensor.hub_online_status(self.node_id)

    def update(self):
        """Update all Node data frome Hive."""
        self.session.core.update_data(self.node_id)
