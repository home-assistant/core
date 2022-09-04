"""Constants for the EnOcean integration."""
import logging

from homeassistant.const import Platform

from .enocean_supported_device_type import EnOceanSupportedDeviceType

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

ENOCEAN_TEST_DIMMER = EnOceanSupportedDeviceType(
    eep="eltako_fud61npn", manufacturer="Eltako", model="FUD61NPN"
)

ENOCEAN_TEST_SWITCH = EnOceanSupportedDeviceType(
    eep="A5-12-01",
    manufacturer="Permundo",
    model="PSC234 (switch and power monitor)",
)

ENOCEAN_TEST_BINARY_SENSOR = EnOceanSupportedDeviceType(
    eep="F6-02-01",
    manufacturer="Generic",
    model="EEP F6-02-01 (Light and Blind Control - Application Style 2)",
)


ENOCEAN_SUPPORTED_DEVICES = [
    ENOCEAN_TEST_DIMMER,
    EnOceanSupportedDeviceType(
        eep="F6-02-01", manufacturer="Eltako", model="FT55 battery-less wall switch"
    ),
    EnOceanSupportedDeviceType(eep="F6-02-01", manufacturer="Jung", model="ENO Series"),
    EnOceanSupportedDeviceType(eep="F6-02-01", manufacturer="Omnio", model="WS-CH-102"),
    ENOCEAN_TEST_SWITCH,
    EnOceanSupportedDeviceType(
        eep="F6-10-00",
        manufacturer="Hoppe",
        model="SecuSignal window handle from Somfy",
    ),
    EnOceanSupportedDeviceType(
        eep="F6-02-01", manufacturer="TRIO2SYS", model="TRIO2SYS Wall switches "
    ),
    ENOCEAN_TEST_BINARY_SENSOR,
    EnOceanSupportedDeviceType(
        eep="F5-02-02",
        manufacturer="Generic",
        model="EEP F6-02-02 (Light and Blind Control - Application Style 1)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-01",
        manufacturer="Generic",
        model="EEP A5-02-01 (Temperature Sensor Range -40 °C to 0 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-02",
        manufacturer="Generic",
        model="EEP A5-02-02 (Temperature Sensor Range -30 °C to +10 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-03",
        manufacturer="Generic",
        model="EEP A5-02-03 (Temperature Sensor Range -20 °C to +20 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-04",
        manufacturer="Generic",
        model="EEP A5-02-04 (Temperature Sensor Range -10 °C to +30 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-05",
        manufacturer="Generic",
        model="EEP A5-02-05 (Temperature Sensor Range 0 °C to +40 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-06",
        manufacturer="Generic",
        model="EEP A5-02-06 (Temperature Sensor Range +10 °C to +50 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-07",
        manufacturer="Generic",
        model="EEP A5-02-07 (Temperature Sensor Range +20 °C to +60 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-08",
        manufacturer="Generic",
        model="EEP A5-02-08 (Temperature Sensor Range +30 °C to +70 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-09",
        manufacturer="Generic",
        model="EEP A5-02-09 (Temperature Sensor Range +40 °C to +80 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-0A",
        manufacturer="Generic",
        model="EEP A5-02-0A (Temperature Sensor Range +50 °C to +90 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-0B",
        manufacturer="Generic",
        model="EEP A5-02-0B (Temperature Sensor Range +60 °C to +100 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-10",
        manufacturer="Generic",
        model="EEP A5-02-10 (Temperature Sensor Range -60 °C to +20 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-11",
        manufacturer="Generic",
        model="EEP A5-02-11 (Temperature Sensor Range -50 °C to +30 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-12",
        manufacturer="Generic",
        model="EEP A5-02-12 (Temperature Sensor Range -40 °C to +40 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-13",
        manufacturer="Generic",
        model="EEP A5-02-13 (Temperature Sensor Range -30 °C to +50 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-14",
        manufacturer="Generic",
        model="EEP A5-02-14 (Temperature Sensor Range -20 °C to +60 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-15",
        manufacturer="Generic",
        model="EEP A5-02-15 (Temperature Sensor Range -10 °C to +70 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-16",
        manufacturer="Generic",
        model="EEP A5-02-16 (Temperature Sensor Range 0 °C to +80 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-17",
        manufacturer="Generic",
        model="EEP A5-02-17 (Temperature Sensor Range +10 °C to +90 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-18",
        manufacturer="Generic",
        model="EEP A5-02-18 (Temperature Sensor Range +20 °C to +100 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-19",
        manufacturer="Generic",
        model="EEP A5-02-19 (Temperature Sensor Range +30 °C to +110 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-1A",
        manufacturer="Generic",
        model="EEP A5-02-1A (Temperature Sensor Range +40 °C to +120 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-1B",
        manufacturer="Generic",
        model="EEP A5-02-1B (Temperature Sensor Range +50 °C to +130 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-12-01",
        manufacturer="Generic",
        model="EEP A5-12-01 (Light and Blind Control - Application Style 1)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-04-01",
        manufacturer="Generic",
        model="EEP A5-04-01 (Temp. and Humidity Sensor, Range 0°C to +40°C and 0% to 100%)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-04-02",
        manufacturer="Generic",
        model="EEP A5-04-02 (Temp. and Humidity Sensor, Range -20°C to +60°C and 0% to 100%)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-10-10",
        manufacturer="Generic",
        model="EEP A5-10-10 (Room Operating Panel)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-10-11",
        manufacturer="Generic",
        model="EEP A5-10-11 (Room Operating Panel)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-10-12",
        manufacturer="Generic",
        model="EEP A5-10-12 (Room Operating Panel)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-10-13",
        manufacturer="Generic",
        model="EEP A5-10-13 (Room Operating Panel)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-10-14",
        manufacturer="Generic",
        model="EEP A5-10-14 (Room Operating Panel)",
    ),
]
