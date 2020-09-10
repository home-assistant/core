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
            OmniLogicTemperatureSensor(
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
            OmniLogicAlarmSensor(
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
                OmniLogicTemperatureSensor(
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
                    OmniLogicPumpSpeedSensor(
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
                    OmniLogicPumpSpeedSensor(
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
                    OmniLogicChlorinatorSensor(
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
                    OmniLogicSaltLevelSensor(
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
                        OmniLogicPHSensor(
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
                        OmniLogicORPSensor(
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

    def add_alarms(self, alarms: dict):
        """Add Alarm attributes."""
        self.alarms = alarms

        self._attrs["Alarm"] = ""
        if len(self.alarms) != 0:
            self._attrs["Alarm"] = (
                self.alarms[0]["Message"] + " (" + self.alarms[0]["Comment"] + ")"
            )

    def find_chlorinator(self, coordinator, systemid):
        """Find the correct chlorinator entity."""

        for backyard in coordinator.data:
            for bow in backyard.get("BOWS"):
                if bow["Chlorinator"]["systemId"] == systemid:
                    sensordata = bow.get("Chlorinator")
                    break

        return sensordata

    def find_csad(self, coordinator, systemid):
        """Find the correct CSAD entity."""

        for backyard in coordinator.data:
            for bow in backyard.get("BOWS"):
                if bow["CSAD"]["systemId"] == systemid:
                    sensordata = bow.get("CSAD")
                    break

        return sensordata


class OmniLogicTemperatureSensor(OmnilogicSensor):
    """Define an OmniLogic Temperature (Air/Water) Sensor."""

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
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            backyard=backyard,
            bow=bow,
            device_class=device_class,
            icon=icon,
            unit=unit,
            sensordata=sensordata,
        )

    @property
    def state(self):
        """Return the state for the temperature sensor."""
        _LOGGER.debug("Updating state of sensor: %s", self._name)

        sensordata = None

        if self._kind == "water_temperature":
            for backyard in self.coordinator.data:
                for bow in backyard["BOWS"]:
                    if bow["systemId"] == self.bow["systemId"]:
                        sensordata = bow["waterTemp"]
                        break

            self._name = (
                self._backyard["BackyardName"]
                + " "
                + self.bow.get("Name")
                + " Water Temperature"
            )

        elif self._kind == "air_temperature":
            for backyard in self.coordinator.data:
                if backyard.get("systemId") == self._attrs["MspSystemId"]:
                    sensordata = backyard.get("airTemp")

            self._name = self._backyard.get("BackyardName") + " Air Temperature"

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
        self._state = float(temp_state)
        self._unit = TEMP_FAHRENHEIT

        return self._state


class OmniLogicPumpSpeedSensor(OmnilogicSensor):
    """Define an OmniLogic Pump Speed Sensor."""

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
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            backyard=backyard,
            bow=bow,
            device_class=device_class,
            icon=icon,
            unit=unit,
            sensordata=sensordata,
        )

    @property
    def state(self):
        """Return the state for the pump speed sensor."""
        _LOGGER.debug("Updating state of sensor: %s", self._name)

        sensordata = {}
        pump_type = ""
        pump_speed = 0

        if self._kind == "filter_pump_speed":
            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    if bow["Filter"]["systemId"] == self.entitydata.get("systemId"):
                        sensordata = bow["Filter"]
                        break

            if sensordata.get("Filter-Type") == "FMT_VARIABLE_SPEED_PUMP":
                pump_type = "VARIABLE"
            elif sensordata.get("Filter-Type") == "FMP_SINGLE_SPEED":
                pump_type = "SINGLE"
            elif sensordata.get("Filter-Type") == "FMT_DUAL_SPEED":
                pump_type = "DUAL"

            pump_speed = sensordata.get("filterSpeed")

        elif self._kind == "pump_speed":
            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    for pump in bow.get("Pumps"):
                        if pump["systemId"] == self.entitydata["systemId"]:
                            sensordata = pump
                            break

            if sensordata.get("Filter-Type") == "PMP_VARIABLE_SPEED_PUMP":
                pump_type = "VARIABLE"
            elif sensordata.get("Filter-Type") == "PMP_SINGLE_SPEED":
                pump_type = "SINGLE"
            elif sensordata.get("Filter-Type") == "PMP_DUAL_SPEED":
                pump_type = "DUAL"

            pump_speed = sensordata.get("pumpSpeed")

        if pump_type == "VARIABLE":
            self._unit = "%"
            self._state = pump_speed
        elif pump_type == "DUAL":
            if pump_speed == 0:
                self._state = "off"
            elif pump_speed == sensordata.get("Min-Pump-Speed"):
                self._state = "low"
            elif pump_speed == sensordata.get("Max-Pump-Speed"):
                self._state = "high"
        elif pump_type == "SINGLE":
            if pump_speed == 0:
                self.state = "off"
            elif pump_speed == sensordata.get("Max-Pump-Speed"):
                self._state = "on"

        self._name = (
            self._backyard["BackyardName"]
            + " "
            + self.bow.get("Name")
            + " "
            + self.entitydata.get("Name")
        )

        self._attrs["PumpType"] = pump_type

        super().add_alarms(sensordata.get("Alarms"))

        return self._state


class OmniLogicSaltLevelSensor(OmnilogicSensor):
    """Define an OmniLogic Salt Level Sensor."""

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
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            backyard=backyard,
            bow=bow,
            device_class=device_class,
            icon=icon,
            unit=unit,
            sensordata=sensordata,
        )

    @property
    def state(self):
        """Return the state for the salt level sensor."""
        _LOGGER.debug("Updating state of sensor: %s", self._name)

        sensordata = super().find_chlorinator(
            self.coordinator, self.entitydata["systemId"]
        )

        salt_return = int(sensordata.get("avgSaltLevel"))
        unit_of_measurement = "ppm"

        if self._backyard["Unit-of-Measurement"] == "Metric":
            salt_return = round(salt_return / 1000, 2)
            unit_of_measurement = "g/L"

        self._state = salt_return
        self._unit = unit_of_measurement
        self._name = (
            self._backyard["BackyardName"]
            + " "
            + self.bow.get("Name")
            + " "
            + self.entitydata.get("Name")
            + " Salt Level"
        )

        super().add_alarms(sensordata.get("Alarms"))

        return self._state


class OmniLogicChlorinatorSensor(OmnilogicSensor):
    """Define an OmniLogic Chlorinator Sensor."""

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
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            backyard=backyard,
            bow=bow,
            device_class=device_class,
            icon=icon,
            unit=unit,
            sensordata=sensordata,
        )

    @property
    def state(self):
        """Return the state for the chlorinator sensor."""
        _LOGGER.debug("Updating state of sensor: %s", self._name)

        sensordata = super().find_chlorinator(
            self.coordinator, self.entitydata["systemId"]
        )

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

        super().add_alarms(sensordata.get("Alarms"))

        return self._state


class OmniLogicPHSensor(OmnilogicSensor):
    """Define an OmniLogic pH Sensor."""

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
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            backyard=backyard,
            bow=bow,
            device_class=device_class,
            icon=icon,
            unit=unit,
            sensordata=sensordata,
        )

    @property
    def state(self):
        """Return the state for the pH sensor."""
        _LOGGER.debug("Updating state of sensor: %s", self._name)

        sensordata = super().find_csad(self.coordinator, self.entitydata["systemId"])

        phstate = None
        if sensordata.get("ph") != 0:
            phstate = sensordata.get("ph")

        self._state = phstate
        self._unit = "pH"
        self._name = self._backyard["BackyardName"] + " " + self.bow.get("Name") + " pH"

        super().add_alarms(sensordata.get("Alarms"))

        return self._state


class OmniLogicORPSensor(OmnilogicSensor):
    """Define an OmniLogic ORP Sensor."""

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
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            backyard=backyard,
            bow=bow,
            device_class=device_class,
            icon=icon,
            unit=unit,
            sensordata=sensordata,
        )

    @property
    def state(self):
        """Return the state for the ORP sensor."""
        _LOGGER.debug("Updating state of sensor: %s", self._name)

        sensordata = super().find_csad(self.coordinator, self.entitydata["systemId"])

        orpstate = None
        if sensordata.get("orp") != -1:
            orpstate = sensordata.get("orp")

        self._state = orpstate
        self._unit = "mV"
        self._name = (
            self._backyard["BackyardName"] + " " + self.bow.get("Name") + " ORP"
        )

        super().add_alarms(sensordata.get("Alarms"))

        return self._state


class OmniLogicAlarmSensor(OmnilogicSensor):
    """Define an OmniLogic Alarm Sensor."""

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
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            backyard=backyard,
            bow=bow,
            device_class=device_class,
            icon=icon,
            unit=unit,
            sensordata=sensordata,
        )

    @property
    def state(self):
        """Return the state for the alarm sensor."""
        _LOGGER.debug("Updating state of sensor: %s", self._name)

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
