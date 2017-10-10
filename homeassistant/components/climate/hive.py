"""Hive Integration - climate."""
import logging
from homeassistant.components.climate import (ClimateDevice, ENTITY_ID_FORMAT)
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE
from homeassistant.loader import get_component

DEPENDENCIES = ['hive']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices,
                   device_list, discovery_info=None):
    """Setup Hive climate devices."""
    hive_comp = get_component('hive')

    if len(device_list) > 0:
        for a_device in device_list:
            if ("HA_DeviceType" in a_device and "Hive_NodeID" in a_device and
                    "Hive_NodeName" in a_device):
                if a_device["HA_DeviceType"] == "Heating":
                    add_devices([HiveHeating(hass,
                                             hive_comp.HGO,
                                             a_device["Hive_NodeID"],
                                             a_device["Hive_NodeName"],
                                             a_device["HA_DeviceType"])])

                if a_device["HA_DeviceType"] == "HotWater":
                    add_devices([HiveHotWater(hass,
                                              hive_comp.HGO,
                                              a_device["Hive_NodeID"],
                                              a_device["Hive_NodeName"],
                                              a_device["HA_DeviceType"])])


class HiveHeating(ClimateDevice):
    """Hive Heating Device."""

    def __init__(self, hass, HiveComponent_HiveObjects,
                 NodeID, NodeName, DeviceType):
        """Initialize the Heating device."""
        self.h_o = HiveComponent_HiveObjects
        self.node_id = NodeID
        self.node_name = NodeName
        self.device_type = DeviceType

        set_entity_id = "Hive_Heating"
        if self.node_name is not None:
            set_entity_id = set_entity_id + "_" \
                            + self.node_name.replace(" ", "_")
        self.entity_id = ENTITY_ID_FORMAT.format(set_entity_id.lower())

        def handle_event(event):
            """Handle the new event."""
            self.schedule_update_ha_state()

        hass.bus.listen('Event_Hive_NewNodeData', handle_event)

    @property
    def name(self):
        """Return the name of the heating device."""
        friendly_name = "Heating"
        if self.node_name is not None:
            friendly_name = self.node_name + " " + friendly_name

        return friendly_name

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        return False

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement which this heating device uses."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.h_o.get_current_temperature(self.node_id,
                                                self.device_type)

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self.h_o.get_target_temperature(self.node_id,
                                               self.device_type)

    @property
    def min_temp(self):
        """Return minimum temperature."""
        return self.h_o.get_min_temperature(self.node_id,
                                            self.device_type)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.h_o.get_max_temperature(self.node_id,
                                            self.device_type)

    @property
    def operation_list(self):
        """List of the operation modes."""
        return self.h_o.get_heating_mode_list(self.node_id,
                                              self.device_type)

    @property
    def current_operation(self):
        """Return current mode."""
        return self.h_o.get_heating_mode(self.node_id,
                                         self.device_type)

    def set_operation_mode(self, operation_mode):
        """Set new Heating mode."""
        self.h_o.set_heating_mode(self.node_id, self.device_type,
                                  operation_mode)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            new_temperature = kwargs.get(ATTR_TEMPERATURE)
            self.h_o.set_target_temperature(self.node_id,
                                            self.device_type,
                                            new_temperature)

    def update(self):
        """Update all Node data frome Hive."""
        self.h_o.update_data(self.node_id, self.device_type)


class HiveHotWater(ClimateDevice):
    """Hive HotWater Device."""

    def __init__(self, hass, HiveComponent_HiveObjects,
                 NodeID, NodeName, DeviceType):
        """Initialize the HotWater device."""
        self.h_o = HiveComponent_HiveObjects
        self.node_id = NodeID
        self.node_name = NodeName
        self.device_type = DeviceType

        set_entity_id = "Hive_HotWater"
        self.entity_id = ENTITY_ID_FORMAT.format(set_entity_id.lower())

        def handle_event(event):
            """Handle the new event."""
            self.schedule_update_ha_state()

        hass.bus.listen('Event_Hive_NewNodeData', handle_event)

    @property
    def name(self):
        """Return the name of the HotWater device."""
        friendly_name = "Hot Water"
        return friendly_name

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        return False

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement which this HotWater device uses."""
        return TEMP_CELSIUS

    @property
    def operation_list(self):
        """List of the operation modes."""
        return self.h_o.get_hotwater_mode_list(self.node_id, self.device_type)

    @property
    def current_operation(self):
        """Return current mode."""
        return self.h_o.get_hotwater_mode(self.node_id, self.device_type)

    def set_operation_mode(self, operation_mode):
        """Set new HotWater mode."""
        self.h_o.set_hotwater_mode(self.node_id, self.device_type,
                                   operation_mode)

    def update(self):
        """Update all Node data frome Hive."""
        self.h_o.update_data(self.node_id, self.device_type)
