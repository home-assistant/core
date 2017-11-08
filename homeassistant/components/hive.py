"""Hive Integration - Platform."""
import logging
from datetime import datetime
from homeassistant.helpers.discovery import load_platform

REQUIREMENTS = ['pyhiveapi==0.1.1']

HGO = None
_LOGGER = logging.getLogger(__name__)
DOMAIN = 'hive'


class HivePlatformData:
    """Initiate Hive PlatformData Class."""

    min_max_data = {}


class HiveSession:
    """Initiate Hive Session Class."""

    username = ""
    password = ""
    data = HivePlatformData()
    logging = False
    hass = None
    core = None
    heating = None
    hotwater = None
    light = None
    sensor = None
    switch = None


def setup(hass, config):
    """Setup the Hive platform."""
    from pyhiveapi import Pyhiveapi

    hsc_s = HiveSession()
    hsc_s.core = Pyhiveapi()

    hsc_s.hass = hass

    hsc_s.username = None
    hsc_s.password = None
    api_mins_between_updates = 2
    api_dl_all = {}
    api_dl_sensor = []
    api_dl_climate = []
    api_dl_light = []
    api_dl_switch = []

    hive_config = config[DOMAIN]

    if "username" in hive_config and "password" in hive_config:
        hsc_s.username = config[DOMAIN]['username']
        hsc_s.password = config[DOMAIN]['password']
    else:
        _LOGGER.error("Missing UserName or Password in config")

    if "minutes_between_updates" in hive_config:
        api_mins_between_updates = config[DOMAIN]['minutes_between_updates']
    else:
        api_mins_between_updates = 2

    if "logging" in hive_config:
        if config[DOMAIN]['logging']:
            hsc_s.logging = True
            _LOGGER.warning("Logging is Enabled")
        else:
            hsc_s.logging = False
    else:
        hsc_s.logging = False

    if hsc_s.username is None or hsc_s.password is None:
        _LOGGER.error("Missing UserName or Password in Hive Session details")
    else:

        api_dl_all = hsc_s.core.initialise_api(hsc_s.username,
                                               hsc_s.password,
                                               api_mins_between_updates)
        if api_dl_all is not None:
            api_dl_sensor = []
            api_dl_climate = []
            api_dl_light = []
            api_dl_switch = []

            if 'device_list_sensor' in api_dl_all:
                api_dl_sensor = api_dl_all["device_list_sensor"]

            if 'device_list_climate' in api_dl_all:
                api_dl_climate = api_dl_all["device_list_climate"]

            if 'device_list_light' in api_dl_all:
                api_dl_light = api_dl_all["device_list_light"]

            if 'device_list_plug' in api_dl_all:
                api_dl_switch = api_dl_all["device_list_plug"]

        else:
            _LOGGER.error("**** Return from initialise_api :: None")

    config_devices = []

    device_list_sensor = []
    device_list_climate = []
    device_list_light = []
    device_list_switch = []

    if "devices" in hive_config:
        config_devices = config[DOMAIN]['devices']

        for a_dl_device in api_dl_sensor:
            if "HA_DeviceType" in a_dl_device:
                if (a_dl_device["HA_DeviceType"]
                        == "Heating_CurrentTemperature" and
                        "hive_heating_currenttemperature" in config_devices):
                    device_list_sensor.append(a_dl_device)

                if (a_dl_device["HA_DeviceType"]
                        == "Heating_TargetTemperature" and
                        "hive_heating_targettemperature" in config_devices):
                    device_list_sensor.append(a_dl_device)

                if (a_dl_device["HA_DeviceType"] == "Heating_State" and
                        "hive_heating_state" in config_devices):
                    device_list_sensor.append(a_dl_device)

                if (a_dl_device["HA_DeviceType"] == "Heating_Mode" and
                        "hive_heating_mode" in config_devices):
                    device_list_sensor.append(a_dl_device)

                if (a_dl_device["HA_DeviceType"] == "Heating_Boost" and
                        "hive_heating_boost" in config_devices):
                    device_list_sensor.append(a_dl_device)

                if (a_dl_device["HA_DeviceType"] == "HotWater_State" and
                        "hive_hotwater_state" in config_devices):
                    device_list_sensor.append(a_dl_device)

                if (a_dl_device["HA_DeviceType"] == "HotWater_Mode" and
                        "hive_hotwater_mode" in config_devices):
                    device_list_sensor.append(a_dl_device)

                if (a_dl_device["HA_DeviceType"] == "HotWater_Boost" and
                        "hive_hotwater_boost" in config_devices):
                    device_list_sensor.append(a_dl_device)

                if (a_dl_device["HA_DeviceType"]
                        == "Hive_Device_BatteryLevel" and
                        "hive_thermostat_batterylevel" in config_devices):
                    device_list_sensor.append(a_dl_device)

                if (a_dl_device["HA_DeviceType"]
                        == "Hive_Device_BatteryLevel" and
                        "hive_sensor_batterylevel" in config_devices):
                    device_list_sensor.append(a_dl_device)

                if (a_dl_device["HA_DeviceType"] == "Hive_Device_Sensor" and
                        "hive_active_sensor" in config_devices):
                    device_list_sensor.append(a_dl_device)

                if (a_dl_device["HA_DeviceType"]
                        == "Hive_Device_Light_Mode" and
                        "hive_active_light_sensor" in config_devices):
                    device_list_sensor.append(a_dl_device)

                if (a_dl_device["HA_DeviceType"]
                        == "Hive_Device_Plug_Mode" and
                        "hive_active_plug_sensor" in config_devices):
                    device_list_sensor.append(a_dl_device)

        for a_dl_device in api_dl_climate:
            if "HA_DeviceType" in a_dl_device:
                if (a_dl_device["HA_DeviceType"] == "Heating" and
                        "hive_heating" in config_devices):
                    device_list_climate.append(a_dl_device)
                if (a_dl_device["HA_DeviceType"] == "HotWater" and
                        "hive_hotwater" in config_devices):
                    device_list_climate.append(a_dl_device)

        for a_dl_device in api_dl_light:
            if "HA_DeviceType" in a_dl_device:
                if (a_dl_device["HA_DeviceType"] == "Hive_Device_Light" and
                        "hive_active_light" in config_devices):
                    device_list_light.append(a_dl_device)

        for a_dl_device in api_dl_switch:
            if "HA_DeviceType" in a_dl_device:
                if (a_dl_device["HA_DeviceType"] == "Hive_Device_Plug" and
                        "hive_active_plug" in config_devices):
                    device_list_switch.append(a_dl_device)

    else:
        device_list_sensor = api_dl_sensor
        device_list_climate = api_dl_climate
        device_list_light = api_dl_light
        device_list_switch = api_dl_switch

    global HGO

    try:
        hsc_s.sensor = Pyhiveapi.Sensor()
        hsc_s.heating = Pyhiveapi.Heating()
        hsc_s.hotwater = Pyhiveapi.Hotwater()
        hsc_s.light = Pyhiveapi.Light()
        hsc_s.switch = Pyhiveapi.Switch()
        HGO = HiveObjects(hsc_s)
    except RuntimeError:
        return False

    if (len(device_list_sensor) > 0 or
            len(device_list_climate) > 0 or
            len(device_list_light) > 0 or
            len(device_list_switch) > 0):
        if len(device_list_sensor) > 0:
            load_platform(hass, 'sensor', DOMAIN, device_list_sensor)
        if len(device_list_climate) > 0:
            load_platform(hass, 'climate', DOMAIN, device_list_climate)
        if len(device_list_light) > 0:
            load_platform(hass, 'light', DOMAIN, device_list_light)
        if len(device_list_switch) > 0:
            load_platform(hass, 'switch', DOMAIN, device_list_switch)
        return True


class HiveObjects():
    """Initiate the HiveObjects class."""

    def __init__(self, hivesession):
        """Initialize HiveObjects."""
        self.hsc = hivesession
        self.nodeid = ""

    def fire_bus_event(self, node_id, device_type):
        """Fire off an event if some data has changed."""
        self.hsc.hass.bus.fire('Event_Hive_NewNodeData',
                               {device_type: node_id})

    def update_data(self, node_id, device_type):
        """Get the latest data from the Hive API - rate limiting."""
        self.hsc.core.hive_api_get_nodes_rl(node_id)

    def get_min_temperature(self, node_id, device_type):
        """Public get minimum target heating temperature possible."""
        return self.hsc.heating.min_temperature(node_id)

    def get_max_temperature(self, node_id, device_type):
        """Public get maximum target heating temperature possible."""
        return self.hsc.heating.max_temperature(node_id)

    def get_current_temperature(self, node_id, device_type):
        """Public get current heating temperature."""
        curtempret = self.hsc.heating.current_temperature(node_id)

        if curtempret != -1000:
            if node_id in self.hsc.data.min_max_data:
                if (self.hsc.data.min_max_data[node_id]['TodayDate'] !=
                        datetime.date(datetime.now())):
                    self.hsc.data.min_max_data[node_id]['TodayMin'] = 1000
                    self.hsc.data.min_max_data[node_id]['TodayMax'] = -1000
                    self.hsc.data.min_max_data[node_id]['TodayDate'] = \
                        datetime.date(datetime.now())

                if (curtempret <
                        self.hsc.data.min_max_data[node_id]['TodayMin']):
                    self.hsc.data.min_max_data[node_id]['TodayMin'] = \
                        curtempret

                if (curtempret >
                        self.hsc.data.min_max_data[node_id]['TodayMax']):
                    self.hsc.data.min_max_data[node_id]['TodayMax'] = \
                        curtempret

                if (curtempret <
                        self.hsc.data.min_max_data[node_id]['RestartMin']):
                    self.hsc.data.min_max_data[node_id]['RestartMin'] = \
                        curtempret

                if curtempret > \
                        self.hsc.data.min_max_data[node_id]['RestartMax']:
                    self.hsc.data.min_max_data[node_id]['RestartMax'] = \
                        curtempret
            else:
                current_node_max_min_data = {}
                current_node_max_min_data['TodayMin'] = curtempret
                current_node_max_min_data['TodayMax'] = curtempret
                current_node_max_min_data['TodayDate'] = \
                    datetime.date(datetime.now())
                current_node_max_min_data['RestartMin'] = curtempret
                current_node_max_min_data['RestartMax'] = curtempret
                self.hsc.data.min_max_data[node_id] = \
                    current_node_max_min_data

        else:
            curtempret = 0

        return curtempret

    def get_current_temp_sa(self, node_id, device_type):
        """Public get current heating temperature state attributes."""
        s_a = {}
        temp_current = 0
        temperature_target = 0
        temperature_difference = 0

        if node_id in self.hsc.data.min_max_data:
            s_a.update({"Today Min / Max":
                        str(self.hsc.data.min_max_data[node_id]
                            ['TodayMin']) + " °C" + " / "
                        + str(self.hsc.data.min_max_data[node_id]
                              ['TodayMax']) + " °C"})

            s_a.update({"Restart Min / Max":
                        str(self.hsc.data.min_max_data[node_id]
                            ['RestartMin']) + " °C" + " / "
                        + str(self.hsc.data.min_max_data[node_id]
                              ['RestartMax']) + " °C"})

        temp_current = self.get_current_temperature(node_id, device_type)
        temperature_target = self.get_target_temperature(node_id, device_type)

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

    def get_target_temperature(self, node_id, device_type):
        """Public get current heating target temperature."""
        return self.hsc.heating.get_target_temperature(node_id)

    def get_target_temp_sa(self, node_id, device_type):
        """Public get current heating target temperature state attributes."""
        state_attributes = {}
        self.nodeid = node_id

        return state_attributes

    def set_target_temperature(self, node_id, device_type, new_temperature):
        """Public set target heating temperature."""
        set_result = self.hsc.heating.set_target_temperature(node_id,
                                                             new_temperature)
        if set_result:
            self.fire_bus_event(node_id, device_type)

    def get_heating_state(self, node_id, device_type):
        """Public get current heating state."""
        return self.hsc.heating.get_state(node_id)

    def get_heating_state_sa(self, node_id, device_type):
        """Public get current heating state, state attributes."""
        state_attributes = {}

        snan = self.hsc.heating.get_schedule_now_next_later(node_id)
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
                    state_attributes.update({"Now": sa_string})

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
                    state_attributes.update({"Next": sa_string})

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
                    state_attributes.update({"Later": sa_string})
        else:
            state_attributes.update({"Schedule not active": ""})

        return state_attributes

    def get_heating_mode(self, node_id, device_type):
        """Public get current heating mode."""
        return self.hsc.heating.get_mode(node_id)

    def set_heating_mode(self, node_id, device_type, new_operation_mode):
        """Public set heating mode."""
        set_mode_success = self.hsc.heating.set_mode(node_id,
                                                     new_operation_mode)

        if set_mode_success:
            self.fire_bus_event(node_id, device_type)

    def get_heating_mode_sa(self, node_id, device_type):
        """Public get current heating mode state attributes."""
        return self.get_heating_state_sa(node_id, device_type)

    def get_heating_mode_list(self, node_id, device_type):
        """Public get possible heating modes list."""
        return self.hsc.heating.get_operation_modes(node_id)

    def get_heating_boost(self, node_id, device_type):
        """Public get heating boost status."""
        return self.hsc.heating.get_boost(node_id)

    def get_heating_boost_sa(self, node_id, device_type):
        """Public get heating boost status state attributes."""
        state_attributes = {}

        if self.get_heating_boost(node_id, device_type) == "ON":
            minsend = self.hsc.heating.get_boost_time(node_id)
            state_attributes.update({"Boost ends in":
                                     (str(minsend) + " minutes")})

        return state_attributes

    def get_hotwater_state(self, node_id, device_type):
        """Public get current hot water state."""
        return self.hsc.hotwater.get_state(node_id)

    def get_hotwater_state_sa(self, node_id, device_type):
        """Public get current hotwater state, state attributes."""
        state_attributes = {}

        snan = self.hsc.hotwater.get_schedule_now_next_later(node_id)
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
                    state_attributes.update({"Now": sa_string})

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
                    state_attributes.update({"Next": sa_string})
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
                    state_attributes.update({"Later": sa_string})
        else:
            state_attributes.update({"Schedule not active": ""})

        return state_attributes

    def get_hotwater_mode(self, node_id, device_type):
        """Public get current hot water mode."""
        return self.hsc.hotwater.get_mode(node_id)

    def get_hotwater_mode_sa(self, node_id, device_type):
        """Public get current hot water mode state attributes."""
        return self.get_hotwater_state_sa(node_id, device_type)

    def set_hotwater_mode(self, node_id, device_type, new_operation_mode):
        """Public set hot water mode ."""
        set_res = self.hsc.hotwater.set_mode(node_id, new_operation_mode)

        if set_res:
            self.fire_bus_event(node_id, device_type)

    def get_hotwater_mode_list(self, node_id, device_type):
        """Public get hot water possible modes list."""
        return self.hsc.hotwater.get_operation_modes(node_id)

    def get_hotwater_boost(self, node_id, device_type):
        """Public get current hot water boost status."""
        return self.hsc.hotwater.get_boost(node_id)

    def get_hotwater_boost_sa(self, node_id, device_type):
        """Public get current hot water bosst status state attributes."""
        state_attributes = {}

        if self.get_hotwater_boost(node_id, device_type) == "ON":
            endsin = self.hsc.hotwater.get_boost_time(node_id)
            state_attributes.update({"Boost ends in":
                                     (str(endsin) + " minutes")})

        return state_attributes

    def get_battery_level(self,
                          node_id,
                          node_name,
                          device_type,
                          node_device_type):
        """Public get node battery level."""
        if self.hsc.logging:
            _LOGGER.debug("Getting Battery Level for  %s", node_name)
        return self.hsc.sensor.battery_level(node_id)

    def get_light_state(self, node_id, node_name):
        """Public get current light state."""
        if self.hsc.logging:
            _LOGGER.debug("Getting status for  %s", node_name)
        return self.hsc.light.get_state(node_id)

    def get_light_min_color_temp(self, node_id, node_name):
        """Public get light minimum colour temperature."""
        if self.hsc.logging:
            _LOGGER.debug("Getting min colour temp for  %s", node_name)
        return self.hsc.light.get_min_colour_temp(node_id)

    def get_light_max_color_temp(self, node_id, node_name):
        """Public get light maximum colour temperature."""
        if self.hsc.logging:
            _LOGGER.debug("Getting max colour temp for  %s", node_name)
        return self.hsc.light.get_max_colour_temp(node_id)

    def get_light_brightness(self, node_id, node_name):
        """Public get current light brightness."""
        if self.hsc.logging:
            _LOGGER.debug("Getting brightness for  %s", node_name)
        return self.hsc.light.get_brightness(node_id)

    def get_light_color_temp(self, node_id, node_name):
        """Public get light current colour temperature."""
        if self.hsc.logging:
            _LOGGER.debug("Getting colour temperature for  %s", node_name)
        return self.hsc.light.get_color_temp(node_id)

    def set_light_turn_on(self,
                          node_id,
                          device_type,
                          node_name,
                          new_brightness,
                          new_color_temp):
        """Public set light turn on."""
        if self.hsc.logging:
            if new_brightness is None and new_color_temp is None:
                _LOGGER.debug("Switching %s light on", node_name)
            elif new_brightness is not None and new_color_temp is None:
                _LOGGER.debug("New Brightness is %s", new_brightness)
            elif new_brightness is None and new_color_temp is not None:
                _LOGGER.debug("New Colour Temprature is %s", new_color_temp)

        if new_brightness is not None:
            set_light_success = self.hsc.light.set_brightness(node_id,
                                                              new_brightness)
        elif new_color_temp is not None:
            set_light_success = self.hsc.light.set_colour_temp(node_id,
                                                               new_color_temp)
        else:
            set_light_success = self.hsc.light.turn_on(node_id)

        if set_light_success:
            self.fire_bus_event(node_id, device_type)

        return set_light_success

    def set_light_turn_off(self,
                           node_id,
                           device_type,
                           node_name):
        """Public set light turn off."""
        if self.hsc.logging:
            _LOGGER.debug("Switching %s light off", node_name)
        set_light_success = self.hsc.light.turn_off(node_id)

        if set_light_success:
            self.fire_bus_event(node_id, device_type)

        return set_light_success

    def get_smartplug_state(self, node_id, node_name):
        """Public get current smart plug state."""
        if self.hsc.logging:
            _LOGGER.debug("Getting status for %s", node_name)
        return self.hsc.switch.get_state(node_id)

    def get_smartplug_power_consumption(self, node_id, node_name):
        """Public get smart plug current power consumption."""
        if self.hsc.logging:
            _LOGGER.debug("Getting current power consumption for %s",
                          node_name)
        return self.hsc.switch.get_power_usage(node_id)

    def set_smartplug_turn_on(self,
                              node_id,
                              device_type,
                              node_name):
        """Public set smart plug turn on."""
        if self.hsc.logging:
            _LOGGER.debug("Switching %s on", node_name)
        set_switch_success = self.hsc.switch.turn_on(node_id)

        if set_switch_success:
            self.fire_bus_event(node_id, device_type)

        return set_switch_success

    def set_smartplug_turn_off(self,
                               node_id,
                               device_type,
                               node_name):
        """Public set smart plug turn off."""
        if self.hsc.logging:
            _LOGGER.debug("Switching %s off", node_name)
        set_switch_success = self.hsc.switch.turn_off(node_id)

        if set_switch_success:
            self.fire_bus_event(node_id, device_type)

        return set_switch_success

    def get_sensor_state(self,
                         node_id,
                         device_type,
                         node_name,
                         node_device_type):
        """Public get current sensor state."""
        if self.hsc.logging:
            _LOGGER.debug("Getting Sensor State for  %s", node_name)
        sensor_state_return = self.hsc.sensor.get_state(node_id,
                                                        node_device_type)

        if self.hsc.logging:
            _LOGGER.warning("Sensor state is %s", sensor_state_return)

        return sensor_state_return

    def get_device_mode(self,
                        node_id,
                        device_type,
                        node_name,
                        node_device_type):
        """Public get current device mode."""
        if self.hsc.logging:
            _LOGGER.debug("Getting Device Mode for  %s", node_name)

        hive_device_mode_return = self.hsc.sensor.get_mode(node_id)

        if self.hsc.logging:
            _LOGGER.warning("Device Mode is %s", hive_device_mode_return)

        return hive_device_mode_return
