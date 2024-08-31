"""Constants for the ISY Platform."""

import logging

from pyisy.constants import PROP_ON_LEVEL, PROP_RAMP_RATE

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_MEDIUM,
    FAN_ON,
    PRESET_AWAY,
    PRESET_BOOST,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    CURRENCY_CENT,
    CURRENCY_DOLLAR,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
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
    UV_INDEX,
    Platform,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfReactivePower,
    UnitOfSoundPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
    UnitOfVolumetricFlux,
)

_LOGGER = logging.getLogger(__package__)

DOMAIN = "isy994"

MANUFACTURER = "Universal Devices, Inc"

CONF_NETWORK = "network"
CONF_IGNORE_STRING = "ignore_string"
CONF_SENSOR_STRING = "sensor_string"
CONF_VAR_SENSOR_STRING = "variable_sensor_string"
CONF_TLS_VER = "tls"
CONF_RESTORE_LIGHT_STATE = "restore_light_state"

DEFAULT_IGNORE_STRING = "{IGNORE ME}"
DEFAULT_SENSOR_STRING = "sensor"
DEFAULT_RESTORE_LIGHT_STATE = False
DEFAULT_TLS_VERSION = 1.1
DEFAULT_PROGRAM_STRING = "HA."
DEFAULT_VAR_SENSOR_STRING = "HA."

KEY_ACTIONS = "actions"
KEY_STATUS = "status"

NODE_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
]
NODE_AUX_PROP_PLATFORMS = [
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]
PROGRAM_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.FAN,
    Platform.LOCK,
    Platform.SWITCH,
]
ROOT_NODE_PLATFORMS = [Platform.BUTTON]
VARIABLE_PLATFORMS = [Platform.NUMBER, Platform.SENSOR]

# Set of all platforms used by integration
PLATFORMS = {
    *NODE_PLATFORMS,
    *NODE_AUX_PROP_PLATFORMS,
    *PROGRAM_PLATFORMS,
    *ROOT_NODE_PLATFORMS,
    *VARIABLE_PLATFORMS,
}

SUPPORTED_BIN_SENS_CLASSES = ["moisture", "opening", "motion", "climate"]

# ISY Scenes are more like Switches than Home Assistant Scenes
# (they can turn off, and report their state)
ISY_GROUP_PLATFORM = Platform.SWITCH

ISY_CONF_UUID = "uuid"
ISY_CONF_NAME = "name"
ISY_CONF_MODEL = "model"
ISY_CONF_FIRMWARE = "firmware"

ISY_CONN_PORT = "port"
ISY_CONN_ADDRESS = "addr"
ISY_CONN_TLS = "tls"

FILTER_UOM = "uom"
FILTER_STATES = "states"
FILTER_NODE_DEF_ID = "node_def_id"
FILTER_INSTEON_TYPE = "insteon_type"
FILTER_ZWAVE_CAT = "zwave_cat"

# Special Subnodes for some Insteon Devices
SUBNODE_CLIMATE_COOL = 2
SUBNODE_CLIMATE_HEAT = 3
SUBNODE_DUSK_DAWN = 2
SUBNODE_EZIO2X4_SENSORS = [9, 10, 11, 12]
SUBNODE_FANLINC_LIGHT = 1
SUBNODE_HEARTBEAT = 4
SUBNODE_IOLINC_RELAY = 2
SUBNODE_LOW_BATTERY = 3
SUBNODE_MOTION_DISABLED = (13, 19)  # Int->13 or Hex->0xD depending on firmware
SUBNODE_NEGATIVE = 2
SUBNODE_TAMPER = (10, 16)  # Int->10 or Hex->0xA depending on firmware

# Generic Insteon Type Categories for Filters
TYPE_CATEGORY_CONTROLLERS = "0."
TYPE_CATEGORY_DIMMABLE = "1."
TYPE_CATEGORY_SWITCHED = "2."
TYPE_CATEGORY_IRRIGATION = "4."
TYPE_CATEGORY_CLIMATE = "5."
TYPE_CATEGORY_POOL_CTL = "6."
TYPE_CATEGORY_SENSOR_ACTUATORS = "7."
TYPE_CATEGORY_ENERGY_MGMT = "9."
TYPE_CATEGORY_COVER = "14."
TYPE_CATEGORY_LOCK = "15."
TYPE_CATEGORY_SAFETY = "16."
TYPE_CATEGORY_X10 = "113."

TYPE_EZIO2X4 = "7.3.255."
TYPE_INSTEON_MOTION = ("16.1.", "16.22.")

# Used for discovery
UDN_UUID_PREFIX = "uuid:"
ISY_URL_POSTFIX = "/desc"
EVENTS_SUFFIX = "_ISYSUB"

# Special Units of Measure
UOM_ISYV4_DEGREES = "degrees"
UOM_ISYV4_NONE = "n/a"

UOM_ISY_CELSIUS = 1
UOM_ISY_FAHRENHEIT = 2

UOM_8_BIT_RANGE = "100"
UOM_BARRIER = "97"
UOM_DOUBLE_TEMP = "101"
UOM_HVAC_ACTIONS = "66"
UOM_HVAC_MODE_GENERIC = "67"
UOM_HVAC_MODE_INSTEON = "98"
UOM_FAN_MODES = "99"
UOM_INDEX = "25"
UOM_ON_OFF = "2"
UOM_PERCENTAGE = "51"

# Do not use the Home Assistant consts for the states here - we're matching exact API
# responses, not using them for Home Assistant states
# Insteon Types: https://www.universal-devices.com/developers/wsdk/5.0.4/1_fam.xml
# Z-Wave Categories: https://www.universal-devices.com/developers/wsdk/5.0.4/4_fam.xml
NODE_FILTERS: dict[Platform, dict[str, list[str]]] = {
    Platform.BINARY_SENSOR: {
        FILTER_UOM: [UOM_ON_OFF],
        FILTER_STATES: [],
        FILTER_NODE_DEF_ID: [
            "BinaryAlarm",
            "BinaryAlarm_ADV",
            "BinaryControl",
            "BinaryControl_ADV",
            "EZIO2x4_Input",
            "EZRAIN_Input",
            "OnOffControl",
            "OnOffControl_ADV",
        ],
        FILTER_INSTEON_TYPE: [
            "7.0.",
            "7.13.",
            TYPE_CATEGORY_SAFETY,
        ],  # Does a startswith() match; include the dot
        FILTER_ZWAVE_CAT: (["104", "112", "138", *map(str, range(148, 180))]),
    },
    Platform.SENSOR: {
        # This is just a more-readable way of including MOST uoms between 1-100
        # (Remember that range() is non-inclusive of the stop value)
        FILTER_UOM: (
            [
                "1",
                *map(str, range(3, 11)),
                *map(str, range(12, 51)),
                *map(str, range(52, 66)),
                *map(str, range(69, 78)),
                "79",
                *map(str, range(82, 97)),
            ]
        ),
        FILTER_STATES: [],
        FILTER_NODE_DEF_ID: [
            "IMETER_SOLO",
            "EZIO2x4_Input_ADV",
            "KeypadButton",
            "KeypadButton_ADV",
            "RemoteLinc2",
            "RemoteLinc2_ADV",
        ],
        FILTER_INSTEON_TYPE: ["0.16.", "0.17.", "0.18.", "9.0.", "9.7."],
        FILTER_ZWAVE_CAT: (["118", "143", *map(str, range(180, 186))]),
    },
    Platform.LOCK: {
        FILTER_UOM: ["11"],
        FILTER_STATES: ["locked", "unlocked"],
        FILTER_NODE_DEF_ID: ["DoorLock"],
        FILTER_INSTEON_TYPE: [TYPE_CATEGORY_LOCK, "4.64."],
        FILTER_ZWAVE_CAT: ["111"],
    },
    Platform.FAN: {
        FILTER_UOM: [],
        FILTER_STATES: ["off", "low", "med", "high"],
        FILTER_NODE_DEF_ID: ["FanLincMotor"],
        FILTER_INSTEON_TYPE: ["1.46."],
        FILTER_ZWAVE_CAT: [],
    },
    Platform.COVER: {
        FILTER_UOM: [UOM_BARRIER],
        FILTER_STATES: ["open", "closed", "closing", "opening", "stopped"],
        FILTER_NODE_DEF_ID: ["DimmerMotorSwitch_ADV"],
        FILTER_INSTEON_TYPE: [TYPE_CATEGORY_COVER],
        FILTER_ZWAVE_CAT: ["106", "107"],
    },
    Platform.LIGHT: {
        FILTER_UOM: ["51"],
        FILTER_STATES: ["on", "off", "%"],
        FILTER_NODE_DEF_ID: [
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
        FILTER_INSTEON_TYPE: [TYPE_CATEGORY_DIMMABLE],
        FILTER_ZWAVE_CAT: ["109", "119"],
    },
    Platform.SWITCH: {
        FILTER_UOM: ["78"],
        FILTER_STATES: ["on", "off"],
        FILTER_NODE_DEF_ID: [
            "AlertModuleArmed",
            "AlertModuleSiren",
            "AlertModuleSiren_ADV",
            "EZIO2x4_Output",
            "EZRAIN_Output",
            "KeypadRelay",
            "KeypadRelay_ADV",
            "RelayLampOnly",
            "RelayLampOnly_ADV",
            "RelayLampSwitch",
            "RelayLampSwitch_ADV",
            "RelaySwitchOnlyPlusQuery",
            "RelaySwitchOnlyPlusQuery_ADV",
            "Siren",
            "Siren_ADV",
            "X10",
        ],
        FILTER_INSTEON_TYPE: [
            TYPE_CATEGORY_SWITCHED,
            "7.3.255.",
            "9.10.",
            "9.11.",
            TYPE_CATEGORY_X10,
        ],
        FILTER_ZWAVE_CAT: ["121", "122", "123", "137", "141", "147"],
    },
    Platform.CLIMATE: {
        FILTER_UOM: [UOM_ON_OFF],
        FILTER_STATES: ["heating", "cooling", "idle", "fan_only", "off"],
        FILTER_NODE_DEF_ID: ["TempLinc", "Thermostat"],
        FILTER_INSTEON_TYPE: ["4.8", TYPE_CATEGORY_CLIMATE],
        FILTER_ZWAVE_CAT: ["140"],
    },
}
NODE_AUX_FILTERS: dict[str, Platform] = {
    PROP_ON_LEVEL: Platform.NUMBER,
    PROP_RAMP_RATE: Platform.SELECT,
}

UOM_FRIENDLY_NAME = {
    "1": UnitOfElectricCurrent.AMPERE,
    UOM_ON_OFF: "",  # Binary, no unit
    "3": UnitOfPower.BTU_PER_HOUR,
    "4": UnitOfTemperature.CELSIUS,
    "5": UnitOfLength.CENTIMETERS,
    "6": UnitOfVolume.CUBIC_FEET,
    "7": UnitOfVolumeFlowRate.CUBIC_FEET_PER_MINUTE,
    "8": UnitOfVolume.CUBIC_METERS,
    "9": UnitOfTime.DAYS,
    "10": UnitOfTime.DAYS,
    "12": UnitOfSoundPressure.DECIBEL,
    "13": UnitOfSoundPressure.WEIGHTED_DECIBEL_A,
    "14": DEGREE,
    "16": "macroseismic",
    "17": UnitOfTemperature.FAHRENHEIT,
    "18": UnitOfLength.FEET,
    "19": UnitOfTime.HOURS,
    "20": UnitOfTime.HOURS,
    "21": PERCENTAGE,
    "22": PERCENTAGE,
    "23": UnitOfPressure.INHG,
    "24": UnitOfVolumetricFlux.INCHES_PER_HOUR,
    UOM_INDEX: UOM_INDEX,  # Index type. Use "node.formatted" for value
    "26": UnitOfTemperature.KELVIN,
    "27": "keyword",
    "28": UnitOfMass.KILOGRAMS,
    "29": "kV",
    "30": UnitOfPower.KILO_WATT,
    "31": UnitOfPressure.KPA,
    "32": UnitOfSpeed.KILOMETERS_PER_HOUR,
    "33": UnitOfEnergy.KILO_WATT_HOUR,
    "34": "liedu",
    "35": UnitOfVolume.LITERS,
    "36": LIGHT_LUX,
    "37": "mercalli",
    "38": UnitOfLength.METERS,
    "39": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    "40": UnitOfSpeed.METERS_PER_SECOND,
    "41": UnitOfElectricCurrent.MILLIAMPERE,
    "42": UnitOfTime.MILLISECONDS,
    "43": UnitOfElectricPotential.MILLIVOLT,
    "44": UnitOfTime.MINUTES,
    "45": UnitOfTime.MINUTES,
    "46": UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
    "47": UnitOfTime.MONTHS,
    "48": UnitOfSpeed.MILES_PER_HOUR,
    "49": UnitOfSpeed.METERS_PER_SECOND,
    "50": "Ω",
    UOM_PERCENTAGE: PERCENTAGE,
    "52": UnitOfMass.POUNDS,
    "53": "pf",
    "54": CONCENTRATION_PARTS_PER_MILLION,
    "55": "pulse count",
    "57": UnitOfTime.SECONDS,
    "58": UnitOfTime.SECONDS,
    "59": "S/m",
    "60": "m_b",
    "61": "M_L",
    "62": "M_w",
    "63": "M_S",
    "64": "shindo",
    "65": "SML",
    "69": UnitOfVolume.GALLONS,
    "71": UV_INDEX,
    "72": UnitOfElectricPotential.VOLT,
    "73": UnitOfPower.WATT,
    "74": UnitOfIrradiance.WATTS_PER_SQUARE_METER,
    "75": "weekday",
    "76": DEGREE,
    "77": UnitOfTime.YEARS,
    "82": UnitOfLength.MILLIMETERS,
    "83": UnitOfLength.KILOMETERS,
    "85": "Ω",
    "86": "kΩ",
    "87": f"{UnitOfVolume.CUBIC_METERS}/{UnitOfVolume.CUBIC_METERS}",
    "88": "Water activity",
    "89": REVOLUTIONS_PER_MINUTE,
    "90": UnitOfFrequency.HERTZ,
    "91": DEGREE,
    "92": f"{DEGREE} South",
    UOM_8_BIT_RANGE: "",  # Range 0-255, no unit.
    UOM_DOUBLE_TEMP: UOM_DOUBLE_TEMP,
    "102": "kWs",  # Kilowatt Seconds
    "103": CURRENCY_DOLLAR,
    "104": CURRENCY_CENT,
    "105": UnitOfLength.INCHES,
    "106": UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
    "107": "",  # raw 1-byte unsigned value
    "108": "",  # raw 2-byte unsigned value
    "109": "",  # raw 3-byte unsigned value
    "110": "",  # raw 4-byte unsigned value
    "111": "",  # raw 1-byte signed value
    "112": "",  # raw 2-byte signed value
    "113": "",  # raw 3-byte signed value
    "114": "",  # raw 4-byte signed value
    "116": UnitOfLength.MILES,
    "117": UnitOfPressure.MBAR,
    "118": UnitOfPressure.HPA,
    "119": UnitOfEnergy.WATT_HOUR,
    "120": UnitOfVolumetricFlux.INCHES_PER_DAY,
    "122": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # Microgram per cubic meter
    "123": f"bq/{UnitOfVolume.CUBIC_METERS}",  # Becquerel per cubic meter
    "124": f"pCi/{UnitOfVolume.LITERS}",  # Picocuries per liter
    "125": "pH",
    "126": "bpm",  # Beats per Minute
    "127": UnitOfPressure.MMHG,
    "128": "J",
    "129": "BMI",  # Body Mass Index
    "130": f"{UnitOfVolume.LITERS}/{UnitOfTime.HOURS}",
    "131": SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    "132": "bpm",  # Breaths per minute
    "133": UnitOfFrequency.KILOHERTZ,
    "134": f"{UnitOfLength.METERS}/{UnitOfTime.SECONDS}²",
    "135": UnitOfApparentPower.VOLT_AMPERE,  # Volt-Amp
    "136": UnitOfReactivePower.VOLT_AMPERE_REACTIVE,  # VAR = Volt-Amp Reactive
    "137": "",  # NTP DateTime - Number of seconds since 1900
    "138": UnitOfPressure.PSI,
    "139": DEGREE,  # Degree 0-360
    "140": f"{UnitOfMass.MILLIGRAMS}/{UnitOfVolume.LITERS}",
    "141": "N",  # Netwon
    "142": f"{UnitOfVolume.GALLONS}/{UnitOfTime.SECONDS}",
    "143": "gpm",  # Gallon per Minute
    "144": "gph",  # Gallon per Hour
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
    UOM_HVAC_ACTIONS: {  # Thermostat Heat/Cool State
        0: HVACAction.IDLE.value,
        1: HVACAction.HEATING.value,
        2: HVACAction.COOLING.value,
        3: HVACAction.FAN.value,
        4: HVACAction.HEATING.value,  # Pending Heat
        5: HVACAction.COOLING.value,  # Pending Cool
        # >6 defined in ISY but not implemented, leaving for future expanision.
        6: HVACAction.IDLE.value,
        7: HVACAction.HEATING.value,
        8: HVACAction.HEATING.value,
        9: HVACAction.COOLING.value,
        10: HVACAction.HEATING.value,
        11: HVACAction.HEATING.value,
    },
    UOM_HVAC_MODE_GENERIC: {  # Thermostat Mode
        0: HVACMode.OFF.value,
        1: HVACMode.HEAT.value,
        2: HVACMode.COOL.value,
        3: HVACMode.AUTO.value,
        4: PRESET_BOOST,
        5: "resume",
        6: HVACMode.FAN_ONLY.value,
        7: "furnace",
        8: HVACMode.DRY.value,
        9: "moist air",
        10: "auto changeover",
        11: "energy save heat",
        12: "energy save cool",
        13: PRESET_AWAY,
        14: HVACMode.AUTO.value,
        15: HVACMode.AUTO.value,
        16: HVACMode.AUTO.value,
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
    UOM_BARRIER: {  # Barrier Status
        0: STATE_CLOSED,
        100: STATE_OPEN,
        101: STATE_UNKNOWN,
        102: "stopped",
        103: STATE_CLOSING,
        104: STATE_OPENING,
        **{
            b: f"{b} %" for a, b in enumerate(list(range(1, 100)))
        },  # 1-99 are percentage open
    },
    UOM_HVAC_MODE_INSTEON: {  # Insteon Thermostat Mode
        0: HVACMode.OFF.value,
        1: HVACMode.HEAT.value,
        2: HVACMode.COOL.value,
        3: HVACMode.HEAT_COOL.value,
        4: HVACMode.FAN_ONLY.value,
        5: HVACMode.AUTO.value,  # Program Auto
        6: HVACMode.AUTO.value,  # Program Heat-Set @ Local Device Only
        7: HVACMode.AUTO.value,  # Program Cool-Set @ Local Device Only
    },
    UOM_FAN_MODES: {7: FAN_ON, 8: FAN_AUTO},  # Insteon Thermostat Fan Mode
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

ISY_HVAC_MODES = [
    HVACMode.OFF,
    HVACMode.HEAT,
    HVACMode.COOL,
    HVACMode.HEAT_COOL,
    HVACMode.AUTO,
    HVACMode.FAN_ONLY,
]

HA_HVAC_TO_ISY = {
    HVACMode.OFF: "off",
    HVACMode.HEAT: "heat",
    HVACMode.COOL: "cool",
    HVACMode.HEAT_COOL: "auto",
    HVACMode.FAN_ONLY: "fan_only",
    HVACMode.AUTO: "program_auto",
}

HA_FAN_TO_ISY = {FAN_ON: "on", FAN_AUTO: "auto"}

BINARY_SENSOR_DEVICE_TYPES_ISY = {
    BinarySensorDeviceClass.MOISTURE: ["16.8.", "16.13.", "16.14."],
    BinarySensorDeviceClass.OPENING: [
        "16.9.",
        "16.6.",
        "16.7.",
        "16.2.",
        "16.17.",
        "16.20.",
        "16.21.",
    ],
    BinarySensorDeviceClass.MOTION: ["16.1.", "16.4.", "16.5.", "16.3.", "16.22."],
}

BINARY_SENSOR_DEVICE_TYPES_ZWAVE = {
    BinarySensorDeviceClass.SAFETY: ["137", "172", "176", "177", "178"],
    BinarySensorDeviceClass.SMOKE: ["138", "156"],
    BinarySensorDeviceClass.PROBLEM: ["148", "149", "157", "158", "164", "174", "175"],
    BinarySensorDeviceClass.GAS: ["150", "151"],
    BinarySensorDeviceClass.SOUND: ["153"],
    BinarySensorDeviceClass.COLD: ["152", "168"],
    BinarySensorDeviceClass.HEAT: ["154", "166", "167"],
    BinarySensorDeviceClass.MOISTURE: ["159", "169"],
    BinarySensorDeviceClass.DOOR: ["160"],
    BinarySensorDeviceClass.BATTERY: ["162"],
    BinarySensorDeviceClass.MOTION: ["155"],
    BinarySensorDeviceClass.VIBRATION: ["173"],
}


SCHEME_HTTP = "http"
HTTP_PORT = 80
SCHEME_HTTPS = "https"
HTTPS_PORT = 443
