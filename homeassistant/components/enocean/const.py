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

EEP_A5_12_01 = EnOceanSupportedDeviceType(
    eep="A5-12-01",
    model="EEP A5-12-01 (Light and Blind Control - Application Style 1)",
)

ENOCEAN_TEST_BINARY_SENSOR = EnOceanSupportedDeviceType(
    eep="F6-02-01",
    model="EEP F6-02-01 (Light and Blind Control - Application Style 2)",
)

# list of supported devices; contains not only generic EEPs but also a list of
# devices given by manufacturer and model (and the respective EEP)
ENOCEAN_SUPPORTED_DEVICES: list[EnOceanSupportedDeviceType] = [
    # Part 1/2: Generic EEPs
    EnOceanSupportedDeviceType(
        eep="F5-02-02",
        model="EEP F6-02-02 (Light and Blind Control - Application Style 1)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-01",
        model="EEP A5-02-01 (Temperature Sensor Range -40 °C to 0 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-02",
        model="EEP A5-02-02 (Temperature Sensor Range -30 °C to +10 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-03",
        model="EEP A5-02-03 (Temperature Sensor Range -20 °C to +20 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-04",
        model="EEP A5-02-04 (Temperature Sensor Range -10 °C to +30 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-05",
        model="EEP A5-02-05 (Temperature Sensor Range 0 °C to +40 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-06",
        model="EEP A5-02-06 (Temperature Sensor Range +10 °C to +50 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-07",
        model="EEP A5-02-07 (Temperature Sensor Range +20 °C to +60 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-08",
        model="EEP A5-02-08 (Temperature Sensor Range +30 °C to +70 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-09",
        model="EEP A5-02-09 (Temperature Sensor Range +40 °C to +80 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-0A",
        model="EEP A5-02-0A (Temperature Sensor Range +50 °C to +90 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-0B",
        model="EEP A5-02-0B (Temperature Sensor Range +60 °C to +100 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-10",
        model="EEP A5-02-10 (Temperature Sensor Range -60 °C to +20 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-11",
        model="EEP A5-02-11 (Temperature Sensor Range -50 °C to +30 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-12",
        model="EEP A5-02-12 (Temperature Sensor Range -40 °C to +40 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-13",
        model="EEP A5-02-13 (Temperature Sensor Range -30 °C to +50 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-14",
        model="EEP A5-02-14 (Temperature Sensor Range -20 °C to +60 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-15",
        model="EEP A5-02-15 (Temperature Sensor Range -10 °C to +70 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-16",
        model="EEP A5-02-16 (Temperature Sensor Range 0 °C to +80 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-17",
        model="EEP A5-02-17 (Temperature Sensor Range +10 °C to +90 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-18",
        model="EEP A5-02-18 (Temperature Sensor Range +20 °C to +100 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-19",
        model="EEP A5-02-19 (Temperature Sensor Range +30 °C to +110 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-1A",
        model="EEP A5-02-1A (Temperature Sensor Range +40 °C to +120 °C)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-02-1B",
        model="EEP A5-02-1B (Temperature Sensor Range +50 °C to +130 °C)",
    ),
    EEP_A5_12_01,
    EnOceanSupportedDeviceType(
        eep="A5-04-01",
        model="EEP A5-04-01 (Temperature and Humidity Sensor, Range 0 °C to +40 °C and 0% to 100%)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-04-02",
        model="EEP A5-04-02 (Temperature and Humidity Sensor, Range -20 °C to +60 °C and 0% to 100%)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-10-10",
        model="EEP A5-10-10 (Room Operating Panel)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-10-11",
        model="EEP A5-10-11 (Room Operating Panel)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-10-12",
        model="EEP A5-10-12 (Room Operating Panel)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-10-13",
        model="EEP A5-10-13 (Room Operating Panel)",
    ),
    EnOceanSupportedDeviceType(
        eep="A5-10-14",
        model="EEP A5-10-14 (Room Operating Panel)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-00",
        model="EEP D2-01-00 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 00)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-01",
        model="EEP D2-01-01 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 01)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-03",
        model="EEP D2-01-03 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 03)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-04",
        model="EEP D2-01-04 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 04)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-05",
        model="EEP D2-01-05 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 05)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-06",
        model="EEP D2-01-06 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 06)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-07",
        model="EEP D2-01-07 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 07)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-08",
        model="EEP D2-01-08 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 08)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-09",
        model="EEP D2-01-09 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 09)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-0A",
        model="EEP D2-01-0A (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0A)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-0B",
        model="EEP D2-01-0B (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0B)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-0C",
        model="EEP D2-01-0C (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0C)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-0D",
        model="EEP D2-01-0D (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0D)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-0E",
        model="EEP D2-01-0E (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0E)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-0F",
        model="EEP D2-01-0F (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0F)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-10",
        model="EEP D2-01-10 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 10)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-11",
        model="EEP D2-01-11 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 11)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-12",
        model="EEP D2-01-12 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 12)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-13",
        model="EEP D2-01-13 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 13)",
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-14",
        model="EEP D2-01-14 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 14)",
    ),
    # Part 2/2: specific devices by manufacturer and model (and EEP)
    ENOCEAN_TEST_DIMMER,
    EnOceanSupportedDeviceType(
        eep="F6-02-01", manufacturer="Eltako", model="FT55 battery-less wall switch"
    ),
    EnOceanSupportedDeviceType(eep="F6-02-01", manufacturer="Jung", model="ENO Series"),
    EnOceanSupportedDeviceType(eep="F6-02-01", manufacturer="Omnio", model="WS-CH-102"),
    EEP_A5_12_01,
    EnOceanSupportedDeviceType(
        eep="F6-10-00",
        manufacturer="Hoppe",
        model="SecuSignal window handle from Somfy",
    ),
    EnOceanSupportedDeviceType(
        eep="F6-02-01", manufacturer="TRIO2SYS", model="TRIO2SYS Wall switches "
    ),
    EnOceanSupportedDeviceType(
        eep="D2-01-09",
        manufacturer="Permundo",
        model="PSC234 (switch and power monitor)",
    ),
    ENOCEAN_TEST_BINARY_SENSOR,
]
