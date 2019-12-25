"""Analog Output on Zigbee Home Automation networks."""
from collections import OrderedDict
import logging

from homeassistant.components.input_number import (
    ATTR_INITIAL,
    ATTR_MAX,
    ATTR_MIN,
    ATTR_MODE,
    ATTR_STEP,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ICON,
    CONF_INITIAL,
    CONF_MAX,
    CONF_MIN,
    CONF_MODE,
    CONF_STEP,
    DOMAIN,
    MODE_SLIDER,
    InputNumber,
)
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .core.const import (
    CHANNEL_ANALOG_OUTPUT,
    DATA_ZHA,
    DATA_ZHA_DISPATCHERS,
    SIGNAL_ATTR_UPDATED,
    ZHA_DISCOVERY_NEW,
)
from .entity import ZhaEntity

_LOGGER = logging.getLogger(__name__)

UNITS = {
    0: "Square-meters",
    1: "Square-feet",
    2: "Milliamperes",
    3: "Amperes",
    4: "Ohms",
    5: "Volts",
    6: "Kilo-volts",
    7: "Mega-volts",
    8: "Volt-amperes",
    9: "Kilo-volt-amperes",
    10: "Mega-volt-amperes",
    11: "Volt-amperes-reactive",
    12: "Kilo-volt-amperes-reactive",
    13: "Mega-volt-amperes-reactive",
    14: "Degrees-phase",
    15: "Power-factor",
    16: "Joules",
    17: "Kilojoules",
    18: "Watt-hours",
    19: "Kilowatt-hours",
    20: "BTUs",
    21: "Therms",
    22: "Ton-hours",
    23: "Joules-per-kilogram-dry-air",
    24: "BTUs-per-pound-dry-air",
    25: "Cycles-per-hour",
    26: "Cycles-per-minute",
    27: "Hertz",
    28: "Grams-of-water-per-kilogram-dry-air",
    29: "Percent-relative-humidity",
    30: "Millimeters",
    31: "Meters",
    32: "Inches",
    33: "Feet",
    34: "Watts-per-square-foot",
    35: "Watts-per-square-meter",
    36: "Lumens",
    37: "Luxes",
    38: "Foot-candles",
    39: "Kilograms",
    40: "Pounds-mass",
    41: "Tons",
    42: "Kilograms-per-second",
    43: "Kilograms-per-minute",
    44: "Kilograms-per-hour",
    45: "Pounds-mass-per-minute",
    46: "Pounds-mass-per-hour",
    47: "Watts",
    48: "Kilowatts",
    49: "Megawatts",
    50: "BTUs-per-hour",
    51: "Horsepower",
    52: "Tons-refrigeration",
    53: "Pascals",
    54: "Kilopascals",
    55: "Bars",
    56: "Pounds-force-per-square-inch",
    57: "Centimeters-of-water",
    58: "Inches-of-water",
    59: "Millimeters-of-mercury",
    60: "Centimeters-of-mercury",
    61: "Inches-of-mercury",
    62: "°C",
    63: "°K",
    64: "°F",
    65: "Degree-days-Celsius",
    66: "Degree-days-Fahrenheit",
    67: "Years",
    68: "Months",
    69: "Weeks",
    70: "Days",
    71: "Hours",
    72: "Minutes",
    73: "Seconds",
    74: "Meters-per-second",
    75: "Kilometers-per-hour",
    76: "Feet-per-second",
    77: "Feet-per-minute",
    78: "Miles-per-hour",
    79: "Cubic-feet",
    80: "Cubic-meters",
    81: "Imperial-gallons",
    82: "Liters",
    83: "Us-gallons",
    84: "Cubic-feet-per-minute",
    85: "Cubic-meters-per-second",
    86: "Imperial-gallons-per-minute",
    87: "Liters-per-second",
    88: "Liters-per-minute",
    89: "Us-gallons-per-minute",
    90: "Degrees-angular",
    91: "Degrees-Celsius-per-hour",
    92: "Degrees-Celsius-per-minute",
    93: "Degrees-Fahrenheit-per-hour",
    94: "Degrees-Fahrenheit-per-minute",
    95: None,
    96: "Parts-per-million",
    97: "Parts-per-billion",
    98: "%",
    99: "Percent-per-second",
    100: "Per-minute",
    101: "Per-second",
    102: "Psi-per-Degree-Fahrenheit",
    103: "Radians",
    104: "Revolutions-per-minute",
    105: "Currency1",
    106: "Currency2",
    107: "Currency3",
    108: "Currency4",
    109: "Currency5",
    110: "Currency6",
    111: "Currency7",
    112: "Currency8",
    113: "Currency9",
    114: "Currency10",
    115: "Square-inches",
    116: "Square-centimeters",
    117: "BTUs-per-pound",
    118: "Centimeters",
    119: "Pounds-mass-per-second",
    120: "Delta-Degrees-Fahrenheit",
    121: "Delta-Degrees-Kelvin",
    122: "Kilohms",
    123: "Megohms",
    124: "Millivolts",
    125: "Kilojoules-per-kilogram",
    126: "Megajoules",
    127: "Joules-per-degree-Kelvin",
    128: "Joules-per-kilogram-degree-Kelvin",
    129: "Kilohertz",
    130: "Megahertz",
    131: "Per-hour",
    132: "Milliwatts",
    133: "Hectopascals",
    134: "Millibars",
    135: "Cubic-meters-per-hour",
    136: "Liters-per-hour",
    137: "Kilowatt-hours-per-square-meter",
    138: "Kilowatt-hours-per-square-foot",
    139: "Megajoules-per-square-meter",
    140: "Megajoules-per-square-foot",
    141: "Watts-per-square-meter-Degree-Kelvin",
    142: "Cubic-feet-per-second",
    143: "Percent-obscuration-per-foot",
    144: "Percent-obscuration-per-meter",
    145: "Milliohms",
    146: "Megawatt-hours",
    147: "Kilo-BTUs",
    148: "Mega-BTUs",
    149: "Kilojoules-per-kilogram-dry-air",
    150: "Megajoules-per-kilogram-dry-air",
    151: "Kilojoules-per-degree-Kelvin",
    152: "Megajoules-per-degree-Kelvin",
    153: "Newton",
    154: "Grams-per-second",
    155: "Grams-per-minute",
    156: "Tons-per-hour",
    157: "Kilo-BTUs-per-hour",
    158: "Hundredths-seconds",
    159: "Milliseconds",
    160: "Newton-meters",
    161: "Millimeters-per-second",
    162: "Millimeters-per-minute",
    163: "Meters-per-minute",
    164: "Meters-per-hour",
    165: "Cubic-meters-per-minute",
    166: "Meters-per-second-per-second",
    167: "Amperes-per-meter",
    168: "Amperes-per-square-meter",
    169: "Ampere-square-meters",
    170: "Farads",
    171: "Henrys",
    172: "Ohm-meters",
    173: "Siemens",
    174: "Siemens-per-meter",
    175: "Teslas",
    176: "Volts-per-degree-Kelvin",
    177: "Volts-per-meter",
    178: "Webers",
    179: "Candelas",
    180: "Candelas-per-square-meter",
    181: "Kelvins-per-hour",
    182: "Kelvins-per-minute",
    183: "Joule-seconds",
    185: "Square-meters-per-Newton",
    186: "Kilogram-per-cubic-meter",
    187: "Newton-seconds",
    188: "Newtons-per-meter",
    189: "Watts-per-meter-per-degree-Kelvin",
}

ICONS = {
    0: "mdi:temperature-celsius",
    1: "mdi:water-percent",
    2: "mdi:gauge",
    3: "mdi:speedometer",
    4: "mdi:percent",
    5: "mdi:air-filter",
    6: "mdi:fan",
    7: "mdi:flash",
    8: "mdi:current-ac",
    9: "mdi:flash",
    10: "mdi:flash",
    11: "mdi:flash",
    12: "mdi:counter",
    13: "mdi:thermometer-lines",
    14: "mdi:timer",
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up Zigbee Home Automation analog outputs."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation analog output from config entry."""

    async def async_discover(discovery_info):
        await _async_setup_entities(
            hass, config_entry, async_add_entities, [discovery_info]
        )

    unsub = async_dispatcher_connect(
        hass, ZHA_DISCOVERY_NEW.format(DOMAIN), async_discover
    )
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)

    analog_outputs = hass.data.get(DATA_ZHA, {}).get(DOMAIN)
    if analog_outputs is not None:
        await _async_setup_entities(
            hass, config_entry, async_add_entities, analog_outputs.values()
        )
        del hass.data[DATA_ZHA][DOMAIN]


async def _async_setup_entities(
    hass, config_entry, async_add_entities, discovery_infos
):
    """Set up the ZHA analog outputs."""
    entities = []
    for discovery_info in discovery_infos:
        entities.append(ZhaInputNumber(**discovery_info))

    async_add_entities(entities, update_before_add=True)


class ZhaInputNumber(ZhaEntity, InputNumber):
    """ZHA analog output."""

    def __init__(self, **kwargs):
        """Initialize the ZHA analog output."""
        super().__init__(**kwargs)

        config = OrderedDict()
        config[CONF_INITIAL] = None
        config[CONF_MIN] = 0.0
        config[CONF_MAX] = 100.0
        config[CONF_STEP] = 1.0
        config[CONF_MODE] = MODE_SLIDER
        config[CONF_ICON] = None
        config[ATTR_UNIT_OF_MEASUREMENT] = None
        InputNumber.__init__(self, config=config)

        self._channel = self.cluster_channels.get(CHANNEL_ANALOG_OUTPUT)

    async def async_set_value(self, value):
        """Set new value."""
        await self._channel.cluster.write_attributes({"present_value": value})
        await super().async_set_value(value)

    async def async_set_value_from_attr(self, value):
        """Handle state update from channel."""
        await super().async_set_value(value)

    async def async_increment(self):
        """Increment value."""
        await self.async_set_value(self._current_value + self._step)

    async def async_decrement(self):
        """Decrement value."""
        await self.async_set_value(self._current_value - self._step)

    @property
    def device_state_attributes(self):
        """Return state attributes."""
        return self.state_attributes

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        max_present_value = await self._channel.get_attribute_value("max_present_value")
        min_present_value = await self._channel.get_attribute_value("min_present_value")
        relinquish_default = await self._channel.get_attribute_value(
            "relinquish_default"
        )
        step = await self._channel.get_attribute_value("resolution")
        description = await self._channel.get_attribute_value("description")
        engineering_units = await self._channel.get_attribute_value("engineering_units")
        application_type = await self._channel.get_attribute_value("application_type")
        if max_present_value:
            self._config[CONF_MAX] = max_present_value
        if min_present_value:
            self._config[CONF_MIN] = min_present_value
        if relinquish_default:
            self._config[CONF_INITIAL] = relinquish_default
            if not self._current_value:
                self._current_value = relinquish_default
        if step and step > 0:
            self._config[CONF_STEP] = step
        if description and len(description) > 0:
            self._name = description
        if engineering_units:
            self._config[ATTR_UNIT_OF_MEASUREMENT] = UNITS.get(engineering_units)
        if application_type:
            self._config[CONF_ICON] = ICONS.get(application_type >> 16)
        await InputNumber.async_added_to_hass(self)
        await self.async_accept_signal(
            self._channel, SIGNAL_ATTR_UPDATED, self.async_set_value_from_attr
        )

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._current_value = last_state.state
        self._name = last_state.attributes.get(ATTR_FRIENDLY_NAME, self._name)
        self._config[CONF_INITIAL] = last_state.attributes.get(
            ATTR_INITIAL, self._config[CONF_INITIAL]
        )
        self._config[CONF_MIN] = last_state.attributes.get(
            ATTR_MIN, self._config[CONF_MIN]
        )
        self._config[CONF_MAX] = last_state.attributes.get(
            ATTR_MAX, self._config[CONF_MAX]
        )
        self._config[CONF_STEP] = last_state.attributes.get(
            ATTR_STEP, self._config[CONF_STEP]
        )
        self._config[CONF_MODE] = last_state.attributes.get(
            ATTR_MODE, self._config[CONF_MODE]
        )
        self._config[CONF_ICON] = last_state.attributes.get(
            ATTR_ICON, self._config[CONF_ICON]
        )
        self._config[ATTR_UNIT_OF_MEASUREMENT] = last_state.attributes.get(
            ATTR_UNIT_OF_MEASUREMENT, self._config[ATTR_UNIT_OF_MEASUREMENT]
        )

    async def async_update(self):
        """Attempt to retrieve state from the device."""
        await super().async_update()
        present_value = self._current_value = await self._channel.get_attribute_value(
            "present_value"
        )
        if present_value:
            self._current_value = present_value
