"""Constants for the ENOcean integration."""
import logging

from homeassistant.const import Platform
from homeassistant.helpers import selector

DOMAIN = "enocean"
DATA_ENOCEAN = "enocean"
ENOCEAN_DONGLE = "dongle"

ERROR_INVALID_DONGLE_PATH = "invalid_dongle_path"

SIGNAL_RECEIVE_MESSAGE = "enocean.receive_message"
SIGNAL_SEND_MESSAGE = "enocean.send_message"

LOGGER = logging.getLogger(__package__)

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]

ENOCEAN_EQUIPMENT_PROFILES = [
    selector.SelectOptionDict(value="eltako_fud61npn", label="Eltako FUD61NPN"),
    selector.SelectOptionDict(
        value="F6-02-01", label="Eltako FT55 battery-less wall switch"
    ),
    selector.SelectOptionDict(value="F6-02-01", label="Jung ENO Series"),
    selector.SelectOptionDict(value="F6-02-01", label="Omnio WS-CH-102"),
    selector.SelectOptionDict(
        value="A5-12-01", label="Permundo PSC234 (switch and power monitor)"
    ),
    selector.SelectOptionDict(
        value="F6-10-00", label="Hoppe SecuSignal window handle from Somfy"
    ),
    selector.SelectOptionDict(value="F6-02-01", label="TRIO2SYS Wall switches "),
    selector.SelectOptionDict(
        value="F6-02-01",
        label="Generic EEP F6-02-01 (Light and Blind Control - Application Style 2)",
    ),
    selector.SelectOptionDict(
        value="F5-02-02",
        label="Generic EEP F6-02-02 (Light and Blind Control - Application Style 1)",
    ),
    selector.SelectOptionDict(
        value="A5-02-01",
        label="Generic EEP A5-02-01 (Temperature Sensor Range -40 °C to 0 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-02",
        label="Generic EEP A5-02-02 (Temperature Sensor Range -30 °C to +10 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-03",
        label="Generic EEP A5-02-03 (Temperature Sensor Range -20 °C to +20 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-04",
        label="Generic EEP A5-02-04 (Temperature Sensor Range -10 °C to +30 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-05",
        label="Generic EEP A5-02-05 (Temperature Sensor Range 0 °C to +40 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-06",
        label="Generic EEP A5-02-06 (Temperature Sensor Range +10 °C to +50 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-07",
        label="Generic EEP A5-02-07 (Temperature Sensor Range +20 °C to +60 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-08",
        label="Generic EEP A5-02-08 (Temperature Sensor Range +30 °C to +70 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-09",
        label="Generic EEP A5-02-09 (Temperature Sensor Range +40 °C to +80 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-0A",
        label="Generic EEP A5-02-0A (Temperature Sensor Range +50 °C to +90 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-0B",
        label="Generic EEP A5-02-0B (Temperature Sensor Range +60 °C to +100 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-10",
        label="Generic EEP A5-02-10 (Temperature Sensor Range -60 °C to +20 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-11",
        label="Generic EEP A5-02-11 (Temperature Sensor Range -50 °C to +30 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-12",
        label="Generic EEP A5-02-12 (Temperature Sensor Range -40 °C to +40 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-13",
        label="Generic EEP A5-02-13 (Temperature Sensor Range -30 °C to +50 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-14",
        label="Generic EEP A5-02-14 (Temperature Sensor Range -20 °C to +60 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-15",
        label="Generic EEP A5-02-15 (Temperature Sensor Range -10 °C to +70 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-16",
        label="Generic EEP A5-02-16 (Temperature Sensor Range 0 °C to +80 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-17",
        label="Generic EEP A5-02-17 (Temperature Sensor Range +10 °C to +90 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-18",
        label="Generic EEP A5-02-18 (Temperature Sensor Range +20 °C to +100 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-19",
        label="Generic EEP A5-02-19 (Temperature Sensor Range +30 °C to +110 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-1A",
        label="Generic EEP A5-02-1A (Temperature Sensor Range +40 °C to +120 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-02-1B",
        label="Generic EEP A5-02-1B (Temperature Sensor Range +50 °C to +130 °C)",
    ),
    selector.SelectOptionDict(
        value="A5-12-01",
        label="Generic EEP A5-12-01 (Light and Blind Control - Application Style 1)",
    ),
    selector.SelectOptionDict(
        value="A5-04-01",
        label="Generic EEP A5-04-01 (Temp. and Humidity Sensor, Range 0°C to +40°C and 0% to 100%)",
    ),
    selector.SelectOptionDict(
        value="A5-04-02",
        label="Generic EEP A5-04-02 (Temp. and Humidity Sensor, Range -20°C to +60°C and 0% to 100%)",
    ),
    selector.SelectOptionDict(
        value="A5-10-10", label="Generic EEP A5-10-10 (Room Operating Panel)"
    ),
    selector.SelectOptionDict(
        value="A5-10-11", label="Generic EEP A5-10-11 (Room Operating Panel)"
    ),
    selector.SelectOptionDict(
        value="A5-10-12", label="Generic EEP A5-10-12 (Room Operating Panel)"
    ),
    selector.SelectOptionDict(
        value="A5-10-13", label="Generic EEP A5-10-13 (Room Operating Panel)"
    ),
    selector.SelectOptionDict(
        value="A5-10-14", label="Generic EEP A5-10-14 (Room Operating Panel)"
    ),
]
