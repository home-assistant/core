"""Support for ISY994 sensors."""
import logging
from typing import Callable

from homeassistant.components.sensor import DOMAIN
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    LENGTH_CENTIMETERS,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    MASS_KILOGRAMS,
    POWER_WATT,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TIME_DAYS,
    TIME_HOURS,
    TIME_MILLISECONDS,
    TIME_MINUTES,
    TIME_MONTHS,
    TIME_SECONDS,
    TIME_YEARS,
    UNIT_DEGREE,
    UNIT_PERCENTAGE,
    UNIT_UV_INDEX,
    UNIT_VOLT,
)
from homeassistant.helpers.typing import ConfigType

from . import ISY994_NODES, ISY994_WEATHER, ISYDevice

_LOGGER = logging.getLogger(__name__)

UOM_FRIENDLY_NAME = {
    "1": "amp",
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
    "14": UNIT_DEGREE,
    "16": "macroseismic",
    "17": TEMP_FAHRENHEIT,
    "18": "ft",
    "19": TIME_HOURS,
    "20": TIME_HOURS,
    "21": "abs. humidity (%)",
    "22": "rel. humidity (%)",
    "23": "inHg",
    "24": "in/hr",
    "25": "index",
    "26": "K",
    "27": "keyword",
    "28": MASS_KILOGRAMS,
    "29": "kV",
    "30": "kW",
    "31": "kPa",
    "32": SPEED_KILOMETERS_PER_HOUR,
    "33": "kWH",
    "34": "liedu",
    "35": "l",
    "36": "lx",
    "37": "mercalli",
    "38": LENGTH_METERS,
    "39": "m³/hr",
    "40": SPEED_METERS_PER_SECOND,
    "41": "mA",
    "42": TIME_MILLISECONDS,
    "43": "mV",
    "44": TIME_MINUTES,
    "45": TIME_MINUTES,
    "46": "mm/hr",
    "47": TIME_MONTHS,
    "48": SPEED_MILES_PER_HOUR,
    "49": SPEED_METERS_PER_SECOND,
    "50": "ohm",
    "51": UNIT_PERCENTAGE,
    "52": "lb",
    "53": "power factor",
    "54": CONCENTRATION_PARTS_PER_MILLION,
    "55": "pulse count",
    "57": TIME_SECONDS,
    "58": TIME_SECONDS,
    "59": "seimens/m",
    "60": "body wave magnitude scale",
    "61": "Ricter scale",
    "62": "moment magnitude scale",
    "63": "surface wave magnitude scale",
    "64": "shindo",
    "65": "SML",
    "69": "gal",
    "71": UNIT_UV_INDEX,
    "72": UNIT_VOLT,
    "73": POWER_WATT,
    "74": f"{POWER_WATT}/m²",
    "75": "weekday",
    "76": f"Wind Direction ({UNIT_DEGREE})",
    "77": TIME_YEARS,
    "82": "mm",
    "83": LENGTH_KILOMETERS,
    "85": "ohm",
    "86": "kOhm",
    "87": "m³/m³",
    "88": "Water activity",
    "89": "RPM",
    "90": "Hz",
    "91": f"{UNIT_DEGREE} (Relative to North)",
    "92": f"{UNIT_DEGREE} (Relative to South)",
}

UOM_TO_STATES = {
    "11": {"0": "unlocked", "100": "locked", "102": "jammed"},
    "15": {
        "1": "master code changed",
        "2": "tamper code entry limit",
        "3": "escutcheon removed",
        "4": "key/manually locked",
        "5": "locked by touch",
        "6": "key/manually unlocked",
        "7": "remote locking jammed bolt",
        "8": "remotely locked",
        "9": "remotely unlocked",
        "10": "deadbolt jammed",
        "11": "battery too low to operate",
        "12": "critical low battery",
        "13": "low battery",
        "14": "automatically locked",
        "15": "automatic locking jammed bolt",
        "16": "remotely power cycled",
        "17": "lock handling complete",
        "19": "user deleted",
        "20": "user added",
        "21": "duplicate pin",
        "22": "jammed bolt by locking with keypad",
        "23": "locked by keypad",
        "24": "unlocked by keypad",
        "25": "keypad attempt outside schedule",
        "26": "hardware failure",
        "27": "factory reset",
    },
    "66": {
        "0": "idle",
        "1": "heating",
        "2": "cooling",
        "3": "fan only",
        "4": "pending heat",
        "5": "pending cool",
        "6": "vent",
        "7": "aux heat",
        "8": "2nd stage heating",
        "9": "2nd stage cooling",
        "10": "2nd stage aux heat",
        "11": "3rd stage aux heat",
    },
    "67": {
        "0": "off",
        "1": "heat",
        "2": "cool",
        "3": "auto",
        "4": "aux/emergency heat",
        "5": "resume",
        "6": "fan only",
        "7": "furnace",
        "8": "dry air",
        "9": "moist air",
        "10": "auto changeover",
        "11": "energy save heat",
        "12": "energy save cool",
        "13": "away",
    },
    "68": {
        "0": "auto",
        "1": "on",
        "2": "auto high",
        "3": "high",
        "4": "auto medium",
        "5": "medium",
        "6": "circulation",
        "7": "humidity circulation",
    },
    "93": {
        "1": "power applied",
        "2": "ac mains disconnected",
        "3": "ac mains reconnected",
        "4": "surge detection",
        "5": "volt drop or drift",
        "6": "over current detected",
        "7": "over voltage detected",
        "8": "over load detected",
        "9": "load error",
        "10": "replace battery soon",
        "11": "replace battery now",
        "12": "battery is charging",
        "13": "battery is fully charged",
        "14": "charge battery soon",
        "15": "charge battery now",
    },
    "94": {
        "1": "program started",
        "2": "program in progress",
        "3": "program completed",
        "4": "replace main filter",
        "5": "failure to set target temperature",
        "6": "supplying water",
        "7": "water supply failure",
        "8": "boiling",
        "9": "boiling failure",
        "10": "washing",
        "11": "washing failure",
        "12": "rinsing",
        "13": "rinsing failure",
        "14": "draining",
        "15": "draining failure",
        "16": "spinning",
        "17": "spinning failure",
        "18": "drying",
        "19": "drying failure",
        "20": "fan failure",
        "21": "compressor failure",
    },
    "95": {
        "1": "leaving bed",
        "2": "sitting on bed",
        "3": "lying on bed",
        "4": "posture changed",
        "5": "sitting on edge of bed",
    },
    "96": {
        "1": "clean",
        "2": "slightly polluted",
        "3": "moderately polluted",
        "4": "highly polluted",
    },
    "97": {
        "0": "closed",
        "100": "open",
        "102": "stopped",
        "103": "closing",
        "104": "opening",
    },
}


def setup_platform(
    hass, config: ConfigType, add_entities: Callable[[list], None], discovery_info=None
):
    """Set up the ISY994 sensor platform."""
    devices = []

    for node in hass.data[ISY994_NODES][DOMAIN]:
        _LOGGER.debug("Loading %s", node.name)
        devices.append(ISYSensorDevice(node))

    for node in hass.data[ISY994_WEATHER]:
        devices.append(ISYWeatherDevice(node))

    add_entities(devices)


class ISYSensorDevice(ISYDevice):
    """Representation of an ISY994 sensor device."""

    @property
    def raw_unit_of_measurement(self) -> str:
        """Get the raw unit of measurement for the ISY994 sensor device."""
        if len(self._node.uom) == 1:
            if self._node.uom[0] in UOM_FRIENDLY_NAME:
                friendly_name = UOM_FRIENDLY_NAME.get(self._node.uom[0])
                if friendly_name in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
                    friendly_name = self.hass.config.units.temperature_unit
                return friendly_name
            return self._node.uom[0]
        return None

    @property
    def state(self) -> str:
        """Get the state of the ISY994 sensor device."""
        if self.is_unknown():
            return None

        if len(self._node.uom) == 1:
            if self._node.uom[0] in UOM_TO_STATES:
                states = UOM_TO_STATES.get(self._node.uom[0])
                if self.value in states:
                    return states.get(self.value)
            elif self._node.prec and self._node.prec != [0]:
                str_val = str(self.value)
                int_prec = int(self._node.prec)
                decimal_part = str_val[-int_prec:]
                whole_part = str_val[: len(str_val) - int_prec]
                val = float(f"{whole_part}.{decimal_part}")
                raw_units = self.raw_unit_of_measurement
                if raw_units in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
                    val = self.hass.config.units.temperature(val, raw_units)

                return str(val)
            else:
                return self.value

        return None

    @property
    def unit_of_measurement(self) -> str:
        """Get the unit of measurement for the ISY994 sensor device."""
        raw_units = self.raw_unit_of_measurement
        if raw_units in (TEMP_FAHRENHEIT, TEMP_CELSIUS):
            return self.hass.config.units.temperature_unit
        return raw_units


class ISYWeatherDevice(ISYDevice):
    """Representation of an ISY994 weather device."""

    @property
    def raw_units(self) -> str:
        """Return the raw unit of measurement."""
        if self._node.uom == "F":
            return TEMP_FAHRENHEIT
        if self._node.uom == "C":
            return TEMP_CELSIUS
        return self._node.uom

    @property
    def state(self) -> object:
        """Return the value of the node."""
        # pylint: disable=protected-access
        val = self._node.status._val
        raw_units = self._node.uom

        if raw_units in [TEMP_CELSIUS, TEMP_FAHRENHEIT]:
            return self.hass.config.units.temperature(val, raw_units)
        return val

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement for the node."""
        raw_units = self.raw_units

        if raw_units in [TEMP_CELSIUS, TEMP_FAHRENHEIT]:
            return self.hass.config.units.temperature_unit
        return raw_units
