"""Definition and setup of the Omnilogic Sensors for Home Assistant."""

import logging

from homeassistant.const import PERCENTAGE, TEMP_CELSIUS, TEMP_FAHRENHEIT

from .const import COORDINATOR, DOMAIN
from .omnilogic_common import OmniLogicEntity, OmniLogicUpdateCoordinator

TEMP_UNITS = [TEMP_CELSIUS, TEMP_FAHRENHEIT]
PERCENT_UNITS = [PERCENTAGE, PERCENTAGE]
SALT_UNITS = ["g/L", "ppm"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""

    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    sensors = []

    for backyard in coordinator.data:
        sensors.append(
            OmnilogicSensor(
                coordinator,
                "air_temperature",
                "Air Temperature",
                backyard,
                {},
                "temperature",
                "mdi:thermometer",
                TEMP_UNITS,
                backyard.get("airTemp"),
            )
        )

        sensors.append(
            OmnilogicSensor(
                coordinator,
                "alarm",
                "Alarm",
                backyard,
                {},
                "none",
                "mdi:alert-circle",
                "",
                backyard,
            )
        )

        for bow in backyard["BOWS"]:
            sensors.append(
                OmnilogicSensor(
                    coordinator,
                    "water_temperature",
                    "Water Temperature",
                    backyard,
                    bow,
                    "temperature",
                    "mdi:thermometer",
                    TEMP_UNITS,
                    bow.get("waterTemp"),
                )
            )

            if "Filter" in bow.keys():
                sensors.append(
                    OmnilogicSensor(
                        coordinator,
                        "filter_pump_speed",
                        "Pump Speed",
                        backyard,
                        bow,
                        "none",
                        "mdi:speedometer",
                        PERCENT_UNITS,
                        bow["Filter"],
                    )
                )

            for pump in bow["Pumps"]:
                sensors.append(
                    OmnilogicSensor(
                        coordinator,
                        "pump_speed",
                        "Pump Speed",
                        backyard,
                        bow,
                        "none",
                        "mdi:speedometer",
                        PERCENT_UNITS,
                        pump,
                    )
                )

            if "Chlorinator" in bow.keys():
                sensors.append(
                    OmnilogicSensor(
                        coordinator,
                        "chlorinator",
                        "Chlorinator",
                        backyard,
                        bow,
                        "none",
                        "mdi:gauge",
                        PERCENT_UNITS,
                        bow["Chlorinator"],
                    )
                )
                sensors.append(
                    OmnilogicSensor(
                        coordinator,
                        "salt_level",
                        "Salt Level",
                        backyard,
                        bow,
                        "none",
                        "mdi:gauge",
                        PERCENT_UNITS,
                        bow["Chlorinator"],
                    )
                )

            if "CSAD" in bow.keys():
                if bow["CSAD"]["systemId"] != "0":
                    sensors.append(
                        OmnilogicSensor(
                            coordinator,
                            "csad_ph",
                            "CSAD",
                            backyard,
                            bow,
                            "none",
                            "mdi:gauge",
                            PERCENT_UNITS,
                            bow["CSAD"],
                        )
                    )

                    sensors.append(
                        OmnilogicSensor(
                            coordinator,
                            "csad_orp",
                            "CSAD",
                            backyard,
                            bow,
                            "none",
                            "mdi:gauge",
                            PERCENT_UNITS,
                            bow["CSAD"],
                        )
                    )

    async_add_entities(sensors, update_before_add=True)


class OmnilogicSensor(OmniLogicEntity):
    """Defines an Omnilogic sensor entity."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        kind: str,
        name: str,
        backyard: dict,
        bow: dict,
        device_class: str,
        icon: str,
        unit: str,
        sensordata: dict,
    ):
        """Initialize Entities."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            backyard=backyard,
            bow=bow,
            icon=icon,
            entitydata=sensordata,
        )
        self._state = None
        self._unit_type = backyard["Unit-of-Measurement"]
        self._device_class = device_class
        self._unit = None

    @property
    def device_class(self):
        """Return the device class of the entity."""
        if self._device_class != "none":
            return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the right unit of measure."""
        return self._unit

    @property
    def force_update(self):
        """Force update."""
        return True

    @property
    def state(self):
        """Return the state."""

        _LOGGER.debug("Updating state of sensor: %s", self._name)
        if self._kind == "water_temperature":
            sensordata = None

            for backyard in self.coordinator.data:
                for bow in backyard["BOWS"]:
                    if bow["systemId"] == self.bow["systemId"]:
                        sensordata = bow["waterTemp"]
                        break

            temp_return = int(sensordata)
            temp_state = int(sensordata)
            unit_of_measurement = TEMP_FAHRENHEIT
            if self._backyard["Unit-of-Measurement"] == "Metric":
                temp_return = round((temp_return - 32) * 5 / 9, 1)
                unit_of_measurement = TEMP_CELSIUS

            if int(sensordata) == -1:
                temp_return = None
                temp_state = None

            self._attrs["hayward_temperature"] = temp_return
            self._attrs["hayward_unit_of_measure"] = unit_of_measurement
            self._state = temp_state
            self._unit = TEMP_FAHRENHEIT
            self._attrs["systemId"] = self.bow.get("systemId")
            self._name = (
                self._backyard["BackyardName"]
                + " "
                + self.bow.get("Name")
                + " Water Temperature"
            )

        elif self._kind == "filter_pump_speed":
            sensordata = {}

            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    if bow["Filter"]["systemId"] == self.entitydata.get("systemId"):
                        sensordata = bow["Filter"]
                        break

            self._state = sensordata.get("filterSpeed")
            self._unit = "%"
            self._name = (
                self._backyard["BackyardName"]
                + " "
                + self.bow.get("Name")
                + " "
                + self.entitydata.get("Name")
            )
            self._attrs["systemId"] = self.entitydata.get("systemId")
            self._attrs["MspSystemId"] = self._backyard["systemId"]
            self._attrs["PumpType"] = self.entitydata.get("Filter-Type")

            self.alarms = sensordata.get("Alarms")

            self._attrs["Alarm"] = ""
            if len(self.alarms) != 0:
                self._attrs["Alarm"] = (
                    self.alarms[0]["Message"] + " (" + self.alarms[0]["Comment"] + ")"
                )

        elif self._kind == "pump_speed":
            sensordata = {}

            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    for pump in bow.get("Pumps"):
                        if pump["systemId"] == self.entitydata["systemId"]:
                            sensordata = pump
                            break

            if self.entitydata.get("Type") == "PMP_SINGLE_SPEED":
                if sensordata.get("pumpSpeed") == "100":
                    self._state = "on"
                else:
                    self._state = "off"
            else:
                self._state = sensordata.get("pumpSpeed")
                self._unit = "%"

            self._name = (
                self._backyard["BackyardName"]
                + " "
                + self.bow.get("Name")
                + " "
                + self.entitydata.get("Name")
            )
            self._attrs["systemId"] = self.entitydata.get("systemId")
            self._attrs["MspSystemId"] = self._backyard["systemId"]
            self._attrs["PumpType"] = self.entitydata.get("Type")

            self.alarms = sensordata.get("Alarms")

            self._attrs["Alarm"] = ""
            if len(self.alarms) != 0:
                alarm_message = self.alarms[0].get("Message")
                if self.alarms[0].get("Comment") is not None:
                    alarm_message = alarm_message + (
                        " (" + self.alarms[0].get("Comment") + ")"
                    )

        elif self._kind == "salt_level":
            sensordata = {}

            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    if bow["Chlorinator"]["systemId"] == self.entitydata["systemId"]:
                        sensordata = bow.get("Chlorinator")
                        break

            salt_return = int(sensordata.get("avgSaltLevel"))
            unit_of_measurement = "ppm"

            if self._backyard["Unit-of-Measurement"] == "Metric":
                salt_return = round(salt_return / 1000, 2)
                unit_of_measurement = "g/L"

            self._state = salt_return
            self._unit = unit_of_measurement
            self._attrs["SystemId"] = self.entitydata.get("systemId")
            self._name = (
                self._backyard["BackyardName"]
                + " "
                + self.bow.get("Name")
                + " "
                + self.entitydata.get("Name")
                + " Salt Level"
            )

            self.alarms = sensordata.get("Alarms")

            self._attrs["Alarm"] = ""
            if len(self.alarms) > 0:
                self._attrs["Alarm"] = (
                    self.alarms[0]["Message"] + " (" + self.alarms[0]["Comment"] + ")"
                )

        elif self._kind == "chlorinator":
            sensordata = {}

            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    if bow["Chlorinator"]["systemId"] == self.entitydata["systemId"]:
                        sensordata = bow.get("Chlorinator")
                        break

            if sensordata.get("operatingMode") == "1":
                self._state = sensordata.get("Timed-Percent")
                self._unit = "%"
            elif sensordata.get("operatingMode") == "2":
                if sensordata.get("Timed-Percent") == "100":
                    self._state = "on"
                else:
                    self._state = "off"

            self._name = (
                self._backyard["BackyardName"]
                + " "
                + self.bow.get("Name")
                + " "
                + self.entitydata.get("Name")
                + " Setting"
            )

            self.alarms = sensordata.get("Alarms")

            self._attrs["Alarm"] = ""
            if len(self.alarms) != 0:
                self._attrs["Alarm"] = (
                    self.alarms[0]["Message"] + " (" + self.alarms[0]["Comment"] + ")"
                )

        elif self._kind == "csad_ph":
            sensordata = {}

            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    if bow["CSAD"]["systemId"] == self.entitydata["systemId"]:
                        sensordata = bow.get("CSAD")
                        break

            phstate = None
            if sensordata.get("ph") != 0:
                phstate = sensordata.get("ph")

            self._state = phstate
            self._unit = "pH"
            self._name = (
                self._backyard["BackyardName"] + " " + self.bow.get("Name") + " pH"
            )

            self.alarms = sensordata.get("Alarms")

            self._attrs["Alarm"] = ""
            if len(self.alarms) != 0:
                self._attrs["Alarm"] = (
                    self.alarms[0]["Message"] + " (" + self.alarms[0]["Comment"] + ")"
                )

        elif self._kind == "csad_orp":
            sensordata = {}

            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    if bow["CSAD"]["systemId"] == self.entitydata["systemId"]:
                        sensordata = bow.get("CSAD")
                        break

            orpstate = None
            if sensordata.get("orp") != -1:
                orpstate = sensordata.get("orp")

            self._state = orpstate
            self._unit = "mV"
            self._name = (
                self._backyard["BackyardName"] + " " + self.bow.get("Name") + " ORP"
            )

            self.alarms = sensordata.get("Alarms")

            self._attrs["Alarm"] = ""
            if len(self.alarms) != 0:
                self._attrs["Alarm"] = (
                    self.alarms[0]["Message"] + " (" + self.alarms[0]["Comment"] + ")"
                )

        elif self._kind == "air_temperature":
            sensordata = 0

            for backyard in self.coordinator.data:
                if backyard.get("systemId") == self._attrs["MspSystemId"]:
                    sensordata = backyard.get("airTemp")

            temp_return = int(sensordata)
            unit_of_measurement = TEMP_FAHRENHEIT
            if self._backyard["Unit-of-Measurement"] == "Metric":
                temp_return = round((temp_return - 32) * 5 / 9, 1)
                unit_of_measurement = TEMP_CELSIUS

            self._attrs["hayward_temperature"] = temp_return
            self._attrs["hayward_unit_of_measure"] = unit_of_measurement
            self._state = float(sensordata)
            self._unit = TEMP_FAHRENHEIT
            self._name = self._backyard.get("BackyardName") + " Air Temperature"
            self._attrs["MspSystemId"] = self._backyard["systemId"]

        elif self._kind == "alarm":
            sensordata = []

            self._name = self._backyard.get("BackyardName") + " Alarms"

            for backyard in self.coordinator.data:
                if backyard.get("systemId") == self._attrs["MspSystemId"]:
                    sensordata = backyard

            alarms_list = sensordata["Alarms"]

            if len(alarms_list) > 0:
                self._state = "on"
                alarm_message = alarms_list[0].get("Message")
                if alarms_list[0].get("Comment") is not None:
                    alarm_message = alarm_message + (
                        " (" + alarms_list[0].get("Comment") + ")"
                    )
                self._attrs["Alarm"] = alarm_message
            else:
                self._state = "off"
        return self._state
