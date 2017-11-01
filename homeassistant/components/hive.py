"""Hive Integration - Platform."""
import logging
from datetime import datetime
from homeassistant.helpers.discovery import load_platform

REQUIREMENTS = ['pyhiveapi==0.0.41']

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
    platform_data = HivePlatformData()
    logging = False
    hass = None
    core = None
    heating = None
    hotwater = None
    light = None
    sensor = None
    switch = None


HSC = HiveSession()


def fire_bus_event(node_id, device_type):
    """Fire off an event if some data has changed."""
    fire_events = True
    if fire_events:
        HSC.hass.bus.fire('Event_Hive_NewNodeData', {device_type: node_id})


def hive_api_get_nodes_rl(node_id, device_type):
    """Get latest data for Hive nodes - rate limiting."""
    nodes_updated = HSC.core.hive_api_get_nodes_rl(node_id)

    return nodes_updated


def p_get_heating_min_temp(node_id, device_type):
    """Get heating minimum target temperature."""
    heating_min_temp_return = HSC.heating.min_temperature(node_id)

    return heating_min_temp_return


def p_get_heating_max_temp(node_id, device_type):
    """Get heating maximum target temperature."""
    heating_max_temp_return = HSC.heating.max_temperature(node_id)

    return heating_max_temp_return


def p_get_heating_current_temp(node_id, device_type):
    """Get heating current temperature."""
    current_temp_return = HSC.heating.current_temperature(node_id)

    if current_temp_return != -1000:
        if node_id in HSC.platform_data.min_max_data:
            if (HSC.platform_data.min_max_data[node_id]['TodayDate'] !=
                    datetime.date(datetime.now())):
                HSC.platform_data.min_max_data[node_id]['TodayMin'] = 1000
                HSC.platform_data.min_max_data[node_id]['TodayMax'] = -1000
                HSC.platform_data.min_max_data[node_id]['TodayDate'] = \
                    datetime.date(datetime.now())

            if (current_temp_return <
                    HSC.platform_data.min_max_data[node_id]['TodayMin']):
                HSC.platform_data.min_max_data[node_id]['TodayMin'] = \
                    current_temp_return

            if (current_temp_return >
                    HSC.platform_data.min_max_data[node_id]['TodayMax']):
                HSC.platform_data.min_max_data[node_id]['TodayMax'] = \
                    current_temp_return

            if (current_temp_return <
                    HSC.platform_data.min_max_data[node_id]['RestartMin']):
                HSC.platform_data.min_max_data[node_id]['RestartMin'] = \
                    current_temp_return

            if current_temp_return > \
                    HSC.platform_data.min_max_data[node_id]['RestartMax']:
                HSC.platform_data.min_max_data[node_id]['RestartMax'] = \
                    current_temp_return
        else:
            current_node_max_min_data = {}
            current_node_max_min_data['TodayMin'] = current_temp_return
            current_node_max_min_data['TodayMax'] = current_temp_return
            current_node_max_min_data['TodayDate'] = \
                datetime.date(datetime.now())
            current_node_max_min_data['RestartMin'] = current_temp_return
            current_node_max_min_data['RestartMax'] = current_temp_return
            HSC.platform_data.min_max_data[node_id] = \
                current_node_max_min_data

    else:
        current_temp_return = 0

    return current_temp_return


def p_get_heating_current_temp_sa(node_id, device_type):
    """Get heating current temperature state attributes."""
    state_attributes = {}
    temperature_current = 0
    temperature_target = 0
    temperature_difference = 0

    if node_id in HSC.platform_data.min_max_data:
        state_attributes.update({"Today Min / Max":
                                 str(HSC.platform_data.min_max_data[node_id]
                                     ['TodayMin']) + " °C" + " / "
                                 + str(HSC.platform_data.min_max_data[node_id]
                                       ['TodayMax']) + " °C"})

        state_attributes.update({"Restart Min / Max":
                                 str(HSC.platform_data.min_max_data[node_id]
                                     ['RestartMin']) + " °C" + " / "
                                 + str(HSC.platform_data.min_max_data[node_id]
                                       ['RestartMax']) + " °C"})

    temperature_current = p_get_heating_current_temp(node_id, device_type)
    temperature_target = p_get_heating_target_temp(node_id, device_type)

    if temperature_target > temperature_current:
        temperature_difference = temperature_target - temperature_current

        state_attributes.update({"Current Temperature":
                                 temperature_current})
        state_attributes.update({"Target Temperature":
                                 temperature_target})
        state_attributes.update({"Temperature Difference":
                                 temperature_difference})
# State_Attributes.update({"Time to target": "01:30"})
    return state_attributes


def p_get_heating_target_temp(node_id, device_type):
    """Get heating target temperature."""
    heating_target_temp_return = HSC.heating.get_target_temperature(node_id)

    return heating_target_temp_return


def p_get_heating_target_temp_sa(node_id, device_type):
    """Get heating target temperature state attributes."""
    state_attributes = {}

    return state_attributes


def p_get_heating_state(node_id, device_type):
    """Get heating current state."""
    heating_state_return = HSC.heating.get_state(node_id)

    return heating_state_return


def p_get_heating_state_sa(node_id, device_type):
    """Get heating current state, state attributes."""
    state_attributes = {}

    snan = HSC.heating.get_schedule_now_next_later(node_id)
    if snan is not None:
        if 'now' in snan:
            if ('value' in snan["now"] and
                    'start' in snan["now"] and
                    'Start_DateTime' in snan["now"] and
                    'End_DateTime' in snan["now"] and
                    'target' in snan["now"]["value"]):
                now_target = str(snan["now"]["value"]["target"]) + " °C"
                now_start = snan["now"]["Start_DateTime"].strftime("%H:%M")
                now_end = snan["now"]["End_DateTime"].strftime("%H:%M")

                sa_string = (now_target
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
                    'target' in snan["next"]["value"]):
                next_target = str(snan["next"]["value"]["target"]) + " °C"
                next_start = snan["next"]["Start_DateTime"].strftime("%H:%M")
                next_end = snan["next"]["End_DateTime"].strftime("%H:%M")

                sa_string = (next_target
                             + " : "
                             + next_start
                             + " - "
                             + next_end)
                state_attributes.update({"Next": sa_string})

        if 'later' in snan:
            if ('value' in snan["later"] and
                    'start' in snan["later"] and
                    'Start_DateTime' in snan["later"] and
                    'End_DateTime' in snan["later"] and
                    'target' in snan["later"]["value"]):
                later_target = str(snan["later"]["value"]["target"]) + " °C"
                later_start = snan["later"]["Start_DateTime"].strftime("%H:%M")
                later_end = snan["later"]["End_DateTime"].strftime("%H:%M")

                sa_string = (later_target
                             + " : "
                             + later_start
                             + " - "
                             + later_end)
                state_attributes.update({"Later": sa_string})
    else:
        state_attributes.update({"Schedule not active": ""})

    return state_attributes


def p_get_heating_mode(node_id, device_type):
    """Get heating current mode."""
    mode_return = HSC.heating.get_mode(node_id)

    return mode_return


def p_get_heating_mode_sa(node_id, device_type):
    """Get heating current mode state attributes."""
    state_attributes = p_get_heating_state_sa(node_id, device_type)

    return state_attributes


def p_get_heating_operation_modes(node_id, device_type):
    """Get heating list of possible modes."""
    hive_heating_operation_list = HSC.heating.get_operation_modes(node_id)

    return hive_heating_operation_list


def p_get_heating_boost(node_id, device_type):
    """Get heating boost current status."""
    heating_boost_return = HSC.heating.get_boost(node_id)

    return heating_boost_return


def p_get_heating_boost_sa(node_id, device_type):
    """Get heating boost current status state attributes."""
    state_attributes = {}

    if p_get_heating_boost(node_id, device_type) == "ON":
        state_attributes.update({"Boost ends in":
                                 (str(HSC.heating.get_boost_time(node_id))
                                  + " minutes")})

    return state_attributes


def p_get_hotwater_mode(node_id, device_type):
    """Get hot water current mode."""
    hotwater_mode_return = HSC.hotwater.get_mode(node_id)

    return hotwater_mode_return


def p_get_hotwater_mode_sa(node_id, device_type):
    """Get hot water current mode state attributes."""
    state_attributes = p_get_hotwater_state_sa(node_id, device_type)

    return state_attributes


def p_get_hotwater_operation_modes(node_id, device_type):
    """Get heating list of possible modes."""
    hive_hotwater_operation_list = HSC.hotwater.get_operation_modes(node_id)

    return hive_hotwater_operation_list


def p_get_hotwater_boost(node_id, device_type):
    """Get hot water current boost status."""
    hotwater_boost_return = HSC.hotwater.get_boost(node_id)

    return hotwater_boost_return


def p_get_hotwater_boost_sa(node_id, device_type):
    """Get hot water current boost status state attributes."""
    state_attributes = {}

    if p_get_hotwater_boost(node_id, device_type) == "ON":
        state_attributes.update({"Boost ends in":
                                 (str(HSC.hotwater.get_boost_time(node_id))
                                  + " minutes")})

    return state_attributes


def p_get_hotwater_state(node_id, device_type):
    """Get hot water current state."""
    state_return = HSC.hotwater.get_state(node_id)

    return state_return


def p_get_hotwater_state_sa(node_id, device_type):
    """Get hot water current status state attributes."""
    state_attributes = {}

    snan = HSC.hotwater.get_schedule_now_next_later(node_id)
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
                next_start = snan["next"]["Start_DateTime"].strftime("%H:%M")
                next_end = snan["next"]["End_DateTime"].strftime("%H:%M")

                sa_string = (next_status
                             + " : "
                             + next_start
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


def p_get_device_battery_level(node_id,
                               node_name,
                               device_type,
                               node_device_type):
    """Get device battery level."""
    battery_level_return = HSC.sensor.battery_level(node_id)

    return battery_level_return


def p_get_light_state(node_id):
    """Get light current state."""
    light_state_return = HSC.light.get_state(node_id)

    return light_state_return


def p_get_light_brightness(node_id):
    """Get light current brightness."""
    light_brightness_return = HSC.light.get_brightness(node_id)

    return light_brightness_return


def p_get_light_min_color_temp(node_id):
    """Get light minimum colour temperature."""
    light_min_colour_temp_return = HSC.light.get_min_colour_temp(node_id)

    return light_min_colour_temp_return


def p_get_light_max_color_temp(node_id):
    """Get light maximum colour temperature."""
    light_max_colour_temp_return = HSC.light.get_max_colour_temp(node_id)

    return light_max_colour_temp_return


def p_get_light_color_temp(node_id):
    """Get light current colour temperature."""
    light_colour_temp_return = HSC.light.get_color_temp(node_id)

    return light_colour_temp_return


def p_get_smartplug_state(node_id):
    """Get smart plug current state."""
    switch_state_return = HSC.switch.get_state(node_id)

    return switch_state_return


def p_get_smartplug_power_usage(node_id):
    """Get smart plug current power usage."""
    switch_spower_usage_return = HSC.switch.get_power_usage(node_id)

    return switch_spower_usage_return


def p_get_hive_sensor_state(node_id,
                            device_type,
                            node_name,
                            node_device_type):
    """Get sensor current state."""
    sensor_state_return = HSC.sensor.get_state(node_id, node_device_type)

    if HSC.logging:
        _LOGGER.warning("Sensor state is %s", sensor_state_return)

    return sensor_state_return


def p_get_hive_device_mode(node_id, device_type, node_name, node_device_type):
    """Get device current mode."""
    hive_device_mode_return = HSC.sensor.get_mode(node_id)

    if HSC.logging:
        _LOGGER.warning("Device Mode is %s", hive_device_mode_return)

    return hive_device_mode_return


def p_hive_set_temperature(node_id, device_type, new_temperature):
    """Set heating target temperature."""
    set_temp_success = HSC.heating.set_target_temperature(node_id,
                                                          new_temperature)

    if set_temp_success:
        fire_bus_event(node_id, device_type)

    return set_temp_success


def p_hive_set_heating_mode(node_id, device_type, new_mode):
    """Set heating mode."""
    set_mode_success = HSC.heating.set_mode(node_id, new_mode)

    if set_mode_success:
        fire_bus_event(node_id, device_type)

    return set_mode_success


def p_hive_set_hotwater_mode(node_id, device_type, new_mode):
    """Set hot water mode."""
    set_mode_success = HSC.hotwater.set_mode(node_id, new_mode)

    if set_mode_success:
        fire_bus_event(node_id, device_type)

    return set_mode_success


def p_hive_set_light_turn_on(node_id, device_type, new_brightness,
                             new_color_temp):
    """Set light to turn on."""
    if new_brightness is not None:
        set_light_success = HSC.light.set_brightness(node_id, new_brightness)
    elif new_color_temp is not None:
        set_light_success = HSC.light.set_colour_temp(node_id, new_color_temp)
    else:
        set_light_success = HSC.light.turn_on(node_id)

    if set_light_success:
        fire_bus_event(node_id, device_type)

    return set_light_success


def p_hive_set_light_turn_off(node_id, device_type):
    """Set light to turn off."""
    set_light_success = HSC.light.turn_off(node_id)

    if set_light_success:
        fire_bus_event(node_id, device_type)

    return set_light_success


def p_hive_set_smartplug_turn_on(node_id, device_type):
    """Set smart plug to turn on."""
    set_switch_success = HSC.switch.turn_on(node_id)

    if set_switch_success:
        fire_bus_event(node_id, device_type)

    return set_switch_success


def p_hive_set_smartplug_turn_off(node_id, device_type):
    """Set smart plug to turn off."""
    set_switch_success = HSC.switch.turn_off(node_id)

    if set_switch_success:
        fire_bus_event(node_id, device_type)

    return set_switch_success


def setup(hass, config):
    """Setup the Hive platform."""
    from pyhiveapi import Pyhiveapi
    HSC.core = Pyhiveapi()

    HSC.hass = hass

    HSC.username = None
    HSC.password = None
    api_mins_between_updates = 2
    api_dl_all = {}
    api_dl_sensor = []
    api_dl_climate = []
    api_dl_light = []
    api_dl_switch = []

    hive_config = config[DOMAIN]

    if "username" in hive_config and "password" in hive_config:
        HSC.username = config[DOMAIN]['username']
        HSC.password = config[DOMAIN]['password']
    else:
        _LOGGER.error("Missing UserName or Password in config")

    if "minutes_between_updates" in hive_config:
        api_mins_between_updates = config[DOMAIN]['minutes_between_updates']
    else:
        api_mins_between_updates = 2

    if "logging" in hive_config:
        if config[DOMAIN]['logging']:
            HSC.logging = True
            _LOGGER.warning("Logging is Enabled")
        else:
            HSC.logging = False
    else:
        HSC.logging = False

    if HSC.username is None or HSC.password is None:
        _LOGGER.error("Missing UserName or Password in Hive Session details")
    else:

        api_dl_all = HSC.core.initialise_api(HSC.username,
                                             HSC.password,
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
        HGO = HiveObjects()
    except RuntimeError:
        return False

    if (len(device_list_sensor) > 0 or
            len(device_list_climate) > 0 or
            len(device_list_light) > 0 or
            len(device_list_switch) > 0):
        if len(device_list_sensor) > 0:
            HSC.sensor = Pyhiveapi.Sensor()
            load_platform(hass, 'sensor', DOMAIN, device_list_sensor)
        if len(device_list_climate) > 0:
            HSC.heating = Pyhiveapi.Heating()
            HSC.hotwater = Pyhiveapi.Hotwater()
            load_platform(hass, 'climate', DOMAIN, device_list_climate)
        if len(device_list_light) > 0:
            HSC.light = Pyhiveapi.Light()
            load_platform(hass, 'light', DOMAIN, device_list_light)
        if len(device_list_switch) > 0:
            HSC.switch = Pyhiveapi.Switch()
            load_platform(hass, 'switch', DOMAIN, device_list_switch)
        return True


class HiveObjects():
    """Initiate the HiveObjects class to expose platform methods."""

    def __init__(self):
        """Initialize HiveObjects."""
        self.self_node_id = ""

    def update_data(self, node_id, device_type):
        """Get the latest data from the Hive API - rate limiting."""
        self.self_node_id = node_id
        hive_api_get_nodes_rl(node_id, device_type)

    def get_min_temperature(self, node_id, device_type):
        """Public get minimum target heating temperature possible."""
        self.self_node_id = node_id
        return p_get_heating_min_temp(node_id, device_type)

    def get_max_temperature(self, node_id, device_type):
        """Public get maximum target heating temperature possible."""
        self.self_node_id = node_id
        return p_get_heating_max_temp(node_id, device_type)

    def get_current_temperature(self, node_id, device_type):
        """Public get current heating temperature."""
        self.self_node_id = node_id
        return p_get_heating_current_temp(node_id, device_type)

    def get_current_temp_sa(self, node_id, device_type):
        """Public get current heating temperature state attributes."""
        self.self_node_id = node_id
        return p_get_heating_current_temp_sa(node_id, device_type)

    def get_target_temperature(self, node_id, device_type):
        """Public get current heating target temperature."""
        self.self_node_id = node_id
        return p_get_heating_target_temp(node_id, device_type)

    def get_target_temp_sa(self, node_id, device_type):
        """Public get current heating target temperature state attributes."""
        self.self_node_id = node_id
        return p_get_heating_target_temp_sa(node_id, device_type)

    def set_target_temperature(self, node_id, device_type, new_temperature):
        """Public set target heating temperature."""
        self.self_node_id = node_id
        if new_temperature is not None:
            p_hive_set_temperature(node_id, device_type, new_temperature)

    def get_heating_state(self, node_id, device_type):
        """Public get current heating state."""
        self.self_node_id = node_id
        return p_get_heating_state(node_id, device_type)

    def get_heating_state_sa(self, node_id, device_type):
        """Public get current heating state, state attributes."""
        self.self_node_id = node_id
        return p_get_heating_state_sa(node_id, device_type)

    def get_heating_mode(self, node_id, device_type):
        """Public get current heating mode."""
        self.self_node_id = node_id
        return p_get_heating_mode(node_id, device_type)

    def set_heating_mode(self, node_id, device_type, new_operation_mode):
        """Public set heating mode."""
        self.self_node_id = node_id
        p_hive_set_heating_mode(node_id, device_type, new_operation_mode)

    def get_heating_mode_sa(self, node_id, device_type):
        """Public get current heating mode state attributes."""
        self.self_node_id = node_id
        return p_get_heating_mode_sa(node_id, device_type)

    def get_heating_mode_list(self, node_id, device_type):
        """Public get possible heating modes list."""
        self.self_node_id = node_id
        return p_get_heating_operation_modes(node_id, device_type)

    def get_heating_boost(self, node_id, device_type):
        """Public get heating boost status."""
        self.self_node_id = node_id
        return p_get_heating_boost(node_id, device_type)

    def get_heating_boost_sa(self, node_id, device_type):
        """Public get heating boost status state attributes."""
        self.self_node_id = node_id
        return p_get_heating_boost_sa(node_id, device_type)

    def get_hotwater_state(self, node_id, device_type):
        """Public get current hot water state."""
        self.self_node_id = node_id
        return p_get_hotwater_state(node_id, device_type)

    def get_hotwater_state_sa(self, node_id, device_type):
        """Public get current hotwater state, state attributes."""
        self.self_node_id = node_id
        return p_get_hotwater_state_sa(node_id, device_type)

    def get_hotwater_mode(self, node_id, device_type):
        """Public get current hot water mode."""
        self.self_node_id = node_id
        return p_get_hotwater_mode(node_id, device_type)

    def get_hotwater_mode_sa(self, node_id, device_type):
        """Public get current hot water mode state attributes."""
        self.self_node_id = node_id
        return p_get_hotwater_mode_sa(node_id, device_type)

    def set_hotwater_mode(self, node_id, device_type, new_operation_mode):
        """Public set hot water mode ."""
        self.self_node_id = node_id
        p_hive_set_hotwater_mode(node_id, device_type, new_operation_mode)

    def get_hotwater_mode_list(self, node_id, device_type):
        """Public get hot water possible modes list."""
        self.self_node_id = node_id
        return p_get_hotwater_operation_modes(node_id, device_type)

    def get_hotwater_boost(self, node_id, device_type):
        """Public get current hot water boost status."""
        self.self_node_id = node_id
        return p_get_hotwater_boost(node_id, device_type)

    def get_hotwater_boost_sa(self, node_id, device_type):
        """Public get current hot water bosst status state attributes."""
        self.self_node_id = node_id
        return p_get_hotwater_boost_sa(node_id, device_type)

    def get_battery_level(self,
                          node_id,
                          node_name,
                          device_type,
                          node_device_type):
        """Public get node battery level."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.debug("Getting Battery Level for  %s", node_name)
        return p_get_device_battery_level(node_id,
                                          node_name,
                                          device_type,
                                          node_device_type)

    def get_light_state(self, node_id, node_name):
        """Public get current light state."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.debug("Getting status for  %s", node_name)
        return p_get_light_state(node_id)

    def get_light_min_color_temp(self, node_id, node_name):
        """Public get light minimum colour temperature."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.debug("Getting min colour temp for  %s", node_name)
        return p_get_light_min_color_temp(node_id)

    def get_light_max_color_temp(self, node_id, node_name):
        """Public get light maximum colour temperature."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.debug("Getting max colour temp for  %s", node_name)
        return p_get_light_max_color_temp(node_id)

    def get_light_brightness(self, node_id, node_name):
        """Public get current light brightness."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.debug("Getting brightness for  %s", node_name)
        return p_get_light_brightness(node_id)

    def get_light_color_temp(self, node_id, node_name):
        """Public get light current colour temperature."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.debug("Getting colour temperature for  %s", node_name)
        return p_get_light_color_temp(node_id)

    def set_light_turn_on(self,
                          node_id,
                          device_type,
                          node_name,
                          new_brightness,
                          new_color_temp):
        """Public set light turn on."""
        self.self_node_id = node_id
        if HSC.logging:
            if new_brightness is None and new_color_temp is None:
                _LOGGER.debug("Switching %s light on", node_name)
            elif new_brightness is not None and new_color_temp is None:
                _LOGGER.debug("New Brightness is %s", new_brightness)
            elif new_brightness is None and new_color_temp is not None:
                _LOGGER.debug("New Colour Temprature is %s", new_color_temp)
        return p_hive_set_light_turn_on(node_id,
                                        device_type,
                                        new_brightness,
                                        new_color_temp)

    def set_light_turn_off(self,
                           node_id,
                           device_type,
                           node_name):
        """Public set light turn off."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.debug("Switching %s light off", node_name)
        return p_hive_set_light_turn_off(node_id, device_type)

    def get_smartplug_state(self, node_id, node_name):
        """Public get current smart plug state."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.debug("Getting status for %s", node_name)
        return p_get_smartplug_state(node_id)

    def get_smartplug_power_consumption(self, node_id, node_name):
        """Public get smart plug current power consumption."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.debug("Getting current power consumption for %s",
                          node_name)
        return p_get_smartplug_power_usage(node_id)

    def set_smartplug_turn_on(self,
                              node_id,
                              device_type,
                              node_name):
        """Public set smart plug turn on."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.debug("Switching %s on", node_name)
        return p_hive_set_smartplug_turn_on(node_id, device_type)

    def set_smartplug_turn_off(self,
                               node_id,
                               device_type,
                               node_name):
        """Public set smart plug turn off."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.debug("Switching %s off", node_name)
        return p_hive_set_smartplug_turn_off(node_id, device_type)

    def get_sensor_state(self,
                         node_id,
                         device_type,
                         node_name,
                         node_device_type):
        """Public get current sensor state."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.debug("Getting Sensor State for  %s", node_name)
        return p_get_hive_sensor_state(node_id,
                                       device_type,
                                       node_name,
                                       node_device_type)

    def get_device_mode(self,
                        node_id,
                        device_type,
                        node_name,
                        node_device_type):
        """Public get current device mode."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.debug("Getting Device Mode for  %s", node_name)
        return p_get_hive_device_mode(node_id,
                                      device_type,
                                      node_name,
                                      node_device_type)
