"""Module containing a representation of a supported EnOcean device type."""

from homeassistant.helpers import selector


class EnOceanSupportedDeviceType:
    """Representation of a supported EnOcean device type."""

    unique_id: str
    eep: str
    manufacturer: str
    model: str

    def __init__(
        self,
        unique_id: str = "",
        eep: str = "",
        model: str = "",
        manufacturer: str = "Generic",
    ) -> None:
        """Construct an EnOcean device type."""
        self.unique_id = unique_id
        self.eep = eep
        self.model = model
        self.manufacturer = manufacturer

    @property
    def select_option_dict(self) -> selector.SelectOptionDict:
        """Return a SelectOptionDict."""
        return selector.SelectOptionDict(
            value=self.unique_id, label=self.manufacturer + " " + self.model
        )


_supported_enocean_device_types: dict[str, EnOceanSupportedDeviceType] = {
    # A5-02 Temperature Sensors
    "A5-02-01": EnOceanSupportedDeviceType(
        unique_id="A5-02-01",
        eep="A5-02-01",
        model="EEP A5-02-01 (Temperature Sensor Range -40 °C to 0 °C)",
    ),
    "A5-02-02": EnOceanSupportedDeviceType(
        unique_id="A5-02-02",
        eep="A5-02-02",
        model="EEP A5-02-02 (Temperature Sensor Range -30 °C to +10 °C)",
    ),
    "A5-02-03": EnOceanSupportedDeviceType(
        unique_id="A5-02-03",
        eep="A5-02-03",
        model="EEP A5-02-03 (Temperature Sensor Range -20 °C to +20 °C)",
    ),
    "A5-02-04": EnOceanSupportedDeviceType(
        unique_id="A5-02-04",
        eep="A5-02-04",
        model="EEP A5-02-04 (Temperature Sensor Range -10 °C to +30 °C)",
    ),
    "A5-02-05": EnOceanSupportedDeviceType(
        unique_id="A5-02-05",
        eep="A5-02-05",
        model="EEP A5-02-05 (Temperature Sensor Range 0 °C to +40 °C)",
    ),
    "A5-02-06": EnOceanSupportedDeviceType(
        unique_id="A5-02-06",
        eep="A5-02-06",
        model="EEP A5-02-06 (Temperature Sensor Range +10 °C to +50 °C)",
    ),
    "A5-02-07": EnOceanSupportedDeviceType(
        unique_id="A5-02-07",
        eep="A5-02-07",
        model="EEP A5-02-07 (Temperature Sensor Range +20 °C to +60 °C)",
    ),
    "A5-02-08": EnOceanSupportedDeviceType(
        unique_id="A5-02-08",
        eep="A5-02-08",
        model="EEP A5-02-08 (Temperature Sensor Range +30 °C to +70 °C)",
    ),
    "A5-02-09": EnOceanSupportedDeviceType(
        unique_id="A5-02-09",
        eep="A5-02-09",
        model="EEP A5-02-09 (Temperature Sensor Range +40 °C to +80 °C)",
    ),
    "A5-02-0A": EnOceanSupportedDeviceType(
        unique_id="A5-02-0A",
        eep="A5-02-0A",
        model="EEP A5-02-0A (Temperature Sensor Range +50 °C to +90 °C)",
    ),
    "A5-02-0B": EnOceanSupportedDeviceType(
        unique_id="A5-02-0B",
        eep="A5-02-0B",
        model="EEP A5-02-0B (Temperature Sensor Range +60 °C to +100 °C)",
    ),
    "A5-02-10": EnOceanSupportedDeviceType(
        unique_id="A5-02-10",
        eep="A5-02-10",
        model="EEP A5-02-10 (Temperature Sensor Range -60 °C to +20 °C)",
    ),
    "A5-02-11": EnOceanSupportedDeviceType(
        unique_id="A5-02-11",
        eep="A5-02-11",
        model="EEP A5-02-11 (Temperature Sensor Range -50 °C to +30 °C)",
    ),
    "A5-02-12": EnOceanSupportedDeviceType(
        unique_id="A5-02-12",
        eep="A5-02-12",
        model="EEP A5-02-12 (Temperature Sensor Range -40 °C to +40 °C)",
    ),
    "A5-02-13": EnOceanSupportedDeviceType(
        unique_id="A5-02-13",
        eep="A5-02-13",
        model="EEP A5-02-13 (Temperature Sensor Range -30 °C to +50 °C)",
    ),
    "A5-02-14": EnOceanSupportedDeviceType(
        unique_id="A5-02-14",
        eep="A5-02-14",
        model="EEP A5-02-14 (Temperature Sensor Range -20 °C to +60 °C)",
    ),
    "A5-02-15": EnOceanSupportedDeviceType(
        unique_id="A5-02-15",
        eep="A5-02-15",
        model="EEP A5-02-15 (Temperature Sensor Range -10 °C to +70 °C)",
    ),
    "A5-02-16": EnOceanSupportedDeviceType(
        unique_id="A5-02-16",
        eep="A5-02-16",
        model="EEP A5-02-16 (Temperature Sensor Range 0 °C to +80 °C)",
    ),
    "A5-02-17": EnOceanSupportedDeviceType(
        unique_id="A5-02-17",
        eep="A5-02-17",
        model="EEP A5-02-17 (Temperature Sensor Range +10 °C to +90 °C)",
    ),
    "A5-02-18": EnOceanSupportedDeviceType(
        unique_id="A5-02-18",
        eep="A5-02-18",
        model="EEP A5-02-18 (Temperature Sensor Range +20 °C to +100 °C)",
    ),
    "A5-02-19": EnOceanSupportedDeviceType(
        unique_id="A5-02-19",
        eep="A5-02-19",
        model="EEP A5-02-19 (Temperature Sensor Range +30 °C to +110 °C)",
    ),
    "A5-02-1A": EnOceanSupportedDeviceType(
        unique_id="A5-02-1A",
        eep="A5-02-1A",
        model="EEP A5-02-1A (Temperature Sensor Range +40 °C to +120 °C)",
    ),
    "A5-02-1B": EnOceanSupportedDeviceType(
        unique_id="A5-02-1B",
        eep="A5-02-1B",
        model="EEP A5-02-1B (Temperature Sensor Range +50 °C to +130 °C)",
    ),
    # A5-04 Temperature and Humidity sensors (only types 1 and 2)
    "A5-04-01": EnOceanSupportedDeviceType(
        unique_id="A5-04-01",
        eep="A5-04-01",
        model="EEP A5-04-01 (Temperature and Humidity Sensor, Range 0 °C to +40 °C and 0% to 100%)",
    ),
    "A5-04-02": EnOceanSupportedDeviceType(
        unique_id="A5-04-02",
        eep="A5-04-02",
        model="EEP A5-04-02 (Temperature and Humidity Sensor, Range -20 °C to +60 °C and 0% to 100%)",
    ),
    # A5-10 Room Operating Panels
    "A5-10-01": EnOceanSupportedDeviceType(
        unique_id="A5-10-01",
        eep="A5-10-01",
        model="EEP A5-10-01 Room Operating Panel (Temperature Sensor, Set Point, Fan Speed and Occupancy Control)",
    ),
    "A5-10-02": EnOceanSupportedDeviceType(
        unique_id="A5-10-02",
        eep="A5-10-02",
        model="EEP A5-10-02 Room Operating Panel (Temperature Sensor, Set Point Control)",
    ),
    "A5-10-03": EnOceanSupportedDeviceType(
        unique_id="A5-10-03",
        eep="A5-10-03",
        model="EEP A5-10-03 Room Operating Panel (Temperature Sensor, Set Point Control)",
    ),
    "A5-10-04": EnOceanSupportedDeviceType(
        unique_id="A5-10-04",
        eep="A5-10-04",
        model="EEP A5-10-04 Room Operating Panel (Temperature Sensor, Set Point and Fan Speed Control)",
    ),
    "A5-10-05": EnOceanSupportedDeviceType(
        unique_id="A5-10-05",
        eep="A5-10-05",
        model="EEP A5-10-05 Room Operating Panel (Temperature Sensor, Set Point and Occupancy Control)",
    ),
    "A5-10-06": EnOceanSupportedDeviceType(
        unique_id="A5-10-06",
        eep="A5-10-06",
        model="EEP A5-10-06 Room Operating Panel (Temperature Sensor, Set Point and Day/Night Control)",
    ),
    "A5-10-07": EnOceanSupportedDeviceType(
        unique_id="A5-10-07",
        eep="A5-10-07",
        model="EEP A5-10-07 Room Operating Panel (Temperature Sensor, Fan Speed Control)",
    ),
    "A5-10-08": EnOceanSupportedDeviceType(
        unique_id="A5-10-08",
        eep="A5-10-08",
        model="EEP A5-10-08 Room Operating Panel (Temperature Sensor, Fan Speed and Occupancy Control)",
    ),
    "A5-10-09": EnOceanSupportedDeviceType(
        unique_id="A5-10-09",
        eep="A5-10-09",
        model="EEP A5-10-09 Room Operating Panel (Temperature Sensor, Fan Speed and Day/Night Control)",
    ),
    "A5-10-0A": EnOceanSupportedDeviceType(
        unique_id="A5-10-0A",
        eep="A5-10-0A",
        model="EEP A5-10-0A Room Operating Panel (Temperature Sensor, Set Point Adjust and Single Input Contact)",
    ),
    "A5-10-0B": EnOceanSupportedDeviceType(
        unique_id="A5-10-0B",
        eep="A5-10-0B",
        model="EEP A5-10-0B Room Operating Panel (Temperature Sensor and Single Input Contact)",
    ),
    "A5-10-0C": EnOceanSupportedDeviceType(
        unique_id="A5-10-0C",
        eep="A5-10-0C",
        model="EEP A5-10-0C Room Operating Panel (Temperature Sensor and Occupancy Control)",
    ),
    "A5-10-0D": EnOceanSupportedDeviceType(
        unique_id="A5-10-0D",
        eep="A5-10-0D",
        model="EEP A5-10-0D Room Operating Panel (Temperature Sensor and Day/Night Control)",
    ),
    "A5-10-10": EnOceanSupportedDeviceType(
        unique_id="A5-10-10",
        eep="A5-10-10",
        model="EEP A5-10-10 Room Operating Panel (Temperature and Humidity Sensor, Set Point and Occupancy Control)",
    ),
    "A5-10-11": EnOceanSupportedDeviceType(
        unique_id="A5-10-11",
        eep="A5-10-11",
        model="EEP A5-10-11 Room Operating Panel (Temperature and Humidity Sensor, Set Point and Day/Night Control)",
    ),
    "A5-10-12": EnOceanSupportedDeviceType(
        unique_id="A5-10-12",
        eep="A5-10-12",
        model="EEP A5-10-12 Room Operating Panel (Temperature and Humidity Sensor and Set Point)",
    ),
    "A5-10-13": EnOceanSupportedDeviceType(
        unique_id="A5-10-13",
        eep="A5-10-13",
        model="EEP A5-10-13 Room Operating Panel (Temperature and Humidity Sensor, Occupancy Control)",
    ),
    "A5-10-14": EnOceanSupportedDeviceType(
        unique_id="A5-10-14",
        eep="A5-10-14",
        model="EEP A5-10-14 Room Operating Panel (Temperature and Humidity Sensor, Day/Night Control)",
    ),
    # A5-12 Automated Meter Reading
    "A5-12-01": EnOceanSupportedDeviceType(
        unique_id="A5-12-01",
        eep="A5-12-01",
        model="EEP A5-12-01 (Automated Meter Reading [AMR] - Electricity)",
    ),
    # A5-20 HVAC Components - Battery Powered Actuator (BI-DIR)
    "A5-20-01": EnOceanSupportedDeviceType(
        unique_id="A5-20-01",
        eep="A5-20-01",
        model="EEP A5-20-01 (HVAC Components - Battery Powered Actuator (BI-DIR))",
    ),
    # D2-01 Electronic Switches and Dimmers with Energy Measurement and Local Control
    "D2-01-00": EnOceanSupportedDeviceType(
        unique_id="D2-01-00",
        eep="D2-01-00",
        model="EEP D2-01-00 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 00)",
    ),
    "D2-01-01": EnOceanSupportedDeviceType(
        unique_id="D2-01-01",
        eep="D2-01-01",
        model="EEP D2-01-01 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 01)",
    ),
    "D2-01-03": EnOceanSupportedDeviceType(
        unique_id="D2-01-03",
        eep="D2-01-03",
        model="EEP D2-01-03 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 03)",
    ),
    "D2-01-04": EnOceanSupportedDeviceType(
        unique_id="D2-01-04",
        eep="D2-01-04",
        model="EEP D2-01-04 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 04)",
    ),
    "D2-01-05": EnOceanSupportedDeviceType(
        unique_id="D2-01-05",
        eep="D2-01-05",
        model="EEP D2-01-05 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 05)",
    ),
    "D2-01-06": EnOceanSupportedDeviceType(
        unique_id="D2-01-06",
        eep="D2-01-06",
        model="EEP D2-01-06 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 06)",
    ),
    "D2-01-07": EnOceanSupportedDeviceType(
        unique_id="D2-01-07",
        eep="D2-01-07",
        model="EEP D2-01-07 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 07)",
    ),
    "D2-01-08": EnOceanSupportedDeviceType(
        unique_id="D2-01-08",
        eep="D2-01-08",
        model="EEP D2-01-08 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 08)",
    ),
    "D2-01-09": EnOceanSupportedDeviceType(
        unique_id="D2-01-09",
        eep="D2-01-09",
        model="EEP D2-01-09 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 09)",
    ),
    "D2-01-0A": EnOceanSupportedDeviceType(
        unique_id="D2-01-0A",
        eep="D2-01-0A",
        model="EEP D2-01-0A (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0A)",
    ),
    "D2-01-0B": EnOceanSupportedDeviceType(
        unique_id="D2-01-0B",
        eep="D2-01-0B",
        model="EEP D2-01-0B (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0B)",
    ),
    "D2-01-0C": EnOceanSupportedDeviceType(
        unique_id="D2-01-0C",
        eep="D2-01-0C",
        model="EEP D2-01-0C (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0C)",
    ),
    "D2-01-0D": EnOceanSupportedDeviceType(
        unique_id="D2-01-0D",
        eep="D2-01-0D",
        model="EEP D2-01-0D (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0D)",
    ),
    "D2-01-0E": EnOceanSupportedDeviceType(
        unique_id="D2-01-0E",
        eep="D2-01-0E",
        model="EEP D2-01-0E (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0E)",
    ),
    "D2-01-0F": EnOceanSupportedDeviceType(
        unique_id="D2-01-0F",
        eep="D2-01-0F",
        model="EEP D2-01-0F (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0F)",
    ),
    "D2-01-10": EnOceanSupportedDeviceType(
        unique_id="D2-01-10",
        eep="D2-01-10",
        model="EEP D2-01-10 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 10)",
    ),
    "D2-01-11": EnOceanSupportedDeviceType(
        unique_id="D2-01-11",
        eep="D2-01-11",
        model="EEP D2-01-11 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 11)",
    ),
    "D2-01-12": EnOceanSupportedDeviceType(
        unique_id="D2-01-12",
        eep="D2-01-12",
        model="EEP D2-01-12 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 12)",
    ),
    "D2-01-13": EnOceanSupportedDeviceType(
        unique_id="D2-01-13",
        eep="D2-01-13",
        model="EEP D2-01-13 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 13)",
    ),
    "D2-01-14": EnOceanSupportedDeviceType(
        unique_id="D2-01-14",
        eep="D2-01-14",
        model="EEP D2-01-14 (Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 14)",
    ),
    # D2-05-00 Blinds Control for Position and Angle
    "D2-05-00": EnOceanSupportedDeviceType(
        unique_id="D2-05-00",
        eep="D2-05-00",
        model="EEP D2-05-00 (Blinds Control for Position and Angle, Type 00)",
    ),
    # F6-02 Light and Blind Control
    "F6-02-01": EnOceanSupportedDeviceType(
        unique_id="F6-02-01",
        eep="F6-02-01",
        model="EEP F6-02-01 (Light and Blind Control - Application Style 2)",
    ),
    "F6-02-02": EnOceanSupportedDeviceType(
        unique_id="F6-02-02",
        eep="F6-02-02",
        model="EEP F6-02-02 (Light and Blind Control - Application Style 1)",
    ),
    # F6-10-00 Window Handle
    "F6-10-00": EnOceanSupportedDeviceType(
        unique_id="F6-10-00",
        eep="F6-10-00",
        model="EEP F6-10-00 (Mechanical Handle - Window Handle)",
    ),
    # Other Devices
    "Eltako_FUD61NPN": EnOceanSupportedDeviceType(
        unique_id="Eltako_FUD61NPN",
        eep="A5-38-08",
        manufacturer="Eltako",
        model="FUD61NPN",
    ),
    "Eltako_FT55": EnOceanSupportedDeviceType(
        unique_id="Eltako_FT55",
        eep="F6-02-01",
        manufacturer="Eltako",
        model="FT55 battery-less wall switch",
    ),
    "Jung_ENO": EnOceanSupportedDeviceType(
        unique_id="Jung_ENO", eep="F6-02-01", manufacturer="Jung", model="ENO Series"
    ),
    "Omnio_WS-CH-102": EnOceanSupportedDeviceType(
        unique_id="Omnio_WS-CH-102",
        eep="F6-02-01",
        manufacturer="Omnio",
        model="WS-CH-102",
    ),
    "Hoppe_SecuSignal": EnOceanSupportedDeviceType(
        unique_id="Hoppe_SecuSignal",
        eep="F6-10-00",
        manufacturer="Hoppe",
        model="SecuSignal window handle from Somfy",
    ),
    "TRIO2SYS_WallSwitches": EnOceanSupportedDeviceType(
        unique_id="TRIO2SYS_WallSwitches",
        eep="F6-02-01",
        manufacturer="TRIO2SYS",
        model="TRIO2SYS Wall switches",
    ),
    "NodOn_SIN-2-1-01": EnOceanSupportedDeviceType(
        unique_id="NodOn_SIN-2-1-01",
        eep="D2-01-0F",
        manufacturer="NodOn",
        model="SIN-2-1-01",
    ),
    "NodOn_SIN-2-2-01": EnOceanSupportedDeviceType(
        unique_id="NodOn_SIN-2-2-01",
        eep="D2-01-12",
        manufacturer="NodOn",
        model="SIN-2-2-01",
    ),
    "NodOn_SIN-2-RS-01": EnOceanSupportedDeviceType(
        unique_id="NodOn_SIN-2-RS-01",
        eep="D2-05-00",
        manufacturer="NodOn",
        model="SIN-2-RS-01 (roller shutter controller, EEP D2-05-00)",
    ),
    "Permundo_PSC234": EnOceanSupportedDeviceType(
        unique_id="Permundo_PSC234",
        eep="D2-01-09",
        manufacturer="Permundo",
        model="PSC234 (switch and power monitor)",
    ),
}


def get_supported_enocean_device_types() -> dict[str, EnOceanSupportedDeviceType]:
    """Get a dictionary mapping from EnOcean device type id to EnOceanSupportedDeviceType."""
    return _supported_enocean_device_types
