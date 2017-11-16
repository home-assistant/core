"""
Support for the Hive devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/hive/
"""
import logging
from datetime import datetime

from homeassistant.components.climate import (STATE_AUTO, STATE_HEAT,
                                              STATE_OFF, STATE_ON)
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['hive']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, hivedevice, discovery_info=None):
    """Set up Hive sensor devices."""
    session = hass.data.get('DATA_HIVE')

    add_devices([HiveSensorEntity(hass, session, hivedevice)])


class HiveSensorEntity(Entity):
    """Hive Sensor Entity."""

    def __init__(self, hass, Session, HiveDevice):
        """Initialize the sensor."""
        self.node_id = HiveDevice["Hive_NodeID"]
        self.node_name = HiveDevice["Hive_NodeName"]
        self.device_type = HiveDevice["HA_DeviceType"]
        self.node_device_type = HiveDevice["Hive_DeviceType"]
        self.hass = hass
        self.session = Session
        self.session.sensor = self.session.core.Sensor()

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

        self.hass.bus.listen('Event_Hive_NewNodeData', self.handle_event)

    def handle_event(self, event):
        """Handle the new event."""
        if self.device_type + "." + self.node_id not in str(event):
            self.schedule_update_ha_state()

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
            nodeid = self.node_id
            curtempret = self.session.heating.current_temperature(nodeid)

            if curtempret != -1000:
                if nodeid in self.session.data.minmax:
                    if (self.session.data.minmax[nodeid]['TodayDate'] !=
                            datetime.date(datetime.now())):
                        self.session.data.minmax[nodeid]['TodayMin'] = 1000
                        self.session.data.minmax[nodeid]['TodayMax'] = -1000
                        self.session.data.minmax[nodeid]['TodayDate'] = \
                            datetime.date(datetime.now())

                    if (curtempret < self.session.data.minmax[nodeid]
                            ['TodayMin']):
                        self.session.data.minmax[nodeid]['TodayMin'] = \
                            curtempret

                    if (curtempret > self.session.data.minmax[nodeid]
                            ['TodayMax']):
                        self.session.data.minmax[nodeid]['TodayMax'] = \
                            curtempret

                    if (curtempret < self.session.data.minmax[nodeid]
                            ['RestartMin']):
                        self.session.data.minmax[nodeid]['RestartMin'] = \
                            curtempret

                    if (curtempret >
                            self.session.data.minmax[nodeid]
                            ['RestartMax']):
                        self.session.data.minmax[nodeid]['RestartMax'] = \
                            curtempret
                else:
                    current_node_max_min_data = {}
                    current_node_max_min_data['TodayMin'] = curtempret
                    current_node_max_min_data['TodayMax'] = curtempret
                    current_node_max_min_data['TodayDate'] = \
                        datetime.date(datetime.now())
                    current_node_max_min_data['RestartMin'] = curtempret
                    current_node_max_min_data['RestartMax'] = curtempret
                    self.session.data.minmax[nodeid] = \
                        current_node_max_min_data
            else:
                curtempret = 0
            return curtempret
        elif self.device_type == "Heating_TargetTemperature":
            return self.session.heating.get_target_temperature(self.node_id)
        elif self.device_type == "Heating_State":
            return self.session.heating.get_state(self.node_id)
        elif self.device_type == "Heating_Mode":
            currentmode = self.session.heating.get_mode(self.node_id)
            if currentmode == "SCHEDULE":
                return STATE_AUTO
            elif currentmode == "MANUAL":
                return STATE_HEAT
            elif currentmode == "OFF":
                return STATE_OFF
        elif self.device_type == "Heating_Boost":
            return self.session.heating.get_boost(self.node_id)
        elif self.device_type == "HotWater_State":
            return self.session.hotwater.get_state(self.node_id)
        elif self.device_type == "HotWater_Mode":
            currentmode = self.session.hotwater.get_mode(self.node_id)
            if currentmode == "SCHEDULE":
                return STATE_AUTO
            elif currentmode == "ON":
                return STATE_ON
            elif currentmode == "OFF":
                return STATE_OFF
        elif self.device_type == "HotWater_Boost":
            return self.session.hotwater.get_boost(self.node_id)
        elif self.device_type == "Hive_Device_BatteryLevel":
            self.batt_lvl = self.session.sensor.battery_level(self.node_id)
            return self.batt_lvl
        elif self.device_type == "Hive_Device_Sensor":
            return self.session.sensor.get_state(self.node_id,
                                                 self.node_device_type)
        elif self.device_type == "Hive_Device_Light_Mode":
            return self.session.sensor.get_mode(self.node_id)
        elif self.device_type == "Hive_Device_Plug_Mode":
            return self.session.sensor.get_mode(self.node_id)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.device_type == "Heating_CurrentTemperature":
            return self.get_current_temp_sa()
        elif self.device_type == "Heating_TargetTemperature":
            return None
        elif self.device_type == "Heating_State":
            return self.get_heating_state_sa()
        elif self.device_type == "Heating_Mode":
            return self.get_heating_state_sa()
        elif self.device_type == "Heating_Boost":
            s_a = {}
            if self.session.heating.get_boost(self.node_id) == "ON":
                minsend = self.session.heating.get_boost_time(self.node_id)
                s_a.update({"Boost ends in":
                            (str(minsend) + " minutes")})
            return s_a
        elif self.device_type == "HotWater_State":
            return self.get_hotwater_state_sa()
        elif self.device_type == "HotWater_Mode":
            return self.get_hotwater_state_sa()
        elif self.device_type == "HotWater_Boost":
            s_a = {}
            if self.session.hotwater.get_boost(self.node_id) == "ON":
                endsin = self.session.hotwater.get_boost_time(self.node_id)
                s_a.update({"Boost ends in":
                            (str(endsin) + " minutes")})
            return s_a
        elif self.device_type == "Hive_Device_BatteryLevel":
            return None
        elif self.device_type == "Hive_Device_Sensor":
            return None
        elif self.device_type == "Hive_Device_Light_Mode":
            return None
        elif self.device_type == "Hive_Device_Plug_Mode":
            return None

    def get_current_temp_sa(self):
        """Public get current heating temperature state attributes."""
        s_a = {}
        temp_current = 0
        temperature_target = 0
        temperature_difference = 0

        if self.node_id in self.session.data.minmax:
            s_a.update({"Today Min / Max":
                        str(self.session.data.minmax[self.node_id]
                            ['TodayMin']) + " °C" + " / "
                        + str(self.session.data.minmax[self.node_id]
                              ['TodayMax']) + " °C"})

            s_a.update({"Restart Min / Max":
                        str(self.session.data.minmax[self.node_id]
                            ['RestartMin']) + " °C" + " / "
                        + str(self.session.data.minmax[self.node_id]
                              ['RestartMax']) + " °C"})

        temp_current = self.session.heating.current_temperature(self.node_id)
        temperature_target = self.session.heating.\
            get_target_temperature(self.node_id)

        if temperature_target > temp_current:
            temperature_difference = temperature_target - temp_current
            temperature_difference = round(temperature_difference, 2)

            s_a.update({"Current Temperature":
                        temp_current})
            s_a.update({"Target Temperature":
                        temperature_target})
            s_a.update({"Temperature Difference":
                        temperature_difference})

        return s_a

    def get_heating_state_sa(self):
        """Public get current heating state, state attributes."""
        s_a = {}

        snan = self.session.heating.get_schedule_now_next_later(self.node_id)
        if snan is not None:
            if 'now' in snan:
                if ('value' in snan["now"] and
                        'start' in snan["now"] and
                        'Start_DateTime' in snan["now"] and
                        'End_DateTime' in snan["now"] and
                        'target' in snan["now"]["value"]):
                    now_target = str(snan["now"]["value"]["target"]) + " °C"
                    nstrt = snan["now"]["Start_DateTime"].strftime("%H:%M")
                    now_end = snan["now"]["End_DateTime"].strftime("%H:%M")

                    sa_string = (now_target
                                 + " : "
                                 + nstrt
                                 + " - "
                                 + now_end)
                    s_a.update({"Now": sa_string})

            if 'next' in snan:
                if ('value' in snan["next"] and
                        'start' in snan["next"] and
                        'Start_DateTime' in snan["next"] and
                        'End_DateTime' in snan["next"] and
                        'target' in snan["next"]["value"]):
                    next_target = str(snan["next"]["value"]["target"]) + " °C"
                    nxtstrt = snan["next"]["Start_DateTime"].strftime("%H:%M")
                    next_end = snan["next"]["End_DateTime"].strftime("%H:%M")

                    sa_string = (next_target
                                 + " : "
                                 + nxtstrt
                                 + " - "
                                 + next_end)
                    s_a.update({"Next": sa_string})

            if 'later' in snan:
                if ('value' in snan["later"] and
                        'start' in snan["later"] and
                        'Start_DateTime' in snan["later"] and
                        'End_DateTime' in snan["later"] and
                        'target' in snan["later"]["value"]):
                    ltarg = str(snan["later"]["value"]["target"]) + " °C"
                    lstrt = snan["later"]["Start_DateTime"].strftime("%H:%M")
                    lend = snan["later"]["End_DateTime"].strftime("%H:%M")

                    sa_string = (ltarg
                                 + " : "
                                 + lstrt
                                 + " - "
                                 + lend)
                    s_a.update({"Later": sa_string})
        else:
            s_a.update({"Schedule not active": ""})

        return s_a

    def get_hotwater_state_sa(self):
        """Public get current hotwater state, state attributes."""
        s_a = {}

        snan = self.session.hotwater.get_schedule_now_next_later(self.node_id)
        if snan is not None:
            if 'now' in snan:
                if ('value' in snan["now"] and
                        'start' in snan["now"] and
                        'Start_DateTime' in snan["now"] and
                        'End_DateTime' in snan["now"] and
                        'status' in snan["now"]["value"]):
                    now_status = snan["now"]["value"]["status"]
                    now_start = snan["now"]["Start_DateTime"].strftime("%H:%M")
                    now_end = snan["now"]["End_DateTime"].strftime("%H:%M")

                    sa_string = (now_status
                                 + " : "
                                 + now_start
                                 + " - "
                                 + now_end)
                    s_a.update({"Now": sa_string})

            if 'next' in snan:
                if ('value' in snan["next"] and
                        'start' in snan["next"] and
                        'Start_DateTime' in snan["next"] and
                        'End_DateTime' in snan["next"] and
                        'status' in snan["next"]["value"]):
                    next_status = snan["next"]["value"]["status"]
                    nxtstrt = snan["next"]["Start_DateTime"].strftime("%H:%M")
                    next_end = snan["next"]["End_DateTime"].strftime("%H:%M")

                    sa_string = (next_status
                                 + " : "
                                 + nxtstrt
                                 + " - "
                                 + next_end)
                    s_a.update({"Next": sa_string})
            if 'later' in snan:
                if ('value' in snan["later"] and
                        'start' in snan["later"] and
                        'Start_DateTime' in snan["later"] and
                        'End_DateTime' in snan["later"] and
                        'status' in snan["later"]["value"]):
                    later_status = snan["later"]["value"]["status"]
                    later_start = (snan["later"]
                                   ["Start_DateTime"].strftime("%H:%M"))
                    later_end = snan["later"]["End_DateTime"].strftime("%H:%M")

                    sa_string = (later_status
                                 + " : "
                                 + later_start
                                 + " - "
                                 + later_end)
                    s_a.update({"Later": sa_string})
        else:
            s_a.update({"Schedule not active": ""})

        return s_a

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
        self.session.core.hive_api_get_nodes_rl(self.node_id)
