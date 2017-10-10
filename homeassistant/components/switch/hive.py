"""Hive Integration - switch."""
import logging
from homeassistant.components.switch import SwitchDevice
from homeassistant.loader import get_component

DEPENDENCIES = ['hive']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices,
                   device_list, discovery_info=None):
    """Setup Hive switches."""
    hive_comp = get_component('hive')

    if len(device_list) > 0:
        for a_device in device_list:
            add_devices([HiveDevicePlug(hass, hive_comp.HGO,
                                        a_device["Hive_NodeID"],
                                        a_device["Hive_NodeName"],
                                        a_device["HA_DeviceType"],
                                        a_device["Hive_Plug_DeviceType"])])


class HiveDevicePlug(SwitchDevice):
    """Hive Active Plug."""

    def __init__(self, hass, hivecomponent_hiveobjects, node_id, node_name,
                 device_type, node_device_type):
        """Initialize the Switch device."""
        self.h_o = hivecomponent_hiveobjects
        self.node_id = node_id
        self.node_name = node_name
        self.device_type = device_type
        self.node_device_type = node_device_type

        def handle_event(event):
            """Handle the new event."""
            self.schedule_update_ha_state()

        hass.bus.listen('Event_Hive_NewNodeData', handle_event)

    @property
    def name(self):
        """Return the name of this Switch device if any."""
        return self.node_name

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self.h_o.get_smartplug_power_consumption(self.node_id,
                                                        self.device_type,
                                                        self.node_name)

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        return False

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.h_o.get_smartplug_state(self.node_id,
                                            self.device_type,
                                            self.node_name)

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        return self.h_o.set_smartplug_turn_on(self.node_id,
                                              self.device_type,
                                              self.node_name,
                                              self.node_device_type)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        return self.h_o.set_smartplug_turn_off(self.node_id,
                                               self.device_type,
                                               self.node_name,
                                               self.node_device_type)
