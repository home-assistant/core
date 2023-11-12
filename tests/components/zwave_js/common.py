"""Provide common test tools for Z-Wave JS."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from zwave_js_server.model.node.data_model import NodeDataType

from homeassistant.components.zwave_js.helpers import (
    ZwaveValueMatcher,
    value_matches_matcher,
)

AIR_TEMPERATURE_SENSOR = "sensor.multisensor_6_air_temperature"
BATTERY_SENSOR = "sensor.multisensor_6_battery_level"
TAMPER_SENSOR = "binary_sensor.multisensor_6_tampering_product_cover_removed"
HUMIDITY_SENSOR = "sensor.multisensor_6_humidity"
POWER_SENSOR = "sensor.smart_plug_with_two_usb_ports_value_electric_consumed"
ENERGY_SENSOR = "sensor.smart_plug_with_two_usb_ports_value_electric_consumed_2"
VOLTAGE_SENSOR = "sensor.smart_plug_with_two_usb_ports_value_electric_consumed_3"
CURRENT_SENSOR = "sensor.smart_plug_with_two_usb_ports_value_electric_consumed_4"
SWITCH_ENTITY = "switch.smart_plug_with_two_usb_ports"
LOW_BATTERY_BINARY_SENSOR = "binary_sensor.multisensor_6_low_battery_level"
ENABLED_LEGACY_BINARY_SENSOR = "binary_sensor.z_wave_door_window_sensor_any"
DISABLED_LEGACY_BINARY_SENSOR = "binary_sensor.multisensor_6_any"
NOTIFICATION_MOTION_BINARY_SENSOR = "binary_sensor.multisensor_6_motion_detection"
NOTIFICATION_MOTION_SENSOR = "sensor.multisensor_6_home_security_motion_sensor_status"
INDICATOR_SENSOR = "sensor.z_wave_thermostat_indicator_value"
BASIC_LIGHT_ENTITY = "light.livingroomlight_basic"
PROPERTY_DOOR_STATUS_BINARY_SENSOR = (
    "binary_sensor.august_smart_lock_pro_3rd_gen_the_current_status_of_the_door"
)
CLIMATE_RADIO_THERMOSTAT_ENTITY = "climate.z_wave_thermostat"
CLIMATE_DANFOSS_LC13_ENTITY = "climate.living_connect_z_thermostat"
CLIMATE_EUROTRONICS_SPIRIT_Z_ENTITY = "climate.thermostatic_valve"
CLIMATE_FLOOR_THERMOSTAT_ENTITY = "climate.floor_thermostat"
CLIMATE_MAIN_HEAT_ACTIONNER = "climate.main_heat_actionner"
CLIMATE_AIDOO_HVAC_UNIT_ENTITY = "climate.aidoo_control_hvac_unit"
BULB_6_MULTI_COLOR_LIGHT_ENTITY = "light.bulb_6_multi_color"
EATON_RF9640_ENTITY = "light.allloaddimmer"
AEON_SMART_SWITCH_LIGHT_ENTITY = "light.smart_switch_6"
SCHLAGE_BE469_LOCK_ENTITY = "lock.touchscreen_deadbolt"
ZEN_31_ENTITY = "light.kitchen_under_cabinet_lights"
METER_ENERGY_SENSOR = "sensor.smart_switch_6_electric_consumed_kwh"
METER_VOLTAGE_SENSOR = "sensor.smart_switch_6_electric_consumed_v"
HUMIDIFIER_ADC_T3000_ENTITY = "humidifier.adc_t3000_humidifier"
DEHUMIDIFIER_ADC_T3000_ENTITY = "humidifier.adc_t3000_dehumidifier"

PROPERTY_ULTRAVIOLET = "Ultraviolet"


def replace_value_of_zwave_value(
    node_data: NodeDataType, matchers: list[ZwaveValueMatcher], new_value: Any
) -> NodeDataType:
    """Replace the value of a zwave value that matches the input matchers."""
    new_node_data = deepcopy(node_data)
    for value_data in new_node_data["values"]:
        for matcher in matchers:
            if value_matches_matcher(matcher, value_data):
                value_data["value"] = new_value

    return new_node_data
