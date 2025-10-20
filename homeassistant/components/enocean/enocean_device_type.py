"""Module containing a representation of a supported EnOcean device type."""

from homeassistant.helpers import selector


class EnOceanDeviceType:
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
        label = ""
        if self.unique_id == self.eep:
            label = "EEP " + self.eep + " (" + self.model + ")"
        else:
            label = self.manufacturer + " " + self.model + " (EEP " + self.eep + ")"

        return selector.SelectOptionDict(value=self.unique_id, label=label)

    @classmethod
    def getSupportedDeviceTypes(cls) -> dict[str, "EnOceanDeviceType"]:
        """Get a dictionary mapping from EnOcean device type id to EnOceanSupportedDeviceType."""
        return {
            # A5-02 Temperature Sensors
            "A5-02-01": EnOceanDeviceType(
                unique_id="A5-02-01",
                eep="A5-02-01",
                model="Temperature Sensor Range -40 °C to 0 °C",
            ),
            "A5-02-02": EnOceanDeviceType(
                unique_id="A5-02-02",
                eep="A5-02-02",
                model="Temperature Sensor Range -30 °C to +10 °C",
            ),
            "A5-02-03": EnOceanDeviceType(
                unique_id="A5-02-03",
                eep="A5-02-03",
                model="Temperature Sensor Range -20 °C to +20 °C",
            ),
            "A5-02-04": EnOceanDeviceType(
                unique_id="A5-02-04",
                eep="A5-02-04",
                model="Temperature Sensor Range -10 °C to +30 °C",
            ),
            "A5-02-05": EnOceanDeviceType(
                unique_id="A5-02-05",
                eep="A5-02-05",
                model="Temperature Sensor Range 0 °C to +40 °C",
            ),
            "A5-02-06": EnOceanDeviceType(
                unique_id="A5-02-06",
                eep="A5-02-06",
                model="Temperature Sensor Range +10 °C to +50 °C",
            ),
            "A5-02-07": EnOceanDeviceType(
                unique_id="A5-02-07",
                eep="A5-02-07",
                model="Temperature Sensor Range +20 °C to +60 °C",
            ),
            "A5-02-08": EnOceanDeviceType(
                unique_id="A5-02-08",
                eep="A5-02-08",
                model="Temperature Sensor Range +30 °C to +70 °C",
            ),
            "A5-02-09": EnOceanDeviceType(
                unique_id="A5-02-09",
                eep="A5-02-09",
                model="Temperature Sensor Range +40 °C to +80 °C",
            ),
            "A5-02-0A": EnOceanDeviceType(
                unique_id="A5-02-0A",
                eep="A5-02-0A",
                model="Temperature Sensor Range +50 °C to +90 °C",
            ),
            "A5-02-0B": EnOceanDeviceType(
                unique_id="A5-02-0B",
                eep="A5-02-0B",
                model="Temperature Sensor Range +60 °C to +100 °C",
            ),
            "A5-02-10": EnOceanDeviceType(
                unique_id="A5-02-10",
                eep="A5-02-10",
                model="Temperature Sensor Range -60 °C to +20 °C",
            ),
            "A5-02-11": EnOceanDeviceType(
                unique_id="A5-02-11",
                eep="A5-02-11",
                model="Temperature Sensor Range -50 °C to +30 °C",
            ),
            "A5-02-12": EnOceanDeviceType(
                unique_id="A5-02-12",
                eep="A5-02-12",
                model="Temperature Sensor Range -40 °C to +40 °C",
            ),
            "A5-02-13": EnOceanDeviceType(
                unique_id="A5-02-13",
                eep="A5-02-13",
                model="Temperature Sensor Range -30 °C to +50 °C",
            ),
            "A5-02-14": EnOceanDeviceType(
                unique_id="A5-02-14",
                eep="A5-02-14",
                model="Temperature Sensor Range -20 °C to +60 °C",
            ),
            "A5-02-15": EnOceanDeviceType(
                unique_id="A5-02-15",
                eep="A5-02-15",
                model="Temperature Sensor Range -10 °C to +70 °C",
            ),
            "A5-02-16": EnOceanDeviceType(
                unique_id="A5-02-16",
                eep="A5-02-16",
                model="Temperature Sensor Range 0 °C to +80 °C",
            ),
            "A5-02-17": EnOceanDeviceType(
                unique_id="A5-02-17",
                eep="A5-02-17",
                model="Temperature Sensor Range +10 °C to +90 °C",
            ),
            "A5-02-18": EnOceanDeviceType(
                unique_id="A5-02-18",
                eep="A5-02-18",
                model="Temperature Sensor Range +20 °C to +100 °C",
            ),
            "A5-02-19": EnOceanDeviceType(
                unique_id="A5-02-19",
                eep="A5-02-19",
                model="Temperature Sensor Range +30 °C to +110 °C",
            ),
            "A5-02-1A": EnOceanDeviceType(
                unique_id="A5-02-1A",
                eep="A5-02-1A",
                model="Temperature Sensor Range +40 °C to +120 °C",
            ),
            "A5-02-1B": EnOceanDeviceType(
                unique_id="A5-02-1B",
                eep="A5-02-1B",
                model="Temperature Sensor Range +50 °C to +130 °C",
            ),
            # A5-04 Temperature and Humidity sensors (only types 1 and 2)
            "A5-04-01": EnOceanDeviceType(
                unique_id="A5-04-01",
                eep="A5-04-01",
                model="Temperature and Humidity Sensor, Range 0 °C to +40 °C and 0% to 100%",
            ),
            "A5-04-02": EnOceanDeviceType(
                unique_id="A5-04-02",
                eep="A5-04-02",
                model="Temperature and Humidity Sensor, Range -20 °C to +60 °C and 0% to 100%",
            ),
            # A5-10 Room Operating Panels
            "A5-10-01": EnOceanDeviceType(
                unique_id="A5-10-01",
                eep="A5-10-01",
                model="Room Operating Panel Temperature Sensor, Set Point, Fan Speed and Occupancy Control",
            ),
            "A5-10-02": EnOceanDeviceType(
                unique_id="A5-10-02",
                eep="A5-10-02",
                model="Room Operating Panel Temperature Sensor, Set Point Control",
            ),
            "A5-10-03": EnOceanDeviceType(
                unique_id="A5-10-03",
                eep="A5-10-03",
                model="Room Operating Panel Temperature Sensor, Set Point Control",
            ),
            "A5-10-04": EnOceanDeviceType(
                unique_id="A5-10-04",
                eep="A5-10-04",
                model="Room Operating Panel Temperature Sensor, Set Point and Fan Speed Control",
            ),
            "A5-10-05": EnOceanDeviceType(
                unique_id="A5-10-05",
                eep="A5-10-05",
                model="Room Operating Panel Temperature Sensor, Set Point and Occupancy Control",
            ),
            "A5-10-06": EnOceanDeviceType(
                unique_id="A5-10-06",
                eep="A5-10-06",
                model="Room Operating Panel Temperature Sensor, Set Point and Day/Night Control",
            ),
            "A5-10-07": EnOceanDeviceType(
                unique_id="A5-10-07",
                eep="A5-10-07",
                model="Room Operating Panel Temperature Sensor, Fan Speed Control",
            ),
            "A5-10-08": EnOceanDeviceType(
                unique_id="A5-10-08",
                eep="A5-10-08",
                model="Room Operating Panel Temperature Sensor, Fan Speed and Occupancy Control",
            ),
            "A5-10-09": EnOceanDeviceType(
                unique_id="A5-10-09",
                eep="A5-10-09",
                model="Room Operating Panel Temperature Sensor, Fan Speed and Day/Night Control",
            ),
            "A5-10-0A": EnOceanDeviceType(
                unique_id="A5-10-0A",
                eep="A5-10-0A",
                model="Room Operating Panel Temperature Sensor, Set Point Adjust and Single Input Contact",
            ),
            "A5-10-0B": EnOceanDeviceType(
                unique_id="A5-10-0B",
                eep="A5-10-0B",
                model="Room Operating Panel Temperature Sensor and Single Input Contact",
            ),
            "A5-10-0C": EnOceanDeviceType(
                unique_id="A5-10-0C",
                eep="A5-10-0C",
                model="Room Operating Panel Temperature Sensor and Occupancy Control",
            ),
            "A5-10-0D": EnOceanDeviceType(
                unique_id="A5-10-0D",
                eep="A5-10-0D",
                model="Room Operating Panel Temperature Sensor and Day/Night Control",
            ),
            "A5-10-10": EnOceanDeviceType(
                unique_id="A5-10-10",
                eep="A5-10-10",
                model="Room Operating Panel Temperature and Humidity Sensor, Set Point and Occupancy Control",
            ),
            "A5-10-11": EnOceanDeviceType(
                unique_id="A5-10-11",
                eep="A5-10-11",
                model="Room Operating Panel Temperature and Humidity Sensor, Set Point and Day/Night Control",
            ),
            "A5-10-12": EnOceanDeviceType(
                unique_id="A5-10-12",
                eep="A5-10-12",
                model="Room Operating Panel Temperature and Humidity Sensor and Set Point",
            ),
            "A5-10-13": EnOceanDeviceType(
                unique_id="A5-10-13",
                eep="A5-10-13",
                model="Room Operating Panel Temperature and Humidity Sensor, Occupancy Control",
            ),
            "A5-10-14": EnOceanDeviceType(
                unique_id="A5-10-14",
                eep="A5-10-14",
                model="Room Operating Panel Temperature and Humidity Sensor, Day/Night Control",
            ),
            # A5-12 Automated Meter Reading
            "A5-12-01": EnOceanDeviceType(
                unique_id="A5-12-01",
                eep="A5-12-01",
                model="Automated Meter Reading AMR - Electricity",
            ),
            # A5-20 HVAC Components - Battery Powered Actuator (BI-DIR)
            "A5-20-01": EnOceanDeviceType(
                unique_id="A5-20-01",
                eep="A5-20-01",
                model="HVAC Components - Battery Powered Actuator BI-DIR",
            ),
            # D2-01 Electronic Switches and Dimmers with Energy Measurement and Local Control
            "D2-01-00": EnOceanDeviceType(
                unique_id="D2-01-00",
                eep="D2-01-00",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 00",
            ),
            "D2-01-01": EnOceanDeviceType(
                unique_id="D2-01-01",
                eep="D2-01-01",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 01",
            ),
            "D2-01-03": EnOceanDeviceType(
                unique_id="D2-01-03",
                eep="D2-01-03",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 03",
            ),
            "D2-01-04": EnOceanDeviceType(
                unique_id="D2-01-04",
                eep="D2-01-04",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 04",
            ),
            "D2-01-05": EnOceanDeviceType(
                unique_id="D2-01-05",
                eep="D2-01-05",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 05",
            ),
            "D2-01-06": EnOceanDeviceType(
                unique_id="D2-01-06",
                eep="D2-01-06",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 06",
            ),
            "D2-01-07": EnOceanDeviceType(
                unique_id="D2-01-07",
                eep="D2-01-07",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 07",
            ),
            "D2-01-08": EnOceanDeviceType(
                unique_id="D2-01-08",
                eep="D2-01-08",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 08",
            ),
            "D2-01-09": EnOceanDeviceType(
                unique_id="D2-01-09",
                eep="D2-01-09",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 09",
            ),
            "D2-01-0A": EnOceanDeviceType(
                unique_id="D2-01-0A",
                eep="D2-01-0A",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0A",
            ),
            "D2-01-0B": EnOceanDeviceType(
                unique_id="D2-01-0B",
                eep="D2-01-0B",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0B",
            ),
            "D2-01-0C": EnOceanDeviceType(
                unique_id="D2-01-0C",
                eep="D2-01-0C",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0C",
            ),
            "D2-01-0D": EnOceanDeviceType(
                unique_id="D2-01-0D",
                eep="D2-01-0D",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0D",
            ),
            "D2-01-0E": EnOceanDeviceType(
                unique_id="D2-01-0E",
                eep="D2-01-0E",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0E",
            ),
            "D2-01-0F": EnOceanDeviceType(
                unique_id="D2-01-0F",
                eep="D2-01-0F",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 0F",
            ),
            "D2-01-10": EnOceanDeviceType(
                unique_id="D2-01-10",
                eep="D2-01-10",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 10",
            ),
            "D2-01-11": EnOceanDeviceType(
                unique_id="D2-01-11",
                eep="D2-01-11",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 11",
            ),
            "D2-01-12": EnOceanDeviceType(
                unique_id="D2-01-12",
                eep="D2-01-12",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 12",
            ),
            "D2-01-13": EnOceanDeviceType(
                unique_id="D2-01-13",
                eep="D2-01-13",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 13",
            ),
            "D2-01-14": EnOceanDeviceType(
                unique_id="D2-01-14",
                eep="D2-01-14",
                model="Electronic Switches and Dimmers with Energy Measurement and Local Control, Type 14",
            ),
            # D2-05-00 Blinds Control for Position and Angle
            "D2-05-00": EnOceanDeviceType(
                unique_id="D2-05-00",
                eep="D2-05-00",
                model="Blinds Control for Position and Angle, Type 00",
            ),
            # F6-02 Light and Blind Control
            "F6-02-01": EnOceanDeviceType(
                unique_id="F6-02-01",
                eep="F6-02-01",
                model="Light and Blind Control - Application Style 2",
            ),
            "F6-02-02": EnOceanDeviceType(
                unique_id="F6-02-02",
                eep="F6-02-02",
                model="Light and Blind Control - Application Style 1",
            ),
            # F6-10-00 Window Handle
            "F6-10-00": EnOceanDeviceType(
                unique_id="F6-10-00",
                eep="F6-10-00",
                model="Mechanical Handle - Window Handle",
            ),
            # Other Devices
            "Eltako_FUD61NPN": EnOceanDeviceType(
                unique_id="Eltako_FUD61NPN",
                eep="A5-38-08",
                manufacturer="Eltako",
                model="FUD61NPN-230V Wireless universal dimmer",
            ),
            "Eltako_FLD61": EnOceanDeviceType(
                unique_id="Eltako_FLD61",
                eep="A5-38-08",
                manufacturer="Eltako",
                model="FLD61 PWM LED dimmer switch for LEDs 12-36V DC, up to 4A",
            ),
            "Eltako_FT55": EnOceanDeviceType(
                unique_id="Eltako_FT55",
                eep="F6-02-01",
                manufacturer="Eltako",
                model="FT55 battery-less wall switch",
            ),
            "Jung_ENO": EnOceanDeviceType(
                unique_id="Jung_ENO",
                eep="F6-02-01",
                manufacturer="Jung",
                model="ENO Series",
            ),
            "Omnio_WS-CH-102": EnOceanDeviceType(
                unique_id="Omnio_WS-CH-102",
                eep="F6-02-01",
                manufacturer="Omnio",
                model="WS-CH-102",
            ),
            "Hoppe_SecuSignal": EnOceanDeviceType(
                unique_id="Hoppe_SecuSignal",
                eep="F6-10-00",
                manufacturer="Hoppe",
                model="SecuSignal window handle from Somfy",
            ),
            "TRIO2SYS_WallSwitches": EnOceanDeviceType(
                unique_id="TRIO2SYS_WallSwitches",
                eep="F6-02-01",
                manufacturer="TRIO2SYS",
                model="TRIO2SYS Wall switches",
            ),
            "NodOn_SIN-2-1-01": EnOceanDeviceType(
                unique_id="NodOn_SIN-2-1-01",
                eep="D2-01-0F",
                manufacturer="NodOn",
                model="SIN-2-1-01 Single Channel Relay Switch",
            ),
            "NodOn_SIN-2-2-01": EnOceanDeviceType(
                unique_id="NodOn_SIN-2-2-01",
                eep="D2-01-12",
                manufacturer="NodOn",
                model="SIN-2-2-01 Dual Channel Relay Switch",
            ),
            "NodOn_SIN-2-RS-01": EnOceanDeviceType(
                unique_id="NodOn_SIN-2-RS-01",
                eep="D2-05-00",
                manufacturer="NodOn",
                model="SIN-2-RS-01 Roller Shutter Controller",
            ),
            "Permundo_PSC234": EnOceanDeviceType(
                unique_id="Permundo_PSC234",
                eep="D2-01-09",
                manufacturer="Permundo",
                model="PSC234 (switch and power monitor)",
            ),
            "NodOn_PIR-2-1-01": EnOceanDeviceType(
                unique_id="NodOn_PIR-2-1-01",
                eep="A5-07-03",
                manufacturer="NodOn",
                model="PIR-2-1-01 Motion Sensor (NOT TESTED)",
            ),
        }
