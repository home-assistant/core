"""Constants for the ISY994 Platform."""
import logging

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_MEDIUM,
    FAN_ON,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_BOOST,
)
from homeassistant.components.cover import DOMAIN as COVER
from homeassistant.components.fan import DOMAIN as FAN
from homeassistant.components.light import DOMAIN as LIGHT
from homeassistant.components.lock import DOMAIN as LOCK
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.switch import DOMAIN as SWITCH
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ,
    LENGTH_CENTIMETERS,
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    MASS_KILOGRAMS,
    MASS_POUNDS,
    POWER_WATT,
    PRESSURE_INHG,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_LOCKED,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_OPENING,
    STATE_PROBLEM,
    STATE_UNKNOWN,
    STATE_UNLOCKED,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMP_KELVIN,
    TIME_DAYS,
    TIME_HOURS,
    TIME_MILLISECONDS,
    TIME_MINUTES,
    TIME_MONTHS,
    TIME_SECONDS,
    TIME_YEARS,
    UNIT_PERCENTAGE,
    UV_INDEX,
    VOLT,
    VOLUME_GALLONS,
    VOLUME_LITERS,
)

_LOGGER = logging.getLogger(__package__)

DOMAIN = "isy994"

MANUFACTURER = "Universal Devices, Inc"

CONF_IGNORE_STRING = "ignore_string"
CONF_SENSOR_STRING = "sensor_string"
CONF_TLS_VER = "tls"

DEFAULT_IGNORE_STRING = "{IGNORE ME}"
DEFAULT_SENSOR_STRING = "sensor"
DEFAULT_TLS_VERSION = 1.1

KEY_ACTIONS = "actions"
KEY_STATUS = "status"

SUPPORTED_PLATFORMS = [BINARY_SENSOR, SENSOR, LOCK, FAN, COVER, LIGHT, SWITCH]
SUPPORTED_PROGRAM_PLATFORMS = [BINARY_SENSOR, LOCK, FAN, COVER, SWITCH]

SUPPORTED_BIN_SENS_CLASSES = ["moisture", "opening", "motion", "climate"]

# ISY Scenes are more like Switches than Home Assistant Scenes
# (they can turn off, and report their state)
ISY_GROUP_PLATFORM = SWITCH

ISY994_ISY = "isy"
ISY994_NODES = "isy994_nodes"
ISY994_PROGRAMS = "isy994_programs"

# Do not use the Home Assistant consts for the states here - we're matching exact API
# responses, not using them for Home Assistant states
NODE_FILTERS = {
    BINARY_SENSOR: {
        "uom": [],
        "states": [],
        "node_def_id": [
            "BinaryAlarm",
            "BinaryAlarm_ADV",
            "BinaryControl",
            "BinaryControl_ADV",
            "EZIO2x4_Input",
            "EZRAIN_Input",
            "OnOffControl",
            "OnOffControl_ADV",
        ],
        "insteon_type": [
            "7.0.",
            "7.13.",
            "16.",
        ],  # Does a startswith() match; include the dot
    },
    SENSOR: {
        # This is just a more-readable way of including MOST uoms between 1-100
        # (Remember that range() is non-inclusive of the stop value)
        "uom": (
            ["1"]
            + list(map(str, range(3, 11)))
            + list(map(str, range(12, 51)))
            + list(map(str, range(52, 66)))
            + list(map(str, range(69, 78)))
            + ["79"]
            + list(map(str, range(82, 97)))
        ),
        "states": [],
        "node_def_id": ["IMETER_SOLO", "EZIO2x4_Input_ADV"],
        "insteon_type": ["9.0.", "9.7."],
    },
    LOCK: {
        "uom": ["11"],
        "states": ["locked", "unlocked"],
        "node_def_id": ["DoorLock"],
        "insteon_type": ["15.", "4.64."],
    },
    FAN: {
        "uom": [],
        "states": ["off", "low", "med", "high"],
        "node_def_id": ["FanLincMotor"],
        "insteon_type": ["1.46."],
    },
    COVER: {
        "uom": ["97"],
        "states": ["open", "closed", "closing", "opening", "stopped"],
        "node_def_id": [],
        "insteon_type": [],
    },
    LIGHT: {
        "uom": ["51"],
        "states": ["on", "off", "%"],
        "node_def_id": [
            "BallastRelayLampSwitch",
            "BallastRelayLampSwitch_ADV",
            "DimmerLampOnly",
            "DimmerLampSwitch",
            "DimmerLampSwitch_ADV",
            "DimmerSwitchOnly",
            "DimmerSwitchOnly_ADV",
            "KeypadDimmer",
            "KeypadDimmer_ADV",
        ],
        "insteon_type": ["1."],
    },
    SWITCH: {
        "uom": ["2", "78"],
        "states": ["on", "off"],
        "node_def_id": [
            "AlertModuleArmed",
            "AlertModuleSiren",
            "AlertModuleSiren_ADV",
            "EZIO2x4_Output",
            "EZRAIN_Output",
            "KeypadButton",
            "KeypadButton_ADV",
            "KeypadRelay",
            "KeypadRelay_ADV",
            "RelayLampOnly",
            "RelayLampOnly_ADV",
            "RelayLampSwitch",
            "RelayLampSwitch_ADV",
            "RelaySwitchOnlyPlusQuery",
            "RelaySwitchOnlyPlusQuery_ADV",
            "RemoteLinc2",
            "RemoteLinc2_ADV",
            "Siren",
            "Siren_ADV",
            "X10",
        ],
        "insteon_type": ["0.16.", "2.", "7.3.255.", "9.10.", "9.11.", "113."],
    },
}

UOM_FRIENDLY_NAME = {
    "1": "A",
    "3": f"btu/{TIME_HOURS}",
    "4": TEMP_CELSIUS,
    "5": LENGTH_CENTIMETERS,
    "6": "ft³",
    "7": f"ft³/{TIME_MINUTES}",
    "8": "m³",
    "9": TIME_DAYS,
    "10": TIME_DAYS,
    "12": "dB",
    "13": "dB A",
    "14": DEGREE,
    "16": "macroseismic",
    "17": TEMP_FAHRENHEIT,
    "18": LENGTH_FEET,
    "19": TIME_HOURS,
    "20": TIME_HOURS,
    "21": "%AH",
    "22": "%RH",
    "23": PRESSURE_INHG,
    "24": f"{LENGTH_INCHES}/{TIME_HOURS}",
    "25": "index",
    "26": TEMP_KELVIN,
    "27": "keyword",
    "28": MASS_KILOGRAMS,
    "29": "kV",
    "30": "kW",
    "31": "kPa",
    "32": SPEED_KILOMETERS_PER_HOUR,
    "33": ENERGY_KILO_WATT_HOUR,
    "34": "liedu",
    "35": VOLUME_LITERS,
    "36": "lx",
    "37": "mercalli",
    "38": LENGTH_METERS,
    "39": f"{LENGTH_METERS}³/{TIME_HOURS}",
    "40": SPEED_METERS_PER_SECOND,
    "41": "mA",
    "42": TIME_MILLISECONDS,
    "43": "mV",
    "44": TIME_MINUTES,
    "45": TIME_MINUTES,
    "46": f"mm/{TIME_HOURS}",
    "47": TIME_MONTHS,
    "48": SPEED_MILES_PER_HOUR,
    "49": SPEED_METERS_PER_SECOND,
    "50": "Ω",
    "51": UNIT_PERCENTAGE,
    "52": MASS_POUNDS,
    "53": "pf",
    "54": CONCENTRATION_PARTS_PER_MILLION,
    "55": "pulse count",
    "57": TIME_SECONDS,
    "58": TIME_SECONDS,
    "59": "S/m",
    "60": "m_b",
    "61": "M_L",
    "62": "M_w",
    "63": "M_S",
    "64": "shindo",
    "65": "SML",
    "69": VOLUME_GALLONS,
    "71": UV_INDEX,
    "72": VOLT,
    "73": POWER_WATT,
    "74": f"{POWER_WATT}/{LENGTH_METERS}²",
    "75": "weekday",
    "76": DEGREE,
    "77": TIME_YEARS,
    "82": "mm",
    "83": LENGTH_KILOMETERS,
    "85": "Ω",
    "86": "kΩ",
    "87": f"{LENGTH_METERS}³/{LENGTH_METERS}³",
    "88": "Water activity",
    "89": "RPM",
    "90": FREQUENCY_HERTZ,
    "91": DEGREE,
    "92": f"{DEGREE} South",
    "100": "",  # Range 0-255, no unit.
    "101": f"{DEGREE} (x2)",
    "102": "kWs",
    "103": "$",
    "104": "¢",
    "105": LENGTH_INCHES,
    "106": f"mm/{TIME_DAYS}",
    "107": "",  # raw 1-byte unsigned value
    "108": "",  # raw 2-byte unsigned value
    "109": "",  # raw 3-byte unsigned value
    "110": "",  # raw 4-byte unsigned value
    "111": "",  # raw 1-byte signed value
    "112": "",  # raw 2-byte signed value
    "113": "",  # raw 3-byte signed value
    "114": "",  # raw 4-byte signed value
    "116": LENGTH_MILES,
    "117": "mb",
    "118": "hPa",
    "119": f"{POWER_WATT}{TIME_HOURS}",
    "120": f"{LENGTH_INCHES}/{TIME_DAYS}",
}

UOM_TO_STATES = {
    "11": {  # Deadbolt Status
        0: STATE_UNLOCKED,
        100: STATE_LOCKED,
        101: STATE_UNKNOWN,
        102: STATE_PROBLEM,
    },
    "15": {  # Door Lock Alarm
        1: "master code changed",
        2: "tamper code entry limit",
        3: "escutcheon removed",
        4: "key/manually locked",
        5: "locked by touch",
        6: "key/manually unlocked",
        7: "remote locking jammed bolt",
        8: "remotely locked",
        9: "remotely unlocked",
        10: "deadbolt jammed",
        11: "battery too low to operate",
        12: "critical low battery",
        13: "low battery",
        14: "automatically locked",
        15: "automatic locking jammed bolt",
        16: "remotely power cycled",
        17: "lock handling complete",
        19: "user deleted",
        20: "user added",
        21: "duplicate pin",
        22: "jammed bolt by locking with keypad",
        23: "locked by keypad",
        24: "unlocked by keypad",
        25: "keypad attempt outside schedule",
        26: "hardware failure",
        27: "factory reset",
    },
    "66": {  # Thermostat Heat/Cool State
        0: CURRENT_HVAC_IDLE,
        1: CURRENT_HVAC_HEAT,
        2: CURRENT_HVAC_COOL,
        3: CURRENT_HVAC_FAN,
        4: CURRENT_HVAC_HEAT,  # Pending Heat
        5: CURRENT_HVAC_COOL,  # Pending Cool
        # >6 defined in ISY but not implemented, leaving for future expanision.
        6: CURRENT_HVAC_IDLE,
        7: CURRENT_HVAC_HEAT,
        8: CURRENT_HVAC_HEAT,
        9: CURRENT_HVAC_COOL,
        10: CURRENT_HVAC_HEAT,
        11: CURRENT_HVAC_HEAT,
    },
    "67": {  # Thermostat Mode
        0: HVAC_MODE_OFF,
        1: HVAC_MODE_HEAT,
        2: HVAC_MODE_COOL,
        3: HVAC_MODE_AUTO,
        4: PRESET_BOOST,
        5: "resume",
        6: HVAC_MODE_FAN_ONLY,
        7: "furnace",
        8: HVAC_MODE_DRY,
        9: "moist air",
        10: "auto changeover",
        11: "energy save heat",
        12: "energy save cool",
        13: PRESET_AWAY,
        14: HVAC_MODE_AUTO,
        15: HVAC_MODE_AUTO,
        16: HVAC_MODE_AUTO,
    },
    "68": {  # Thermostat Fan Mode
        0: FAN_AUTO,
        1: FAN_ON,
        2: FAN_HIGH,  # Auto High
        3: FAN_HIGH,
        4: FAN_MEDIUM,  # Auto Medium
        5: FAN_MEDIUM,
        6: "circulation",
        7: "humidity circulation",
    },
    "78": {0: STATE_OFF, 100: STATE_ON},  # 0-Off 100-On
    "79": {0: STATE_OPEN, 100: STATE_CLOSED},  # 0-Open 100-Close
    "80": {  # Thermostat Fan Run State
        0: STATE_OFF,
        1: STATE_ON,
        2: "on high",
        3: "on medium",
        4: "circulation",
        5: "humidity circulation",
        6: "right/left circulation",
        7: "up/down circulation",
        8: "quiet circulation",
    },
    "84": {0: SERVICE_LOCK, 1: SERVICE_UNLOCK},  # Secure Mode
    "93": {  # Power Management Alarm
        1: "power applied",
        2: "ac mains disconnected",
        3: "ac mains reconnected",
        4: "surge detection",
        5: "volt drop or drift",
        6: "over current detected",
        7: "over voltage detected",
        8: "over load detected",
        9: "load error",
        10: "replace battery soon",
        11: "replace battery now",
        12: "battery is charging",
        13: "battery is fully charged",
        14: "charge battery soon",
        15: "charge battery now",
    },
    "94": {  # Appliance Alarm
        1: "program started",
        2: "program in progress",
        3: "program completed",
        4: "replace main filter",
        5: "failure to set target temperature",
        6: "supplying water",
        7: "water supply failure",
        8: "boiling",
        9: "boiling failure",
        10: "washing",
        11: "washing failure",
        12: "rinsing",
        13: "rinsing failure",
        14: "draining",
        15: "draining failure",
        16: "spinning",
        17: "spinning failure",
        18: "drying",
        19: "drying failure",
        20: "fan failure",
        21: "compressor failure",
    },
    "95": {  # Home Health Alarm
        1: "leaving bed",
        2: "sitting on bed",
        3: "lying on bed",
        4: "posture changed",
        5: "sitting on edge of bed",
    },
    "96": {  # VOC Level
        1: "clean",
        2: "slightly polluted",
        3: "moderately polluted",
        4: "highly polluted",
    },
    "97": {  # Barrier Status
        **{
            0: STATE_CLOSED,
            100: STATE_OPEN,
            101: STATE_UNKNOWN,
            102: "stopped",
            103: STATE_CLOSING,
            104: STATE_OPENING,
        },
        **{
            b: f"{b} %" for a, b in enumerate(list(range(1, 100)))
        },  # 1-99 are percentage open
    },
    "98": {  # Insteon Thermostat Mode
        0: HVAC_MODE_OFF,
        1: HVAC_MODE_HEAT,
        2: HVAC_MODE_COOL,
        3: HVAC_MODE_HEAT_COOL,
        4: HVAC_MODE_FAN_ONLY,
        5: HVAC_MODE_AUTO,  # Program Auto
        6: HVAC_MODE_AUTO,  # Program Heat-Set @ Local Device Only
        7: HVAC_MODE_AUTO,  # Program Cool-Set @ Local Device Only
    },
    "99": {7: FAN_ON, 8: FAN_AUTO},  # Insteon Thermostat Fan Mode
    "115": {  # Most recent On style action taken for lamp control
        0: "on",
        1: "off",
        2: "fade up",
        3: "fade down",
        4: "fade stop",
        5: "fast on",
        6: "fast off",
        7: "triple press on",
        8: "triple press off",
        9: "4x press on",
        10: "4x press off",
        11: "5x press on",
        12: "5x press off",
    },
}

ISY_BIN_SENS_DEVICE_TYPES = {
    "moisture": ["16.8.", "16.13.", "16.14."],
    "opening": ["16.9.", "16.6.", "16.7.", "16.2.", "16.17.", "16.20.", "16.21."],
    "motion": ["16.1.", "16.4.", "16.5.", "16.3.", "16.22."],
    "climate": ["5.11.", "5.10."],
}
