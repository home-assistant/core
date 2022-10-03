"""Module containing a representation of a supported EnOcean device type."""
from homeassistant.helpers import selector


class EnOceanSupportedDeviceType:
    """Representation of a supported EnOcean device type."""

    manufacturer: str
    model: str
    eep: str

    def __init__(
        self, manufacturer: str = "Generic", model: str = "", eep: str = ""
    ) -> None:
        """Construct an EnOcean device type."""
        self.manufacturer = manufacturer
        self.model = model
        self.eep = eep

    @property
    def unique_id(self) -> str:
        """Return a unique id for this device type."""
        return (
            self.eep.replace(";", "")
            + ";"
            + self.manufacturer.replace(";", "")
            + ";"
            + self.model.replace(";", "")
        )

    @property
    def select_option_dict(self) -> selector.SelectOptionDict:
        """Return a SelectOptionDict."""
        return selector.SelectOptionDict(
            value=self.unique_id, label=self.manufacturer + " " + self.model
        )


# A5-02 Temperature Sensors
EEP_A5_02_01 = EnOceanSupportedDeviceType(
    eep="A5-02-01",
    model="EEP A5-02-01 (Temperature Sensor Range -40 °C to 0 °C)",
)

EEP_A5_02_02 = EnOceanSupportedDeviceType(
    eep="A5-02-02",
    model="EEP A5-02-02 (Temperature Sensor Range -30 °C to +10 °C)",
)

EEP_A5_02_03 = EnOceanSupportedDeviceType(
    eep="A5-02-03",
    model="EEP A5-02-03 (Temperature Sensor Range -20 °C to +20 °C)",
)

EEP_A5_02_04 = EnOceanSupportedDeviceType(
    eep="A5-02-04",
    model="EEP A5-02-04 (Temperature Sensor Range -10 °C to +30 °C)",
)

EEP_A5_02_05 = EnOceanSupportedDeviceType(
    eep="A5-02-05",
    model="EEP A5-02-05 (Temperature Sensor Range 0 °C to +40 °C)",
)

EEP_A5_02_06 = EnOceanSupportedDeviceType(
    eep="A5-02-06",
    model="EEP A5-02-06 (Temperature Sensor Range +10 °C to +50 °C)",
)

EEP_A5_02_07 = EnOceanSupportedDeviceType(
    eep="A5-02-07",
    model="EEP A5-02-07 (Temperature Sensor Range +20 °C to +60 °C)",
)

EEP_A5_02_08 = EnOceanSupportedDeviceType(
    eep="A5-02-08",
    model="EEP A5-02-08 (Temperature Sensor Range +30 °C to +70 °C)",
)

EEP_A5_02_09 = EnOceanSupportedDeviceType(
    eep="A5-02-09",
    model="EEP A5-02-09 (Temperature Sensor Range +40 °C to +80 °C)",
)

EEP_A5_02_0A = EnOceanSupportedDeviceType(
    eep="A5-02-0A",
    model="EEP A5-02-0A (Temperature Sensor Range +50 °C to +90 °C)",
)

EEP_A5_02_0B = EnOceanSupportedDeviceType(
    eep="A5-02-0B",
    model="EEP A5-02-0B (Temperature Sensor Range +60 °C to +100 °C)",
)

EEP_A5_02_10 = EnOceanSupportedDeviceType(
    eep="A5-02-10",
    model="EEP A5-02-10 (Temperature Sensor Range -60 °C to +20 °C)",
)

EEP_A5_02_11 = EnOceanSupportedDeviceType(
    eep="A5-02-11",
    model="EEP A5-02-11 (Temperature Sensor Range -50 °C to +30 °C)",
)

EEP_A5_02_12 = EnOceanSupportedDeviceType(
    eep="A5-02-12",
    model="EEP A5-02-12 (Temperature Sensor Range -40 °C to +40 °C)",
)

EEP_A5_02_13 = EnOceanSupportedDeviceType(
    eep="A5-02-13",
    model="EEP A5-02-13 (Temperature Sensor Range -30 °C to +50 °C)",
)

EEP_A5_02_14 = EnOceanSupportedDeviceType(
    eep="A5-02-14",
    model="EEP A5-02-14 (Temperature Sensor Range -20 °C to +60 °C)",
)

EEP_A5_02_15 = EnOceanSupportedDeviceType(
    eep="A5-02-15",
    model="EEP A5-02-15 (Temperature Sensor Range -10 °C to +70 °C)",
)

EEP_A5_02_16 = EnOceanSupportedDeviceType(
    eep="A5-02-16",
    model="EEP A5-02-16 (Temperature Sensor Range 0 °C to +80 °C)",
)

EEP_A5_02_17 = EnOceanSupportedDeviceType(
    eep="A5-02-17",
    model="EEP A5-02-17 (Temperature Sensor Range +10 °C to +90 °C)",
)

EEP_A5_02_18 = EnOceanSupportedDeviceType(
    eep="A5-02-18",
    model="EEP A5-02-18 (Temperature Sensor Range +20 °C to +100 °C)",
)

EEP_A5_02_19 = EnOceanSupportedDeviceType(
    eep="A5-02-19",
    model="EEP A5-02-19 (Temperature Sensor Range +30 °C to +110 °C)",
)

EEP_A5_02_1A = EnOceanSupportedDeviceType(
    eep="A5-02-1A",
    model="EEP A5-02-1A (Temperature Sensor Range +40 °C to +120 °C)",
)

EEP_A5_02_1B = EnOceanSupportedDeviceType(
    eep="A5-02-1B",
    model="EEP A5-02-1B (Temperature Sensor Range +50 °C to +130 °C)",
)

# A5-04 Temperature and Humidity sensors (only types 1 and 2)
EEP_A5_04_01 = EnOceanSupportedDeviceType(
    eep="A5-04-01",
    model="EEP A5-04-01 (Temperature and Humidity Sensor, Range 0 °C to +40 °C and 0% to 100%)",
)

EEP_A5_04_02 = EnOceanSupportedDeviceType(
    eep="A5-04-02",
    model="EEP A5-04-02 (Temperature and Humidity Sensor, Range -20 °C to +60 °C and 0% to 100%)",
)


# A5-10 Room Operating Panels
EEP_A5_10_01 = EnOceanSupportedDeviceType(
    eep="A5-10-01",
    model="EEP A5-10-01 Room Operating Panel (Temperature Sensor, Set Point, Fan Speed and Occupancy Control)",
)

EEP_A5_10_02 = EnOceanSupportedDeviceType(
    eep="A5-10-02",
    model="EEP A5-10-02 Room Operating Panel (Temperature Sensor, Set Point Control)",
)

EEP_A5_10_03 = EnOceanSupportedDeviceType(
    eep="A5-10-03",
    model="EEP A5-10-03 Room Operating Panel (Temperature Sensor, Set Point Control)",
)

EEP_A5_10_04 = EnOceanSupportedDeviceType(
    eep="A5-10-04",
    model="EEP A5-10-04 Room Operating Panel (Temperature Sensor, Set Point and Fan Speed Control)",
)

EEP_A5_10_05 = EnOceanSupportedDeviceType(
    eep="A5-10-05",
    model="EEP A5-10-05 Room Operating Panel (Temperature Sensor, Set Point and Occupancy Control)",
)

EEP_A5_10_06 = EnOceanSupportedDeviceType(
    eep="A5-10-06",
    model="EEP A5-10-06 Room Operating Panel (Temperature Sensor, Set Point and Day/Night Control)",
)

EEP_A5_10_07 = EnOceanSupportedDeviceType(
    eep="A5-10-07",
    model="EEP A5-10-07 Room Operating Panel (Temperature Sensor, Fan Speed Control)",
)

EEP_A5_10_08 = EnOceanSupportedDeviceType(
    eep="A5-10-08",
    model="EEP A5-10-08 Room Operating Panel (Temperature Sensor, Fan Speed and Occupancy Control)",
)

EEP_A5_10_09 = EnOceanSupportedDeviceType(
    eep="A5-10-09",
    model="EEP A5-10-09 Room Operating Panel (Temperature Sensor, Fan Speed and Day/Night Control)",
)

EEP_A5_10_0A = EnOceanSupportedDeviceType(
    eep="A5-10-0A",
    model="EEP A5-10-0A Room Operating Panel (Temperature Sensor, Set Point Adjust and Single Input Contact)",
)

EEP_A5_10_0B = EnOceanSupportedDeviceType(
    eep="A5-10-0B",
    model="EEP A5-10-0B Room Operating Panel (Temperature Sensor and Single Input Contact)",
)

EEP_A5_10_0C = EnOceanSupportedDeviceType(
    eep="A5-10-0C",
    model="EEP A5-10-0C Room Operating Panel (Temperature Sensor and Occupancy Control)",
)

EEP_A5_10_0D = EnOceanSupportedDeviceType(
    eep="A5-10-0D",
    model="EEP A5-10-0D Room Operating Panel (Temperature Sensor and Day/Night Control)",
)

EEP_A5_10_10 = EnOceanSupportedDeviceType(
    eep="A5-10-10",
    model="EEP A5-10-10 Room Operating Panel (Temperature and Humidity Sensor, Set Point and Occupancy Control)",
)

EEP_A5_10_11 = EnOceanSupportedDeviceType(
    eep="A5-10-11",
    model="EEP A5-10-11 Room Operating Panel (Temperature and Humidity Sensor, Set Point and Day/Night Control)",
)

EEP_A5_10_12 = EnOceanSupportedDeviceType(
    eep="A5-10-12",
    model="EEP A5-10-12 Room Operating Panel (Temperature and Humidity Sensor and Set Point)",
)

EEP_A5_10_13 = EnOceanSupportedDeviceType(
    eep="A5-10-13",
    model="EEP A5-10-13 Room Operating Panel (Temperature and Humidity Sensor, Occupancy Control)",
)

EEP_A5_10_14 = EnOceanSupportedDeviceType(
    eep="A5-10-14",
    model="EEP A5-10-14 Room Operating Panel (Temperature and Humidity Sensor, Day/Night Control)",
)

# A5-12 Automated Meter Reading
EEP_A5_12_01 = EnOceanSupportedDeviceType(
    eep="A5-12-01",
    model="EEP A5-12-01 (Automated Meter Reading [AMR] - Electricity)",
)

# D2-01 Electronic Switches and Dimmers with Energy Measurement and Local Control
EEP_D2_01_00 = EnOceanSupportedDeviceType(
    eep="D2-01-00",
    model="EEP D2-01-00 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 00)",
)

EEP_D2_01_01 = EnOceanSupportedDeviceType(
    eep="D2-01-01",
    model="EEP D2-01-01 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 01)",
)

EEP_D2_01_03 = EnOceanSupportedDeviceType(
    eep="D2-01-03",
    model="EEP D2-01-03 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 03)",
)

EEP_D2_01_04 = EnOceanSupportedDeviceType(
    eep="D2-01-04",
    model="EEP D2-01-04 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 04)",
)

EEP_D2_01_05 = EnOceanSupportedDeviceType(
    eep="D2-01-05",
    model="EEP D2-01-05 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 05)",
)

EEP_D2_01_06 = EnOceanSupportedDeviceType(
    eep="D2-01-06",
    model="EEP D2-01-06 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 06)",
)

EEP_D2_01_07 = EnOceanSupportedDeviceType(
    eep="D2-01-07",
    model="EEP D2-01-07 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 07)",
)

EEP_D2_01_08 = EnOceanSupportedDeviceType(
    eep="D2-01-08",
    model="EEP D2-01-08 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 08)",
)

EEP_D2_01_09 = EnOceanSupportedDeviceType(
    eep="D2-01-09",
    model="EEP D2-01-09 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 09)",
)

EEP_D2_01_0A = EnOceanSupportedDeviceType(
    eep="D2-01-0A",
    model="EEP D2-01-0A (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0A)",
)

EEP_D2_01_0B = EnOceanSupportedDeviceType(
    eep="D2-01-0B",
    model="EEP D2-01-0B (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0B)",
)

EEP_D2_01_0C = EnOceanSupportedDeviceType(
    eep="D2-01-0C",
    model="EEP D2-01-0C (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0C)",
)

EEP_D2_01_0D = EnOceanSupportedDeviceType(
    eep="D2-01-0D",
    model="EEP D2-01-0D (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0D)",
)

EEP_D2_01_0E = EnOceanSupportedDeviceType(
    eep="D2-01-0E",
    model="EEP D2-01-0E (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0E)",
)

EEP_D2_01_0F = EnOceanSupportedDeviceType(
    eep="D2-01-0F",
    model="EEP D2-01-0F (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0F)",
)

EEP_D2_01_10 = EnOceanSupportedDeviceType(
    eep="D2-01-10",
    model="EEP D2-01-10 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 10)",
)

EEP_D2_01_11 = EnOceanSupportedDeviceType(
    eep="D2-01-11",
    model="EEP D2-01-11 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 11)",
)

EEP_D2_01_12 = EnOceanSupportedDeviceType(
    eep="D2-01-12",
    model="EEP D2-01-12 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 12)",
)

EEP_D2_01_13 = EnOceanSupportedDeviceType(
    eep="D2-01-13",
    model="EEP D2-01-13 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 13)",
)

EEP_D2_01_14 = EnOceanSupportedDeviceType(
    eep="D2-01-14",
    model="EEP D2-01-14 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 14)",
)

# F6-02 Light and Blind Control
EEP_F6_02_01 = EnOceanSupportedDeviceType(
    eep="F6-02-01",
    model="EEP F6-02-01 (Light and Blind Control - Application Style 2)",
)

EEP_F6_02_02 = EnOceanSupportedDeviceType(
    eep="F6-02-02",
    model="EEP F6-02-02 (Light and Blind Control - Application Style 1)",
)

# F6-10-00 Window Handle
EEP_F6_10_00 = EnOceanSupportedDeviceType(
    eep="F6-10-00",
    model="EEP F6-10-00 (Mechanical Handle - Window Handle)",
)


# Other Devices
ELTAKO_FUD61 = EnOceanSupportedDeviceType(
    eep="A5-38-08_EltakoFUD61", manufacturer="Eltako", model="FUD61NPN"
)

ELTAKO_FT55 = EnOceanSupportedDeviceType(
    eep="F6-02-01", manufacturer="Eltako", model="FT55 battery-less wall switch"
)

JUNG_ENO = EnOceanSupportedDeviceType(
    eep="F6-02-01", manufacturer="Jung", model="ENO Series"
)

OMNIO_WS_CH_102 = EnOceanSupportedDeviceType(
    eep="F6-02-01", manufacturer="Omnio", model="WS-CH-102"
)

HOPPE_SECUSIGNAL = EnOceanSupportedDeviceType(
    eep="F6-10-00",
    manufacturer="Hoppe",
    model="SecuSignal window handle from Somfy",
)

TRIO2SYS = EnOceanSupportedDeviceType(
    eep="F6-02-01", manufacturer="TRIO2SYS", model="TRIO2SYS Wall switches "
)

NODON_SIN_2_1_01 = EnOceanSupportedDeviceType(
    eep="D2-01-0F",
    manufacturer="NodOn",
    model="SIN-2-1-01",
)

NODON_SIN_2_2_01 = EnOceanSupportedDeviceType(
    eep="D2-01-12",
    manufacturer="NodOn",
    model="SIN-2-2-01",
)


PERMUNDO_PSC234 = EnOceanSupportedDeviceType(
    eep="D2-01-09",
    manufacturer="Permundo",
    model="PSC234 (switch and power monitor)",
)

# list of supported devices; contains not only generic EEPs but also a list of
# devices given by manufacturer and model (and the respective EEP)
ENOCEAN_SUPPORTED_DEVICES: list[EnOceanSupportedDeviceType] = [
    # Part 1/2: Generic EEPs
    # A5-02
    EEP_A5_02_01,
    EEP_A5_02_02,
    EEP_A5_02_03,
    EEP_A5_02_04,
    EEP_A5_02_05,
    EEP_A5_02_06,
    EEP_A5_02_07,
    EEP_A5_02_08,
    EEP_A5_02_09,
    EEP_A5_02_0A,
    EEP_A5_02_0B,
    EEP_A5_02_10,
    EEP_A5_02_11,
    EEP_A5_02_12,
    EEP_A5_02_13,
    EEP_A5_02_14,
    EEP_A5_02_15,
    EEP_A5_02_16,
    EEP_A5_02_17,
    EEP_A5_02_18,
    EEP_A5_02_19,
    EEP_A5_02_1A,
    EEP_A5_02_1B,
    # A5-04
    EEP_A5_04_01,
    EEP_A5_04_02,
    # A5-10
    EEP_A5_10_01,
    EEP_A5_10_02,
    EEP_A5_10_03,
    EEP_A5_10_04,
    EEP_A5_10_05,
    EEP_A5_10_06,
    EEP_A5_10_07,
    EEP_A5_10_08,
    EEP_A5_10_09,
    EEP_A5_10_0A,
    EEP_A5_10_0B,
    EEP_A5_10_0C,
    EEP_A5_10_0D,
    EEP_A5_10_10,
    EEP_A5_10_11,
    EEP_A5_10_12,
    EEP_A5_10_13,
    EEP_A5_10_14,
    # A5-12
    EEP_A5_12_01,
    # D2-01
    EEP_D2_01_00,
    EEP_D2_01_01,
    EEP_D2_01_03,
    EEP_D2_01_04,
    EEP_D2_01_05,
    EEP_D2_01_06,
    EEP_D2_01_07,
    EEP_D2_01_08,
    EEP_D2_01_09,
    EEP_D2_01_0A,
    EEP_D2_01_0B,
    EEP_D2_01_0C,
    EEP_D2_01_0D,
    EEP_D2_01_0E,
    EEP_D2_01_0F,
    EEP_D2_01_10,
    EEP_D2_01_11,
    EEP_D2_01_12,
    EEP_D2_01_13,
    EEP_D2_01_14,
    # F6-02
    EEP_F6_02_01,
    EEP_F6_02_02,
    # F6-10-00
    EEP_F6_10_00,
    # Part 2/2: specific devices by manufacturer and model (and EEP)
    ELTAKO_FUD61,
    ELTAKO_FT55,
    HOPPE_SECUSIGNAL,
    JUNG_ENO,
    NODON_SIN_2_1_01,
    NODON_SIN_2_2_01,
    OMNIO_WS_CH_102,
    PERMUNDO_PSC234,
    TRIO2SYS,
]
