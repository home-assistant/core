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

    for device in device_list:
        if ("HA_DeviceType" in device and "Hive_NodeID" in device and
                "Hive_NodeName" in device):
            add_devices([HiveSensorEntity(hass,
                                          hive_comp.HGO,
                                          device["Hive_NodeID"],
                                          device["Hive_NodeName"],
                                          device["HA_DeviceType"],
                                          device["Hive_DeviceType"])])


class HiveSensorEntity(Entity):
    """Hive Sensor Entity."""

    def __init__(self, hass, HiveComponent_HiveObjects,
                 NodeID, NodeName, DeviceType, NodeDeviceType):
        """Initialize the sensor."""
        self.h_o = HiveComponent_HiveObjects
        self.node_id = NodeID
        self.node_name = NodeName
        self.device_type = DeviceType
        self.node_device_type = NodeDeviceType

        set_entity_id = "Sensor"

        if self.device_type == "Heating_CurrentTemperature":
            set_entity_id = "Hive_Current_Temperature"
        elif self.device_type == "Heating_TargetTemperature":
            set_entity_id = "Hive_Target_Temperature"
        elif self.device_type == "Heating_State":
            set_entity_id = "Hive_Heating_State"
        elif self.device_type == "Heating_Mode":
            set_entity_id = "Hive_Heating_Mode"
        elif self.device_type == "Heating_Boost":
            set_entity_id = "Hive_Heating_Boost"
        elif self.device_type == "HotWater_State":
            set_entity_id = "Hive_Hot_Water_State"
        elif self.device_type == "HotWater_Mode":
            set_entity_id = "Hive_Hot_Water_Mode"
        elif self.device_type == "HotWater_Boost":
            set_entity_id = "Hive_Hot_Water_Boost"
        elif self.device_type == "Hive_Device_BatteryLevel":
            self.batt_lvl = None
            if self.node_device_type == "thermostatui":
                set_entity_id = "Hive_Thermostat_Battery_Level"
        elif self.device_type == "Hive_Device_Sensor":
            set_entity_id = None
        elif self.device_type == "Hive_Device_Light_Mode":
            set_entity_id = None
        elif self.device_type == "Hive_Device_Plug_Mode":
            set_entity_id = None

        if set_entity_id is not None:
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
        friendly_name = "Sensor"

        if self.device_type == "Heating_CurrentTemperature":
            friendly_name = "Current Temperature"
        elif self.device_type == "Heating_TargetTemperature":
            friendly_name = "Target Temperature"
        elif self.device_type == "Heating_State":
            friendly_name = "Heating State"
        elif self.device_type == "Heating_Mode":
            friendly_name = "Heating Mode"
        elif self.device_type == "Heating_Boost":
            friendly_name = "Heating Boost"
        elif self.device_type == "HotWater_State":
            friendly_name = "Hot Water State"
        elif self.device_type == "HotWater_Mode":
            friendly_name = "Hot Water Mode"
        elif self.device_type == "HotWater_Boost":
            friendly_name = "Hot Water Boost"
        elif self.device_type == "Hive_Device_BatteryLevel":
            if self.node_device_type == "thermostatui":
                friendly_name = "Thermostat Battery Level"
            else:
                friendly_name = "Battery Level"
        elif self.device_type == "Hive_Device_Sensor":
            return self.node_name
        elif self.device_type == "Hive_Device_Light_Mode":
            return self.node_name
        elif self.device_type == "Hive_Device_Plug_Mode":
            return self.node_name

        if self.node_name is not None:
            friendly_name = self.node_name + " " + friendly_name

        return friendly_name

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        if self.device_type == "Heating_CurrentTemperature":
            return False
        elif self.device_type == "Heating_TargetTemperature":
            return True
        elif self.device_type == "Heating_State":
            return False
        elif self.device_type == "Heating_Mode":
            return False
        elif self.device_type == "Heating_Boost":
            return False
        elif self.device_type == "HotWater_State":
            return False
        elif self.device_type == "HotWater_Mode":
            return False
        elif self.device_type == "HotWater_Boost":
            return False
        elif self.device_type == "Hive_Device_BatteryLevel":
            return True
        elif self.device_type == "Hive_Device_Sensor":
            return True
        elif self.device_type == "Hive_Device_Light_Mode":
            return True
        elif self.device_type == "Hive_Device_Plug_Mode":
            return True

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.device_type == "Heating_CurrentTemperature":
            return self.h_o.get_current_temperature(self.node_id,
                                                    self.device_type)
        elif self.device_type == "Heating_TargetTemperature":
            return self.h_o.get_target_temperature(self.node_id,
                                                   self.device_type)
        elif self.device_type == "Heating_State":
            return self.h_o.get_heating_state(self.node_id,
                                              self.device_type)
        elif self.device_type == "Heating_Mode":
            return self.h_o.get_heating_mode(self.node_id,
                                             self.device_type)
        elif self.device_type == "Heating_Boost":
            return self.h_o.get_heating_boost(self.node_id,
                                              self.device_type)
        elif self.device_type == "HotWater_State":
            return self.h_o.get_hotwater_state(self.node_id,
                                               self.device_type)
        elif self.device_type == "HotWater_Mode":
            return self.h_o.get_hotwater_mode(self.node_id,
                                              self.device_type)
        elif self.device_type == "HotWater_Boost":
            return self.h_o.get_hotwater_boost(self.node_id,
                                               self.device_type)
        elif self.device_type == "Hive_Device_BatteryLevel":
            self.batt_lvl = self.h_o.get_battery_level(self.node_id,
                                                       self.node_name,
                                                       self.device_type,
                                                       self.node_device_type)
            return self.batt_lvl
        elif self.device_type == "Hive_Device_Sensor":
            return self.h_o.get_sensor_state(self.node_id,
                                             self.node_name,
                                             self.device_type,
                                             self.node_device_type)
        elif self.device_type == "Hive_Device_Light_Mode":
            return self.h_o.get_device_mode(self.node_id,
                                            self.node_name,
                                            self.device_type,
                                            self.node_device_type)
        elif self.device_type == "Hive_Device_Plug_Mode":
            return self.h_o.get_device_mode(self.node_id,
                                            self.node_name,
                                            self.device_type,
                                            self.node_device_type)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.device_type == "Heating_CurrentTemperature":
            return self.h_o.get_current_temp_sa(self.node_id,
                                                self.device_type)
        elif self.device_type == "Heating_TargetTemperature":
            return self.h_o.get_target_temp_sa(self.node_id,
                                               self.device_type)
        elif self.device_type == "Heating_State":
            return self.h_o.get_heating_state_sa(self.node_id,
                                                 self.device_type)
        elif self.device_type == "Heating_Mode":
            return self.h_o.get_heating_mode_sa(self.node_id,
                                                self.device_type)
        elif self.device_type == "Heating_Boost":
            return self.h_o.get_heating_boost_sa(self.node_id,
                                                 self.device_type)
        elif self.device_type == "HotWater_State":
            return self.h_o.get_hotwater_state_sa(self.node_id,
                                                  self.device_type)
        elif self.device_type == "HotWater_Mode":
            return self.h_o.get_hotwater_mode_sa(self.node_id,
                                                 self.device_type)
        elif self.device_type == "HotWater_Boost":
            return self.h_o.get_hotwater_boost_sa(self.node_id,
                                                  self.device_type)
        elif self.device_type == "Hive_Device_BatteryLevel":
            return None
        elif self.device_type == "Hive_Device_Sensor":
            return None
        elif self.device_type == "Hive_Device_Light_Mode":
            return None
        elif self.device_type == "Hive_Device_Plug_Mode":
            return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.device_type == "Heating_CurrentTemperature":
            return TEMP_CELSIUS
        elif self.device_type == "Heating_TargetTemperature":
            return TEMP_CELSIUS
        elif self.device_type == "Heating_State":
            return None
        elif self.device_type == "Heating_Mode":
            return None
        elif self.device_type == "Heating_Boost":
            return None
        elif self.device_type == "HotWater_State":
            return None
        elif self.device_type == "HotWater_Mode":
            return None
        elif self.device_type == "HotWater_Boost":
            return None
        elif self.device_type == "Hive_Device_BatteryLevel":
            return "%"
        elif self.device_type == "Hive_Device_Sensor":
            return None
        elif self.device_type == "Hive_Device_Light_Mode":
            return None
        elif self.device_type == "Hive_Device_Plug_Mode":
            return None

    @property
    def icon(self):
        """Return the icon to use."""
        device_icon = 'mdi:thermometer'

        if self.device_type == "Heating_CurrentTemperature":
            device_icon = 'mdi:thermometer'
        elif self.device_type == "Heating_TargetTemperature":
            device_icon = 'mdi:thermometer'
        elif self.device_type == "Heating_State":
            device_icon = 'mdi:radiator'
        elif self.device_type == "Heating_Mode":
            device_icon = 'mdi:radiator'
        elif self.device_type == "Heating_Boost":
            device_icon = 'mdi:radiator'
        elif self.device_type == "HotWater_State":
            device_icon = 'mdi:water-pump'
        elif self.device_type == "HotWater_Mode":
            device_icon = 'mdi:water-pump'
        elif self.device_type == "HotWater_Boost":
            device_icon = 'mdi:water-pump'
        elif self.device_type == "Hive_Device_BatteryLevel":
            if self.batt_lvl >= 95 and self.batt_lvl <= 100:
                device_icon = 'mdi:battery'
            elif self.batt_lvl >= 85 and self.batt_lvl < 95:
                device_icon = 'mdi:battery-90'
            elif self.batt_lvl >= 75 and self.batt_lvl < 85:
                device_icon = 'mdi:battery-80'
            elif self.batt_lvl >= 65 and self.batt_lvl < 75:
                device_icon = 'mdi:battery-70'
            elif self.batt_lvl >= 55 and self.batt_lvl < 65:
                device_icon = 'mdi:battery-60'
            elif self.batt_lvl >= 45 and self.batt_lvl < 55:
                device_icon = 'mdi:battery-50'
            elif self.batt_lvl >= 35 and self.batt_lvl < 45:
                device_icon = 'mdi:battery-40'
            elif self.batt_lvl >= 25 and self.batt_lvl < 35:
                device_icon = 'mdi:battery-30'
            elif self.batt_lvl >= 15 and self.batt_lvl < 25:
                device_icon = 'mdi:battery-20'
            elif self.batt_lvl > 5 and self.batt_lvl < 15:
                device_icon = 'mdi:battery-10'
            elif self.batt_lvl <= 5:
                device_icon = 'mdi:battery-outline'
        elif self.device_type == "Hive_Device_Sensor":
            device_icon = 'mdi:eye'
        elif self.device_type == "Hive_Device_Light_Mode":
            device_icon = 'mdi:eye'
        elif self.device_type == "Hive_Device_Plug_Mode":
            device_icon = 'mdi:eye'

        return device_icon

    def update(self):
        """Fetch new state data for the sensor."""
        self.h_o.update_data(self.node_id, self.device_type)
