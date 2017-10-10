"""Hive Integration - sensor."""
import logging
from homeassistant.const import TEMP_CELSIUS
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.helpers.entity import Entity
from homeassistant.loader import get_component

DEPENDENCIES = ['hive']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices,
                   device_list, discovery_info=None):
    """Setup Hive sensor devices."""
    hive_comp = get_component('hive')

    if len(device_list) > 0:
        for device in device_list:
            if ("HA_DeviceType" in device and "Hive_NodeID" in device and
                    "Hive_NodeName" in device):
                if device["HA_DeviceType"] == "Heating_CurrentTemperature":
                    add_devices([CurrentTemperature(hass,
                                                    hive_comp.HGO,
                                                    device["Hive_NodeID"],
                                                    device["Hive_NodeName"],
                                                    device["HA_DeviceType"])])
                if device["HA_DeviceType"] == "Heating_TargetTemperature":
                    add_devices([TargetTemperature(hass,
                                                   hive_comp.HGO,
                                                   device["Hive_NodeID"],
                                                   device["Hive_NodeName"],
                                                   device["HA_DeviceType"])])
                if device["HA_DeviceType"] == "Heating_State":
                    add_devices([HeatingState(hass,
                                              hive_comp.HGO,
                                              device["Hive_NodeID"],
                                              device["Hive_NodeName"],
                                              device["HA_DeviceType"])])
                if device["HA_DeviceType"] == "Heating_Mode":
                    add_devices([HeatingMode(hass,
                                             hive_comp.HGO,
                                             device["Hive_NodeID"],
                                             device["Hive_NodeName"],
                                             device["HA_DeviceType"])])
                if device["HA_DeviceType"] == "Heating_Boost":
                    add_devices([HeatingBoost(hass,
                                              hive_comp.HGO,
                                              device["Hive_NodeID"],
                                              device["Hive_NodeName"],
                                              device["HA_DeviceType"])])
                if device["HA_DeviceType"] == "HotWater_State":
                    add_devices([HotWaterState(hass,
                                               hive_comp.HGO,
                                               device["Hive_NodeID"],
                                               device["Hive_NodeName"],
                                               device["HA_DeviceType"])])
                if device["HA_DeviceType"] == "HotWater_Mode":
                    add_devices([HotWaterMode(hass,
                                              hive_comp.HGO,
                                              device["Hive_NodeID"],
                                              device["Hive_NodeName"],
                                              device["HA_DeviceType"])])
                if device["HA_DeviceType"] == "HotWater_Boost":
                    add_devices([HotWaterBoost(hass,
                                               hive_comp.HGO,
                                               device["Hive_NodeID"],
                                               device["Hive_NodeName"],
                                               device["HA_DeviceType"])])
                if device["HA_DeviceType"] == "Hive_Device_BatteryLevel":
                    add_devices([BatteryLevel(hass,
                                              hive_comp.HGO,
                                              device["Hive_NodeID"],
                                              device["Hive_NodeName"],
                                              device["HA_DeviceType"],
                                              device["Hive_DeviceType"])])
                if device["HA_DeviceType"] == "Hive_Device_Sensor":
                    add_devices([DeviceSensor(hass,
                                              hive_comp.HGO,
                                              device["Hive_NodeID"],
                                              device["Hive_NodeName"],
                                              device["HA_DeviceType"],
                                              device["Hive_DeviceType"])])
                if device["HA_DeviceType"] == "Hive_Device_Mode":
                    add_devices([DeviceMode(hass,
                                            hive_comp.HGO,
                                            device["Hive_NodeID"],
                                            device["Hive_NodeName"],
                                            device["HA_DeviceType"],
                                            device["Hive_DeviceType"])])


class CurrentTemperature(Entity):
    """Hive Heating current temperature Sensor."""

    def __init__(self, hass, HiveComponent_HiveObjects,
                 NodeID, NodeName, DeviceType):
        """Initialize the sensor."""
        self.h_o = HiveComponent_HiveObjects
        self.node_id = NodeID
        self.node_name = NodeName
        self.device_type = DeviceType

        set_entity_id = "Hive_Current_Temperature"
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
        """Return the name of the sensor."""
        friendly_name = "Current Temperature"
        if self.node_name is not None:
            friendly_name = self.node_name + " " + friendly_name

        return friendly_name

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.h_o.get_current_temperature(self.node_id,
                                                self.device_type)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self.h_o.get_current_temp_sa(self.node_id, self.device_type)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    def update(self):
        """Fetch new state data for the sensor."""
        self.h_o.update_data(self.node_id, self.device_type)


class TargetTemperature(Entity):
    """Hive Heating target temperature Sensor."""

    def __init__(self, hass, HiveComponent_HiveObjects,
                 NodeID, NodeName, DeviceType):
        """Initialize the sensor."""
        self.h_o = HiveComponent_HiveObjects
        self.node_id = NodeID
        self.node_name = NodeName
        self.device_type = DeviceType

        set_entity_id = "Hive_Target_Temperature"
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
        """Return the name of the sensor."""
        friendly_name = "Target Temperature"
        if self.node_name is not None:
            friendly_name = self.node_name + " " + friendly_name

        return friendly_name

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        return True

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.h_o.get_target_temperature(self.node_id, self.device_type)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self.h_o.get_target_temp_sa(self.node_id, self.device_type)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement to display."""
        return TEMP_CELSIUS

#    @property
#    def temperature_unit(self):
#        """The unit of measurement used by the platform."""
#        return TEMP_FAHRENHEIT

    def update(self):
        """Fetch new state data for the sensor."""
        self.h_o.update_data(self.node_id, self.device_type)


class HeatingState(Entity):
    """Hive Heating current state (On / Off)."""

    def __init__(self, hass, HiveComponent_HiveObjects,
                 NodeID, NodeName, DeviceType):
        """Initialize the sensor."""
        self.h_o = HiveComponent_HiveObjects
        self.node_id = NodeID
        self.node_name = NodeName
        self.device_type = DeviceType

        set_entity_id = "Hive_Heating_State"
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
        """Return the name of the sensor."""
        friendly_name = "Heating State"
        if self.node_name is not None:
            friendly_name = self.node_name + " " + friendly_name

        return friendly_name

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.h_o.get_heating_state(self.node_id, self.device_type)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self.h_o.get_heating_state_sa(self.node_id, self.device_type)

    @property
    def icon(self):
        """Return the icon to use."""
        device_icon = 'mdi:radiator'

        return device_icon

    def update(self):
        """Fetch new state data for the sensor."""
        self.h_o.update_data(self.node_id, self.device_type)


class HeatingMode(Entity):
    """Hive Heating current Mode (SCHEDULE / MANUAL / OFF)."""

    def __init__(self, hass, HiveComponent_HiveObjects,
                 NodeID, NodeName, DeviceType):
        """Initialize the sensor."""
        self.h_o = HiveComponent_HiveObjects
        self.node_id = NodeID
        self.node_name = NodeName
        self.device_type = DeviceType

        set_entity_id = "Hive_Heating_Mode"
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
        """Return the name of the sensor."""
        friendly_name = "Heating Mode"
        if self.node_name is not None:
            friendly_name = self.node_name + " " + friendly_name

        return friendly_name

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.h_o.get_heating_mode(self.node_id, self.device_type)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self.h_o.get_heating_mode_sa(self.node_id, self.device_type)

    @property
    def icon(self):
        """Return the icon to use."""
        device_icon = 'mdi:radiator'

        return device_icon

    def update(self):
        """Fetch new state data for the sensor."""
        self.h_o.update_data(self.node_id, self.device_type)


class HeatingBoost(Entity):
    """Hive Heating current Boost (ON / OFF)."""

    def __init__(self, hass, HiveComponent_HiveObjects,
                 NodeID, NodeName, DeviceType):
        """Initialize the sensor."""
        self.h_o = HiveComponent_HiveObjects
        self.node_id = NodeID
        self.node_name = NodeName
        self.device_type = DeviceType

        set_entity_id = "Hive_Heating_Boost"
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
        """Return the name of the sensor."""
        friendly_name = "Heating Boost"
        if self.node_name is not None:
            friendly_name = self.node_name + " " + friendly_name

        return friendly_name

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.h_o.get_heating_boost(self.node_id, self.device_type)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self.h_o.get_heating_boost_sa(self.node_id, self.device_type)

    @property
    def icon(self):
        """Return the icon to use."""
        device_icon = 'mdi:radiator'

        return device_icon

    def update(self):
        """Fetch new state data for the sensor."""
        self.h_o.update_data(self.node_id, self.device_type)


class HotWaterState(Entity):
    """Hive Hot water current state (On / Off)."""

    def __init__(self, hass, HiveComponent_HiveObjects,
                 NodeID, NodeName, DeviceType):
        """Initialize the sensor."""
        self.h_o = HiveComponent_HiveObjects
        self.node_id = NodeID
        self.node_name = NodeName
        self.device_type = DeviceType

        set_entity_id = "Hive_Hot_Water_State"
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
        """Return the name of the sensor."""
        friendly_name = "Hot Water State"
        if self.node_name is not None:
            friendly_name = self.node_name + " " + friendly_name

        return friendly_name

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.h_o.get_hotwater_state(self.node_id, self.device_type)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self.h_o.get_hotwater_state_sa(self.node_id, self.device_type)

    @property
    def icon(self):
        """Return the icon to use."""
        device_icon = 'mdi:water-pump'

        return device_icon

    def update(self):
        """Fetch new state data for the sensor."""
        self.h_o.update_data(self.node_id, self.device_type)


class HotWaterMode(Entity):
    """Hive HotWater current Mode (SCHEDULE / ON / OFF)."""

    def __init__(self, hass, HiveComponent_HiveObjects,
                 NodeID, NodeName, DeviceType):
        """Initialize the sensor."""
        self.h_o = HiveComponent_HiveObjects
        self.node_id = NodeID
        self.node_name = NodeName
        self.device_type = DeviceType

        set_entity_id = "Hive_Hot_Water_Mode"
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
        """Return the name of the sensor."""
        friendly_name = "Hot Water Mode"
        if self.node_name is not None:
            friendly_name = self.node_name + " " + friendly_name

        return friendly_name

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.h_o.get_hotwater_mode(self.node_id, self.device_type)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self.h_o.get_hotwater_mode_sa(self.node_id, self.device_type)

    @property
    def icon(self):
        """Return the icon to use."""
        device_icon = 'mdi:water-pump'

        return device_icon

    def update(self):
        """Fetch new state data for the sensor."""
        self.h_o.update_data(self.node_id, self.device_type)


class HotWaterBoost(Entity):
    """Hive HotWater current Boost (ON / OFF)."""

    def __init__(self, hass, HiveComponent_HiveObjects,
                 NodeID, NodeName, DeviceType):
        """Initialize the sensor."""
        self.h_o = HiveComponent_HiveObjects
        self.node_id = NodeID
        self.node_name = NodeName
        self.device_type = DeviceType

        set_entity_id = "Hive_Hot_Water_Boost"
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
        """Return the name of the sensor."""
        friendly_name = "Hot Water Boost"
        if self.node_name is not None:
            friendly_name = self.node_name + " " + friendly_name

        return friendly_name

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.h_o.get_hotwater_boost(self.node_id, self.device_type)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self.h_o.get_hotwater_boost_sa(self.node_id, self.device_type)

    @property
    def icon(self):
        """Return the icon to use."""
        device_icon = 'mdi:water-pump'

        return device_icon

    def update(self):
        """Fetch new state data for the sensor."""
        self.h_o.update_data(self.node_id, self.device_type)


class BatteryLevel(Entity):
    """Hive device current battery level sensor."""

    def __init__(self, hass, HiveComponent_HiveObjects,
                 NodeID, NodeName, DeviceType, NodeDeviceType):
        """Initialize the sensor."""
        self.h_o = HiveComponent_HiveObjects
        self.node_id = NodeID
        self.node_name = NodeName
        self.device_type = DeviceType
        self.node_device_type = NodeDeviceType

        if self.node_device_type == "thermostatui":
            set_entity_id = "Hive_Thermostat_Battery_Level"
            if self.node_name is not None:
                set_entity_id = set_entity_id + "_" \
                                + self.node_name.replace(" ", "_")
            self.entity_id = ENTITY_ID_FORMAT.format(set_entity_id.lower())

        self.battery_level = None

        def handle_event(event):
            """Handle the new event."""
            self.schedule_update_ha_state()

        hass.bus.listen('Event_Hive_NewNodeData', handle_event)

    @property
    def name(self):
        """Return the name of the sensor."""
        if self.node_device_type == "thermostatui":
            friendly_name = "Thermostat Battery Level"
        else:
            friendly_name = "Battery Level"
        if self.node_name is not None:
            friendly_name = self.node_name + " " + friendly_name

        return friendly_name

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        return True

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement which this thermostat uses."""
        return "%"

    @property
    def state(self):
        """Return the state of the sensor."""
        self.battery_level = self.h_o.get_battery_level(self.node_id,
                                                        self.node_name,
                                                        self.device_type,
                                                        self.node_device_type)
        return self.battery_level

    @property
    def icon(self):
        """Return the icon to use."""
        device_icon = 'mdi:battery'

        if self.battery_level >= 95 and self.battery_level <= 100:
            device_icon = 'mdi:battery'
        elif self.battery_level >= 85 and self.battery_level < 95:
            device_icon = 'mdi:battery-90'
        elif self.battery_level >= 75 and self.battery_level < 85:
            device_icon = 'mdi:battery-80'
        elif self.battery_level >= 65 and self.battery_level < 75:
            device_icon = 'mdi:battery-70'
        elif self.battery_level >= 55 and self.battery_level < 65:
            device_icon = 'mdi:battery-60'
        elif self.battery_level >= 45 and self.battery_level < 55:
            device_icon = 'mdi:battery-50'
        elif self.battery_level >= 35 and self.battery_level < 45:
            device_icon = 'mdi:battery-40'
        elif self.battery_level >= 25 and self.battery_level < 35:
            device_icon = 'mdi:battery-30'
        elif self.battery_level >= 15 and self.battery_level < 25:
            device_icon = 'mdi:battery-20'
        elif self.battery_level > 5 and self.battery_level < 15:
            device_icon = 'mdi:battery-10'
        elif self.battery_level <= 5:
            device_icon = 'mdi:battery-outline'

        return device_icon

    def update(self):
        """Fetch new state data for the sensor."""
        self.h_o.update_data(self.node_id, self.device_type)


class DeviceSensor(Entity):
    """Hive device sensor."""

    def __init__(self, hass, HiveComponent_HiveObjects,
                 NodeID, NodeName, DeviceType, NodeDeviceType):
        """Initialize the sensor."""
        self.hive_objects = HiveComponent_HiveObjects
        self.node_id = NodeID
        self.node_name = NodeName
        self.device_type = DeviceType
        self.node_device_type = NodeDeviceType

        def handle_event(event):
            """Handle the new event."""
            self.schedule_update_ha_state()

        hass.bus.listen('Event_Hive_NewNodeData', handle_event)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.node_name

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        return True

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.hive_objects.get_sensor_state(self.node_id,
                                                  self.node_name,
                                                  self.device_type,
                                                  self.node_device_type)

    def update(self):
        """Fetch new state data for the sensor."""
        self.hive_objects.update_data(self.node_id, self.device_type)


class DeviceMode(Entity):
    """Hive device current mode sensor."""

    def __init__(self, hass, HiveComponent_HiveObjects,
                 NodeID, NodeName, DeviceType, NodeDeviceType):
        """Initialize the sensor."""
        self.hive_objects = HiveComponent_HiveObjects
        self.node_id = NodeID
        self.node_name = NodeName
        self.device_type = DeviceType
        self.node_device_type = NodeDeviceType

        def handle_event(event):
            """Handle the new event."""
            self.schedule_update_ha_state()

        hass.bus.listen('Event_Hive_NewNodeData', handle_event)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.node_name

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        return True

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.hive_objects.get_device_mode(self.node_id,
                                                 self.node_name,
                                                 self.device_type,
                                                 self.node_device_type)

    def update(self):
        """Fetch new state data for the sensor."""
        self.hive_objects.update_data(self.node_id, self.device_type)
