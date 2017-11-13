"""
Support for the Hive devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/hive/
"""
import logging

from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['hive']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, hivedevice, discovery_info=None):
    """Set up Hive switches."""
    session = hass.data.get('DATA_HIVE')

    add_devices([HiveDevicePlug(hass, session, hivedevice)])


class HiveDevicePlug(SwitchDevice):
    """Hive Active Plug."""

    def __init__(self, hass, Session, HiveDevice):
        """Initialize the Switch device."""
        self.node_id = HiveDevice["Hive_NodeID"]
        self.node_name = HiveDevice["Hive_NodeName"]
        self.device_type = HiveDevice["HA_DeviceType"]
        self.hass = hass
        self.session = Session
        self.session.switch = self.session.core.Switch()

        self.hass.bus.listen('Event_Hive_NewNodeData', self.handle_event)

    def handle_event(self, event):
        """Handle the new event."""
        if self.device_type + "." + self.node_id not in str(event):
            self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of this Switch device if any."""
        return self.node_name

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self.session.switch.get_power_usage(self.node_id)

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        return False

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.session.switch.get_state(self.node_id)

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        eventsource = self.device_type + "." + self.node_id
        self.hass.bus.fire('Event_Hive_NewNodeData',
                           {"EventSource": eventsource})
        return self.session.switch.turn_on(self.node_id)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        eventsource = self.device_type + "." + self.node_id
        self.hass.bus.fire('Event_Hive_NewNodeData',
                           {"EventSource": eventsource})
        return self.session.switch.turn_off(self.node_id)
