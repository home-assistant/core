"""
Support for the Hive devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.hive/
"""
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.hive import DATA_HIVE

DEPENDENCIES = ['hive']

DEVICETYPE_DEVICE_CLASS = {'motionsensor': 'motion',
                           'contactsensor': 'opening'}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Hive sensor devices."""
    if discovery_info is None:
        return
    session = hass.data.get(DATA_HIVE)

    add_devices([HiveBinarySensorEntity(session, discovery_info)])


class HiveBinarySensorEntity(BinarySensorDevice):
    """Representation of a Hive binary sensor."""

    def __init__(self, hivesession, hivedevice):
        """Initialize the hive sensor."""
        self.node_id = hivedevice["Hive_NodeID"]
        self.node_name = hivedevice["Hive_NodeName"]
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
    def device_class(self):
        """Return the class of this sensor."""
        return DEVICETYPE_DEVICE_CLASS.get(self.node_device_type)

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self.node_name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.session.sensor.get_state(self.node_id,
                                             self.node_device_type)

    def update(self):
        """Update all Node data frome Hive."""
        self.session.core.update_data(self.node_id)
