"""Constants for the Alexa integration."""
from collections import OrderedDict

from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.components.climate import const as climate
from homeassistant.components import fan

DOMAIN = "alexa"

# Flash briefing constants
CONF_UID = "uid"
CONF_TITLE = "title"
CONF_AUDIO = "audio"
CONF_TEXT = "text"
CONF_DISPLAY_URL = "display_url"

CONF_FILTER = "filter"
CONF_ENTITY_CONFIG = "entity_config"
CONF_ENDPOINT = "endpoint"
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"

ATTR_UID = "uid"
ATTR_UPDATE_DATE = "updateDate"
ATTR_TITLE_TEXT = "titleText"
ATTR_STREAM_URL = "streamUrl"
ATTR_MAIN_TEXT = "mainText"
ATTR_REDIRECTION_URL = "redirectionURL"

SYN_RESOLUTION_MATCH = "ER_SUCCESS_MATCH"

DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.0Z"

API_DIRECTIVE = "directive"
API_ENDPOINT = "endpoint"
API_EVENT = "event"
API_CONTEXT = "context"
API_HEADER = "header"
API_PAYLOAD = "payload"
API_SCOPE = "scope"
API_CHANGE = "change"

CONF_DESCRIPTION = "description"
CONF_DISPLAY_CATEGORIES = "display_categories"

API_TEMP_UNITS = {TEMP_FAHRENHEIT: "FAHRENHEIT", TEMP_CELSIUS: "CELSIUS"}

# Needs to be ordered dict for `async_api_set_thermostat_mode` which does a
# reverse mapping of this dict and we want to map the first occurrence of OFF
# back to HA state.
API_THERMOSTAT_MODES = OrderedDict(
    [
        (climate.HVAC_MODE_HEAT, "HEAT"),
        (climate.HVAC_MODE_COOL, "COOL"),
        (climate.HVAC_MODE_HEAT_COOL, "AUTO"),
        (climate.HVAC_MODE_AUTO, "AUTO"),
        (climate.HVAC_MODE_OFF, "OFF"),
        (climate.HVAC_MODE_FAN_ONLY, "OFF"),
        (climate.HVAC_MODE_DRY, "CUSTOM"),
    ]
)
API_THERMOSTAT_MODES_CUSTOM = {climate.HVAC_MODE_DRY: "DEHUMIDIFY"}
API_THERMOSTAT_PRESETS = {climate.PRESET_ECO: "ECO"}

PERCENTAGE_FAN_MAP = {
    fan.SPEED_OFF: 0,
    fan.SPEED_LOW: 33,
    fan.SPEED_MEDIUM: 66,
    fan.SPEED_HIGH: 100,
}

RANGE_FAN_MAP = {
    fan.SPEED_OFF: 0,
    fan.SPEED_LOW: 1,
    fan.SPEED_MEDIUM: 2,
    fan.SPEED_HIGH: 3,
}

SPEED_FAN_MAP = {
    0: fan.SPEED_OFF,
    1: fan.SPEED_LOW,
    2: fan.SPEED_MEDIUM,
    3: fan.SPEED_HIGH,
}


class Cause:
    """Possible causes for property changes.

    https://developer.amazon.com/docs/smarthome/state-reporting-for-a-smart-home-skill.html#cause-object
    """

    # Indicates that the event was caused by a customer interaction with an
    # application. For example, a customer switches on a light, or locks a door
    # using the Alexa app or an app provided by a device vendor.
    APP_INTERACTION = "APP_INTERACTION"

    # Indicates that the event was caused by a physical interaction with an
    # endpoint. For example manually switching on a light or manually locking a
    # door lock
    PHYSICAL_INTERACTION = "PHYSICAL_INTERACTION"

    # Indicates that the event was caused by the periodic poll of an appliance,
    # which found a change in value. For example, you might poll a temperature
    # sensor every hour, and send the updated temperature to Alexa.
    PERIODIC_POLL = "PERIODIC_POLL"

    # Indicates that the event was caused by the application of a device rule.
    # For example, a customer configures a rule to switch on a light if a
    # motion sensor detects motion. In this case, Alexa receives an event from
    # the motion sensor, and another event from the light to indicate that its
    # state change was caused by the rule.
    RULE_TRIGGER = "RULE_TRIGGER"

    # Indicates that the event was caused by a voice interaction with Alexa.
    # For example a user speaking to their Echo device.
    VOICE_INTERACTION = "VOICE_INTERACTION"


class Catalog:
    """The Global Alexa catalog.

    https://developer.amazon.com/docs/device-apis/resources-and-assets.html#global-alexa-catalog

    You can use the global Alexa catalog for pre-defined names of devices, settings, values, and units.
    This catalog is localized into all the languages that Alexa supports.

    You can reference the following catalog of pre-defined friendly names.
    Each item in the following list is an asset identifier followed by its supported friendly names.
    The first friendly name for each identifier is the one displayed in the Alexa mobile app.
    """

    LABEL_ASSET = "asset"
    LABEL_TEXT = "text"

    # Shower
    DEVICENAME_SHOWER = "Alexa.DeviceName.Shower"

    # Washer, Washing Machine
    DEVICENAME_WASHER = "Alexa.DeviceName.Washer"

    # Router, Internet Router, Network Router, Wifi Router, Net Router
    DEVICENAME_ROUTER = "Alexa.DeviceName.Router"

    # Fan, Blower
    DEVICENAME_FAN = "Alexa.DeviceName.Fan"

    # Air Purifier, Air Cleaner,Clean Air Machine
    DEVICENAME_AIRPURIFIER = "Alexa.DeviceName.AirPurifier"

    # Space Heater, Portable Heater
    DEVICENAME_SPACEHEATER = "Alexa.DeviceName.SpaceHeater"

    # Rain Head, Overhead shower, Rain Shower, Rain Spout, Rain Faucet
    SHOWER_RAINHEAD = "Alexa.Shower.RainHead"

    # Handheld Shower, Shower Wand, Hand Shower
    SHOWER_HANDHELD = "Alexa.Shower.HandHeld"

    # Water Temperature, Water Temp, Water Heat
    SETTING_WATERTEMPERATURE = "Alexa.Setting.WaterTemperature"

    # Temperature, Temp
    SETTING_TEMPERATURE = "Alexa.Setting.Temperature"

    # Wash Cycle, Wash Preset, Wash setting
    SETTING_WASHCYCLE = "Alexa.Setting.WashCycle"

    # 2.4G Guest Wi-Fi, 2.4G Guest Network, Guest Network 2.4G, 2G Guest Wifi
    SETTING_2GGUESTWIFI = "Alexa.Setting.2GGuestWiFi"

    # 5G Guest Wi-Fi, 5G Guest Network, Guest Network 5G, 5G Guest Wifi
    SETTING_5GGUESTWIFI = "Alexa.Setting.5GGuestWiFi"

    # Guest Wi-fi, Guest Network, Guest Net
    SETTING_GUESTWIFI = "Alexa.Setting.GuestWiFi"

    # Auto, Automatic, Automatic Mode, Auto Mode
    SETTING_AUTO = "Alexa.Setting.Auto"

    #     #Night, Night Mode
    SETTING_NIGHT = "Alexa.Setting.Night"

    # Quiet, Quiet Mode, Noiseless, Silent
    SETTING_QUIET = "Alexa.Setting.Quiet"

    # Oscillate, Swivel, Oscillation, Spin, Back and forth
    SETTING_OSCILLATE = "Alexa.Setting.Oscillate"

    # Fan Speed, Airflow speed, Wind Speed, Air speed, Air velocity
    SETTING_FANSPEED = "Alexa.Setting.FanSpeed"

    # Preset, Setting
    SETTING_PRESET = "Alexa.Setting.Preset"

    # Mode
    SETTING_MODE = "Alexa.Setting.Mode"

    # Direction
    SETTING_DIRECTION = "Alexa.Setting.Direction"

    # Delicates, Delicate
    VALUE_DELICATE = "Alexa.Value.Delicate"

    # Quick Wash, Fast Wash, Wash Quickly, Speed Wash
    VALUE_QUICKWASH = "Alexa.Value.QuickWash"

    # Maximum, Max
    VALUE_MAXIMUM = "Alexa.Value.Maximum"

    # Minimum, Min
    VALUE_MINIMUM = "Alexa.Value.Minimum"

    # High
    VALUE_HIGH = "Alexa.Value.High"

    # Low
    VALUE_LOW = "Alexa.Value.Low"

    # Medium, Mid
    VALUE_MEDIUM = "Alexa.Value.Medium"


class Unit:
    """Alexa Units of Measure.

    https://developer.amazon.com/docs/device-apis/alexa-property-schemas.html#units-of-measure
    """

    ANGLE_DEGREES = "Alexa.Unit.Angle.Degrees"

    ANGLE_RADIANS = "Alexa.Unit.Angle.Radians"

    DISTANCE_FEET = "Alexa.Unit.Distance.Feet"

    DISTANCE_INCHES = "Alexa.Unit.Distance.Inches"

    DISTANCE_KILOMETERS = "Alexa.Unit.Distance.Kilometers"

    DISTANCE_METERS = "Alexa.Unit.Distance.Meters"

    DISTANCE_MILES = "Alexa.Unit.Distance.Miles"

    DISTANCE_YARDS = "Alexa.Unit.Distance.Yards"

    MASS_GRAMS = "Alexa.Unit.Mass.Grams"

    MASS_KILOGRAMS = "Alexa.Unit.Mass.Kilograms"

    PERCENT = "Alexa.Unit.Percent"

    TEMPERATURE_CELSIUS = "Alexa.Unit.Temperature.Celsius"

    TEMPERATURE_DEGREES = "Alexa.Unit.Temperature.Degrees"

    TEMPERATURE_FAHRENHEIT = "Alexa.Unit.Temperature.Fahrenheit"

    TEMPERATURE_KELVIN = "Alexa.Unit.Temperature.Kelvin"

    VOLUME_CUBICFEET = "Alexa.Unit.Volume.CubicFeet"

    VOLUME_CUBICMETERS = "Alexa.Unit.Volume.CubicMeters"

    VOLUME_GALLONS = "Alexa.Unit.Volume.Gallons"

    VOLUME_LITERS = "Alexa.Unit.Volume.Liters"

    VOLUME_PINTS = "Alexa.Unit.Volume.Pints"

    VOLUME_QUARTS = "Alexa.Unit.Volume.Quarts"

    WEIGHT_OUNCES = "Alexa.Unit.Weight.Ounces"

    WEIGHT_POUNDS = "Alexa.Unit.Weight.Pounds"
