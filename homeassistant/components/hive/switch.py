"""Support for the Hive switches."""
from homeassistant.components.switch import SwitchDevice

from . import DATA_HIVE, DOMAIN

DEPENDENCIES = ['hive']


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Hive switches."""
    if discovery_info is None:
        return
    session = hass.data.get(DATA_HIVE)

    add_entities([HiveDevicePlug(session, discovery_info)])


class HiveDevicePlug(SwitchDevice):
    """Hive Active Plug."""

    def __init__(self, hivesession, hivedevice):
        """Initialize the Switch device."""
        self.node_id = hivedevice["Hive_NodeID"]
        self.node_name = hivedevice["Hive_NodeName"]
        self.device_type = hivedevice["HA_DeviceType"]
        self.session = hivesession
        self.attributes = {}
        self.data_updatesource = '{}.{}'.format(
            self.device_type, self.node_id)
        self._unique_id = '{}-{}'.format(self.node_id, self.device_type)
        self.session.entities.append(self)

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        return {
            'identifiers': {
                (DOMAIN, self.unique_id)
            },
            'name': self.name
        }

    def handle_update(self, updatesource):
        """Handle the new update request."""
        if '{}.{}'.format(self.device_type, self.node_id) not in updatesource:
            self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of this Switch device if any."""
        return self.node_name

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        return self.attributes

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self.session.switch.get_power_usage(self.node_id)

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.session.switch.get_state(self.node_id)

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.session.switch.turn_on(self.node_id)
        for entity in self.session.entities:
            entity.handle_update(self.data_updatesource)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.session.switch.turn_off(self.node_id)
        for entity in self.session.entities:
            entity.handle_update(self.data_updatesource)

    def update(self):
        """Update all Node data from Hive."""
        self.session.core.update_data(self.node_id)
        self.attributes = self.session.attributes.state_attributes(
            self.node_id)
