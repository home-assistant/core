"""Constants for the Tuya integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from tuya_iot import TuyaCloudOpenAPIEndpoint

from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_AQI,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_DATE,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_NITROGEN_DIOXIDE,
    DEVICE_CLASS_NITROGEN_MONOXIDE,
    DEVICE_CLASS_NITROUS_OXIDE,
    DEVICE_CLASS_OZONE,
    DEVICE_CLASS_PM1,
    DEVICE_CLASS_PM10,
    DEVICE_CLASS_PM25,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_SULPHUR_DIOXIDE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_CURRENT_MILLIAMPERE,
    ELECTRIC_POTENTIAL_MILLIVOLT,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_KILO_WATT,
    POWER_WATT,
    PRESSURE_BAR,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_MBAR,
    PRESSURE_PA,
    PRESSURE_PSI,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    VOLUME_CUBIC_FEET,
    VOLUME_CUBIC_METERS,
)

DOMAIN = "tuya"

CONF_AUTH_TYPE = "auth_type"
CONF_PROJECT_TYPE = "tuya_project_type"
CONF_ENDPOINT = "endpoint"
CONF_ACCESS_ID = "access_id"
CONF_ACCESS_SECRET = "access_secret"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_COUNTRY_CODE = "country_code"
CONF_APP_TYPE = "tuya_app_type"

DEVICE_CLASS_TUYA_BASIC_ANTI_FLICKR = "tuya__basic_anti_flickr"
DEVICE_CLASS_TUYA_BASIC_NIGHTVISION = "tuya__basic_nightvision"
DEVICE_CLASS_TUYA_DECIBEL_SENSITIVITY = "tuya__decibel_sensitivity"
DEVICE_CLASS_TUYA_IPC_WORK_MODE = "tuya__ipc_work_mode"
DEVICE_CLASS_TUYA_LED_TYPE = "tuya__led_type"
DEVICE_CLASS_TUYA_LIGHT_MODE = "tuya__light_mode"
DEVICE_CLASS_TUYA_MOTION_SENSITIVITY = "tuya__motion_sensitivity"
DEVICE_CLASS_TUYA_RECORD_MODE = "tuya__record_mode"
DEVICE_CLASS_TUYA_RELAY_STATUS = "tuya__relay_status"
DEVICE_CLASS_TUYA_STATUS = "tuya__status"

TUYA_DISCOVERY_NEW = "tuya_discovery_new"
TUYA_HA_SIGNAL_UPDATE_ENTITY = "tuya_entry_update"

TUYA_RESPONSE_CODE = "code"
TUYA_RESPONSE_RESULT = "result"
TUYA_RESPONSE_MSG = "msg"
TUYA_RESPONSE_SUCCESS = "success"
TUYA_RESPONSE_PLATFORM_URL = "platform_url"

TUYA_SMART_APP = "tuyaSmart"
SMARTLIFE_APP = "smartlife"

PLATFORMS = [
    "binary_sensor",
    "camera",
    "climate",
    "cover",
    "fan",
    "humidifier",
    "light",
    "number",
    "scene",
    "select",
    "sensor",
    "siren",
    "switch",
    "vacuum",
]


class WorkMode(str, Enum):
    """Work modes."""

    COLOUR = "colour"
    MUSIC = "music"
    SCENE = "scene"
    WHITE = "white"


class DPCode(str, Enum):
    """Device Property Codes used by Tuya.

    https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
    """

    ALARM_SWITCH = "alarm_switch"  # Alarm switch
    ALARM_TIME = "alarm_time"  # Alarm time
    ALARM_VOLUME = "alarm_volume"  # Alarm volume
    ANGLE_HORIZONTAL = "angle_horizontal"
    ANGLE_VERTICAL = "angle_vertical"
    ANION = "anion"  # Ionizer unit
    BASIC_ANTI_FLICKER = "basic_anti_flicker"
    BASIC_DEVICE_VOLUME = "basic_device_volume"
    BASIC_FLIP = "basic_flip"
    BASIC_INDICATOR = "basic_indicator"
    BASIC_NIGHTVISION = "basic_nightvision"
    BASIC_OSD = "basic_osd"
    BASIC_PRIVATE = "basic_private"
    BASIC_WDR = "basic_wdr"
    BATTERY_PERCENTAGE = "battery_percentage"  # Battery percentage
    BATTERY_STATE = "battery_state"  # Battery state
    BATTERY_VALUE = "battery_value"  # Battery value
    BRIGHT_CONTROLLER = "bright_controller"
    BRIGHT_STATE = "bright_state"  # Brightness status
    BRIGHT_VALUE = "bright_value"  # Brightness
    BRIGHT_VALUE_1 = "bright_value_1"
    BRIGHT_VALUE_2 = "bright_value_2"
    BRIGHT_VALUE_3 = "bright_value_3"
    BRIGHT_VALUE_V2 = "bright_value_v2"
    BRIGHTNESS_MAX_1 = "brightness_max_1"
    BRIGHTNESS_MAX_2 = "brightness_max_2"
    BRIGHTNESS_MAX_3 = "brightness_max_3"
    BRIGHTNESS_MIN_1 = "brightness_min_1"
    BRIGHTNESS_MIN_2 = "brightness_min_2"
    BRIGHTNESS_MIN_3 = "brightness_min_3"
    C_F = "c_f"  # Temperature unit switching
    CH2O_STATE = "ch2o_state"
    CH2O_VALUE = "ch2o_value"
    CH4_SENSOR_STATE = "ch4_sensor_state"
    CH4_SENSOR_VALUE = "ch4_sensor_value"
    CHILD_LOCK = "child_lock"  # Child lock
    CO_STATE = "co_state"
    CO_STATUS = "co_status"
    CO_VALUE = "co_value"
    CO2_STATE = "co2_state"
    CO2_VALUE = "co2_value"  # CO2 concentration
    COLOR_DATA_V2 = "color_data_v2"
    COLOUR_DATA_HSV = "colour_data_hsv"  # Colored light mode
    COLOUR_DATA = "colour_data"  # Colored light mode
    COLOUR_DATA_V2 = "colour_data_v2"  # Colored light mode
    CONCENTRATION_SET = "concentration_set"  # Concentration setting
    CONTROL = "control"
    CONTROL_2 = "control_2"
    CONTROL_3 = "control_3"
    CRY_DETECTION_SWITCH = "cry_detection_switch"
    CUP_NUMBER = "cup_number"  # NUmber of cups
    CUR_CURRENT = "cur_current"  # Actual current
    CUR_POWER = "cur_power"  # Actual power
    CUR_VOLTAGE = "cur_voltage"  # Actual voltage
    DECIBEL_SENSITIVITY = "decibel_sensitivity"
    DECIBEL_SWITCH = "decibel_switch"
    DEHUMIDITY_SET_VALUE = "dehumidify_set_value"
    DO_NOT_DISTURB = "do_not_disturb"
    DOORCONTACT_STATE = "doorcontact_state"  # Status of door window sensor
    DOORCONTACT_STATE_2 = "doorcontact_state_2"
    DOORCONTACT_STATE_3 = "doorcontact_state_3"
    ELECTRICITY_LEFT = "electricity_left"
    FAN_DIRECTION = "fan_direction"  # Fan direction
    FAN_SPEED_ENUM = "fan_speed_enum"  # Speed mode
    FAN_SPEED_PERCENT = "fan_speed_percent"  # Stepless speed
    FAR_DETECTION = "far_detection"
    FILTER_RESET = "filter_reset"  # Filter (cartridge) reset
    FLOODLIGHT_LIGHTNESS = "floodlight_lightness"
    FLOODLIGHT_SWITCH = "floodlight_switch"
    GAS_SENSOR_STATE = "gas_sensor_state"
    GAS_SENSOR_STATUS = "gas_sensor_status"
    GAS_SENSOR_VALUE = "gas_sensor_value"
    HUMIDITY_CURRENT = "humidity_current"  # Current humidity
    HUMIDITY_SET = "humidity_set"  # Humidity setting
    HUMIDITY_VALUE = "humidity_value"  # Humidity
    IPC_WORK_MODE = "ipc_work_mode"
    LED_TYPE_1 = "led_type_1"
    LED_TYPE_2 = "led_type_2"
    LED_TYPE_3 = "led_type_3"
    LEVEL = "level"
    LIGHT = "light"  # Light
    LIGHT_MODE = "light_mode"
    LOCK = "lock"  # Lock / Child lock
    MATERIAL = "material"  # Material
    MODE = "mode"  # Working mode / Mode
    MOTION_RECORD = "motion_record"
    MOTION_SENSITIVITY = "motion_sensitivity"
    MOTION_SWITCH = "motion_switch"  # Motion switch
    MOTION_TRACKING = "motion_tracking"
    MUFFLING = "muffling"  # Muffling
    NEAR_DETECTION = "near_detection"
    PAUSE = "pause"
    PERCENT_CONTROL = "percent_control"
    PERCENT_CONTROL_2 = "percent_control_2"
    PERCENT_CONTROL_3 = "percent_control_3"
    PERCENT_STATE = "percent_state"
    PERCENT_STATE_2 = "percent_state_2"
    PERCENT_STATE_3 = "percent_state_3"
    PIR = "pir"  # Motion sensor
    PM1 = "pm1"
    PM10 = "pm10"
    PM25_STATE = "pm25_state"
    PM25_VALUE = "pm25_value"
    POWDER_SET = "powder_set"  # Powder
    POWER_GO = "power_go"
    PRESENCE_STATE = "presence_state"
    PRESSURE_STATE = "pressure_state"
    PRESSURE_VALUE = "pressure_value"
    PUMP_RESET = "pump_reset"  # Water pump reset
    RECORD_MODE = "record_mode"
    RECORD_SWITCH = "record_switch"  # Recording switch
    RELAY_STATUS = "relay_status"
    SEEK = "seek"
    SENSITIVITY = "sensitivity"  # Sensitivity
    SENSOR_HUMIDITY = "sensor_humidity"
    SENSOR_TEMPERATURE = "sensor_temperature"
    SHAKE = "shake"  # Oscillating
    SHOCK_STATE = "shock_state"  # Vibration status
    SIREN_SWITCH = "siren_switch"
    SITUATION_SET = "situation_set"
    SMOKE_SENSOR_STATE = "smoke_sensor_state"
    SMOKE_SENSOR_STATUS = "smoke_sensor_status"
    SMOKE_SENSOR_VALUE = "smoke_sensor_value"
    SOS = "sos"  # Emergency State
    SOS_STATE = "sos_state"  # Emergency mode
    SPEED = "speed"  # Speed level
    START = "start"  # Start
    STATUS = "status"
    SUCTION = "suction"
    SWING = "swing"  # Swing mode
    SWITCH = "switch"  # Switch
    SWITCH_1 = "switch_1"  # Switch 1
    SWITCH_2 = "switch_2"  # Switch 2
    SWITCH_3 = "switch_3"  # Switch 3
    SWITCH_4 = "switch_4"  # Switch 4
    SWITCH_5 = "switch_5"  # Switch 5
    SWITCH_6 = "switch_6"  # Switch 6
    SWITCH_BACKLIGHT = "switch_backlight"  # Backlight switch
    SWITCH_CHARGE = "switch_charge"
    SWITCH_CONTROLLER = "switch_controller"
    SWITCH_DISTURB = "switch_disturb"
    SWITCH_HORIZONTAL = "switch_horizontal"  # Horizontal swing flap switch
    SWITCH_LED = "switch_led"  # Switch
    SWITCH_LED_1 = "switch_led_1"
    SWITCH_LED_2 = "switch_led_2"
    SWITCH_LED_3 = "switch_led_3"
    SWITCH_NIGHT_LIGHT = "switch_night_light"
    SWITCH_SAVE_ENERGY = "switch_save_energy"
    SWITCH_SPRAY = "switch_spray"  # Spraying switch
    SWITCH_USB1 = "switch_usb1"  # USB 1
    SWITCH_USB2 = "switch_usb2"  # USB 2
    SWITCH_USB3 = "switch_usb3"  # USB 3
    SWITCH_USB4 = "switch_usb4"  # USB 4
    SWITCH_USB5 = "switch_usb5"  # USB 5
    SWITCH_USB6 = "switch_usb6"  # USB 6
    SWITCH_VERTICAL = "switch_vertical"  # Vertical swing flap switch
    SWITCH_VOICE = "switch_voice"  # Voice switch
    TEMP_BOILING_C = "temp_boiling_c"
    TEMP_BOILING_F = "temp_boiling_f"
    TEMP_CONTROLLER = "temp_controller"
    TEMP_CURRENT = "temp_current"  # Current temperature in °C
    TEMP_CURRENT_F = "temp_current_f"  # Current temperature in °F
    TEMP_SET = "temp_set"  # Set the temperature in °C
    TEMP_SET_F = "temp_set_f"  # Set the temperature in °F
    TEMP_UNIT_CONVERT = "temp_unit_convert"  # Temperature unit switching
    TEMP_VALUE = "temp_value"  # Color temperature
    TEMP_VALUE_V2 = "temp_value_v2"
    TEMPER_ALARM = "temper_alarm"  # Tamper alarm
    UV = "uv"  # UV sterilization
    VA_BATTERY = "va_battery"
    VA_HUMIDITY = "va_humidity"
    VA_TEMPERATURE = "va_temperature"
    VOC_STATE = "voc_state"
    VOC_VALUE = "voc_value"
    VOICE_SWITCH = "voice_switch"
    VOLUME_SET = "volume_set"
    WARM = "warm"  # Heat preservation
    WARM_TIME = "warm_time"  # Heat preservation time
    WATER_RESET = "water_reset"  # Resetting of water usage days
    WATER_SET = "water_set"  # Water level
    WATERSENSOR_STATE = "watersensor_state"
    WET = "wet"  # Humidification
    WIRELESS_BATTERYLOCK = "wireless_batterylock"
    WIRELESS_ELECTRICITY = "wireless_electricity"
    WORK_MODE = "work_mode"  # Working mode
    WORK_POWER = "work_power"


@dataclass
class UnitOfMeasurement:
    """Describes a unit of measurement."""

    unit: str
    device_classes: set[str]

    aliases: set[str] = field(default_factory=set)
    conversion_unit: str | None = None
    conversion_fn: Callable[[float], float] | None = None


# A tuple of available units of measurements we can work with.
# Tuya's devices aren't consistent in UOM use, thus this provides
# a list of aliases for units and possible conversions we can do
# to make them compatible with our model.
UNITS = (
    UnitOfMeasurement(
        unit="",
        aliases={" "},
        device_classes={
            DEVICE_CLASS_AQI,
            DEVICE_CLASS_DATE,
            DEVICE_CLASS_MONETARY,
            DEVICE_CLASS_TIMESTAMP,
        },
    ),
    UnitOfMeasurement(
        unit=PERCENTAGE,
        aliases={"pct", "percent"},
        device_classes={
            DEVICE_CLASS_BATTERY,
            DEVICE_CLASS_HUMIDITY,
            DEVICE_CLASS_POWER_FACTOR,
        },
    ),
    UnitOfMeasurement(
        unit=CONCENTRATION_PARTS_PER_MILLION,
        device_classes={
            DEVICE_CLASS_CO,
            DEVICE_CLASS_CO2,
        },
    ),
    UnitOfMeasurement(
        unit=CONCENTRATION_PARTS_PER_BILLION,
        device_classes={
            DEVICE_CLASS_CO,
            DEVICE_CLASS_CO2,
        },
        conversion_unit=CONCENTRATION_PARTS_PER_MILLION,
        conversion_fn=lambda x: x / 1000,
    ),
    UnitOfMeasurement(
        unit=ELECTRIC_CURRENT_AMPERE,
        aliases={"a", "ampere"},
        device_classes={DEVICE_CLASS_CURRENT},
    ),
    UnitOfMeasurement(
        unit=ELECTRIC_CURRENT_MILLIAMPERE,
        aliases={"ma", "milliampere"},
        device_classes={DEVICE_CLASS_CURRENT},
        conversion_unit=ELECTRIC_CURRENT_AMPERE,
        conversion_fn=lambda x: x / 1000,
    ),
    UnitOfMeasurement(
        unit=ENERGY_WATT_HOUR,
        aliases={"wh", "watthour"},
        device_classes={DEVICE_CLASS_ENERGY},
    ),
    UnitOfMeasurement(
        unit=ENERGY_KILO_WATT_HOUR,
        aliases={"kwh", "kilowatt-hour"},
        device_classes={DEVICE_CLASS_ENERGY},
    ),
    UnitOfMeasurement(
        unit=VOLUME_CUBIC_FEET,
        aliases={"ft3"},
        device_classes={DEVICE_CLASS_GAS},
    ),
    UnitOfMeasurement(
        unit=VOLUME_CUBIC_METERS,
        aliases={"m3"},
        device_classes={DEVICE_CLASS_GAS},
    ),
    UnitOfMeasurement(
        unit=LIGHT_LUX,
        aliases={"lux"},
        device_classes={DEVICE_CLASS_ILLUMINANCE},
    ),
    UnitOfMeasurement(
        unit="lm",
        aliases={"lum", "lumen"},
        device_classes={DEVICE_CLASS_ILLUMINANCE},
    ),
    UnitOfMeasurement(
        unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        aliases={"ug/m3", "µg/m3", "ug/m³"},
        device_classes={
            DEVICE_CLASS_NITROGEN_DIOXIDE,
            DEVICE_CLASS_NITROGEN_MONOXIDE,
            DEVICE_CLASS_NITROUS_OXIDE,
            DEVICE_CLASS_OZONE,
            DEVICE_CLASS_PM1,
            DEVICE_CLASS_PM25,
            DEVICE_CLASS_PM10,
            DEVICE_CLASS_SULPHUR_DIOXIDE,
            DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
        },
    ),
    UnitOfMeasurement(
        unit=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
        aliases={"mg/m3"},
        device_classes={
            DEVICE_CLASS_NITROGEN_DIOXIDE,
            DEVICE_CLASS_NITROGEN_MONOXIDE,
            DEVICE_CLASS_NITROUS_OXIDE,
            DEVICE_CLASS_OZONE,
            DEVICE_CLASS_PM1,
            DEVICE_CLASS_PM25,
            DEVICE_CLASS_PM10,
            DEVICE_CLASS_SULPHUR_DIOXIDE,
            DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
        },
        conversion_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        conversion_fn=lambda x: x * 1000,
    ),
    UnitOfMeasurement(
        unit=POWER_WATT,
        aliases={"watt"},
        device_classes={DEVICE_CLASS_POWER},
    ),
    UnitOfMeasurement(
        unit=POWER_KILO_WATT,
        aliases={"kilowatt"},
        device_classes={DEVICE_CLASS_POWER},
    ),
    UnitOfMeasurement(
        unit=PRESSURE_BAR,
        device_classes={DEVICE_CLASS_PRESSURE},
    ),
    UnitOfMeasurement(
        unit=PRESSURE_MBAR,
        aliases={"millibar"},
        device_classes={DEVICE_CLASS_PRESSURE},
    ),
    UnitOfMeasurement(
        unit=PRESSURE_HPA,
        aliases={"hpa", "hectopascal"},
        device_classes={DEVICE_CLASS_PRESSURE},
    ),
    UnitOfMeasurement(
        unit=PRESSURE_INHG,
        aliases={"inhg"},
        device_classes={DEVICE_CLASS_PRESSURE},
    ),
    UnitOfMeasurement(
        unit=PRESSURE_PSI,
        device_classes={DEVICE_CLASS_PRESSURE},
    ),
    UnitOfMeasurement(
        unit=PRESSURE_PA,
        device_classes={DEVICE_CLASS_PRESSURE},
    ),
    UnitOfMeasurement(
        unit=SIGNAL_STRENGTH_DECIBELS,
        aliases={"db"},
        device_classes={DEVICE_CLASS_SIGNAL_STRENGTH},
    ),
    UnitOfMeasurement(
        unit=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        aliases={"dbm"},
        device_classes={DEVICE_CLASS_SIGNAL_STRENGTH},
    ),
    UnitOfMeasurement(
        unit=TEMP_CELSIUS,
        aliases={"°c", "c", "celsius"},
        device_classes={DEVICE_CLASS_TEMPERATURE},
    ),
    UnitOfMeasurement(
        unit=TEMP_FAHRENHEIT,
        aliases={"°f", "f", "fahrenheit"},
        device_classes={DEVICE_CLASS_TEMPERATURE},
    ),
    UnitOfMeasurement(
        unit=ELECTRIC_POTENTIAL_VOLT,
        aliases={"volt"},
        device_classes={DEVICE_CLASS_VOLTAGE},
    ),
    UnitOfMeasurement(
        unit=ELECTRIC_POTENTIAL_MILLIVOLT,
        aliases={"mv", "millivolt"},
        device_classes={DEVICE_CLASS_VOLTAGE},
        conversion_unit=ELECTRIC_POTENTIAL_VOLT,
        conversion_fn=lambda x: x / 1000,
    ),
)


DEVICE_CLASS_UNITS: dict[str, dict[str, UnitOfMeasurement]] = {}
for uom in UNITS:
    for device_class in uom.device_classes:
        DEVICE_CLASS_UNITS.setdefault(device_class, {})[uom.unit] = uom
        for unit_alias in uom.aliases:
            DEVICE_CLASS_UNITS[device_class][unit_alias] = uom


@dataclass
class Country:
    """Describe a supported country."""

    name: str
    country_code: str
    endpoint: str = TuyaCloudOpenAPIEndpoint.AMERICA


# https://developer.tuya.com/en/docs/iot/oem-app-data-center-distributed?id=Kafi0ku9l07qb
TUYA_COUNTRIES = [
    Country("Afghanistan", "93", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Albania", "355", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Algeria", "213", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("American Samoa", "1-684", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Andorra", "376", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Angola", "244", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Anguilla", "1-264", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Antarctica", "672", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Antigua and Barbuda", "1-268", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Argentina", "54", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Armenia", "374", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Aruba", "297", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Australia", "61", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Austria", "43", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Azerbaijan", "994", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Bahamas", "1-242", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Bahrain", "973", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Bangladesh", "880", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Barbados", "1-246", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Belarus", "375", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Belgium", "32", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Belize", "501", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Benin", "229", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Bermuda", "1-441", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Bhutan", "975", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Bolivia", "591", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Bosnia and Herzegovina", "387", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Botswana", "267", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Brazil", "55", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("British Indian Ocean Territory", "246", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("British Virgin Islands", "1-284", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Brunei", "673", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Bulgaria", "359", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Burkina Faso", "226", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Burundi", "257", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Cambodia", "855", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Cameroon", "237", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Canada", "1", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Capo Verde", "238", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Cayman Islands", "1-345", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Central African Republic", "236", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Chad", "235", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Chile", "56", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("China", "86", TuyaCloudOpenAPIEndpoint.CHINA),
    Country("Christmas Island", "61"),
    Country("Cocos Islands", "61"),
    Country("Colombia", "57", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Comoros", "269", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Cook Islands", "682", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Costa Rica", "506", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Croatia", "385", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Cuba", "53"),
    Country("Curacao", "599", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Cyprus", "357", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Czech Republic", "420", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Democratic Republic of the Congo", "243", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Denmark", "45", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Djibouti", "253", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Dominica", "1-767", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Dominican Republic", "1-809", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("East Timor", "670", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Ecuador", "593", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Egypt", "20", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("El Salvador", "503", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Equatorial Guinea", "240", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Eritrea", "291", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Estonia", "372", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Ethiopia", "251", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Falkland Islands", "500", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Faroe Islands", "298", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Fiji", "679", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Finland", "358", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("France", "33", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("French Polynesia", "689", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Gabon", "241", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Gambia", "220", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Georgia", "995", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Germany", "49", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Ghana", "233", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Gibraltar", "350", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Greece", "30", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Greenland", "299", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Grenada", "1-473", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Guam", "1-671", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Guatemala", "502", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Guernsey", "44-1481"),
    Country("Guinea", "224"),
    Country("Guinea-Bissau", "245", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Guyana", "592", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Haiti", "509", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Honduras", "504", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Hong Kong", "852", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Hungary", "36", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Iceland", "354", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("India", "91", TuyaCloudOpenAPIEndpoint.INDIA),
    Country("Indonesia", "62", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Iran", "98"),
    Country("Iraq", "964", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Ireland", "353", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Isle of Man", "44-1624"),
    Country("Israel", "972", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Italy", "39", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Ivory Coast", "225", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Jamaica", "1-876", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Japan", "81", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Jersey", "44-1534"),
    Country("Jordan", "962", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Kazakhstan", "7", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Kenya", "254", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Kiribati", "686", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Kosovo", "383"),
    Country("Kuwait", "965", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Kyrgyzstan", "996", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Laos", "856", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Latvia", "371", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Lebanon", "961", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Lesotho", "266", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Liberia", "231", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Libya", "218", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Liechtenstein", "423", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Lithuania", "370", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Luxembourg", "352", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Macao", "853", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Macedonia", "389", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Madagascar", "261", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Malawi", "265", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Malaysia", "60", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Maldives", "960", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Mali", "223", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Malta", "356", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Marshall Islands", "692", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Mauritania", "222", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Mauritius", "230", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Mayotte", "262", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Mexico", "52", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Micronesia", "691", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Moldova", "373", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Monaco", "377", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Mongolia", "976", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Montenegro", "382", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Montserrat", "1-664", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Morocco", "212", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Mozambique", "258", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Myanmar", "95", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Namibia", "264", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Nauru", "674", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Nepal", "977", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Netherlands", "31", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Netherlands Antilles", "599"),
    Country("New Caledonia", "687", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("New Zealand", "64", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Nicaragua", "505", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Niger", "227", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Nigeria", "234", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Niue", "683", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("North Korea", "850"),
    Country("Northern Mariana Islands", "1-670", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Norway", "47", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Oman", "968", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Pakistan", "92", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Palau", "680", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Palestine", "970", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Panama", "507", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Papua New Guinea", "675", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Paraguay", "595", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Peru", "51", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Philippines", "63", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Pitcairn", "64"),
    Country("Poland", "48", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Portugal", "351", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Puerto Rico", "1-787, 1-939", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Qatar", "974", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Republic of the Congo", "242", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Reunion", "262", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Romania", "40", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Russia", "7", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Rwanda", "250", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Saint Barthelemy", "590", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Saint Helena", "290"),
    Country("Saint Kitts and Nevis", "1-869", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Saint Lucia", "1-758", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Saint Martin", "590", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Saint Pierre and Miquelon", "508", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country(
        "Saint Vincent and the Grenadines", "1-784", TuyaCloudOpenAPIEndpoint.EUROPE
    ),
    Country("Samoa", "685", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("San Marino", "378", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Sao Tome and Principe", "239", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Saudi Arabia", "966", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Senegal", "221", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Serbia", "381", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Seychelles", "248", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Sierra Leone", "232", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Singapore", "65", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Sint Maarten", "1-721", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Slovakia", "421", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Slovenia", "386", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Solomon Islands", "677", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Somalia", "252", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("South Africa", "27", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("South Korea", "82", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("South Sudan", "211"),
    Country("Spain", "34", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Sri Lanka", "94", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Sudan", "249"),
    Country("Suriname", "597", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Svalbard and Jan Mayen", "4779", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Swaziland", "268", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Sweden", "46", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Switzerland", "41", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Syria", "963"),
    Country("Taiwan", "886", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Tajikistan", "992", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Tanzania", "255", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Thailand", "66", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Togo", "228", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Tokelau", "690", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Tonga", "676", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Trinidad and Tobago", "1-868", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Tunisia", "216", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Turkey", "90", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Turkmenistan", "993", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Turks and Caicos Islands", "1-649", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Tuvalu", "688", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("U.S. Virgin Islands", "1-340", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Uganda", "256", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Ukraine", "380", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("United Arab Emirates", "971", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("United Kingdom", "44", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("United States", "1", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Uruguay", "598", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Uzbekistan", "998", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Vanuatu", "678", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Vatican", "379", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Venezuela", "58", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Vietnam", "84", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Wallis and Futuna", "681", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Western Sahara", "212", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Yemen", "967", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Zambia", "260", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Zimbabwe", "263", TuyaCloudOpenAPIEndpoint.EUROPE),
]
