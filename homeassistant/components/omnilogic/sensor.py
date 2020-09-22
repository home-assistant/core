"""Definition and setup of the Omnilogic Sensors for Home Assistant."""

import logging

from homeassistant.components.sensor import DEVICE_CLASS_TEMPERATURE
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS, TEMP_FAHRENHEIT

from .const import COORDINATOR, DOMAIN, PUMP_TYPES
from .omnilogic_common import OmniLogicEntity, OmniLogicUpdateCoordinator

TEMP_UNITS = [TEMP_CELSIUS, TEMP_FAHRENHEIT]
PERCENT_UNITS = [PERCENTAGE, PERCENTAGE]
SALT_UNITS = ["g/L", "ppm"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
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
                DEVICE_CLASS_TEMPERATURE,
                None,
                TEMP_UNITS,
                backyard.get("airTemp"),
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
                    DEVICE_CLASS_TEMPERATURE,
                    None,
                    TEMP_UNITS,
                    bow.get("waterTemp"),
                )
            )

            if "Filter" in bow:
                sensors.append(
                    OmniLogicPumpSpeedSensor(
                        coordinator,
                        "filter_pump_speed",
                        "Pump Speed",
                        backyard,
                        bow,
                        None,
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
                        None,
                        "mdi:speedometer",
                        PERCENT_UNITS,
                        pump,
                    )
                )

            if "Chlorinator" in bow:
                sensors.append(
                    OmniLogicChlorinatorSensor(
                        coordinator,
                        "chlorinator",
                        "Chlorinator Setting",
                        backyard,
                        bow,
                        None,
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
                        None,
                        "mdi:gauge",
                        PERCENT_UNITS,
                        bow["Chlorinator"],
                    )
                )

            if "CSAD" in bow:
                if bow["CSAD"]["systemId"] != "0":
                    sensors.append(
                        OmniLogicPHSensor(
                            coordinator,
                            "csad_ph",
                            "pH",
                            backyard,
                            bow,
                            None,
                            "mdi:gauge",
                            PERCENT_UNITS,
                            bow["CSAD"],
                        )
                    )

                    sensors.append(
                        OmniLogicORPSensor(
                            coordinator,
                            "csad_orp",
                            "ORP",
                            backyard,
                            bow,
                            None,
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
        sensor_data: dict,
        system_id: str,
    ):
        """Initialize Entities."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            backyard=backyard,
            bow=bow,
            icon=icon,
            entity_data=sensor_data,
        )
        self._state = None
        self._unit_type = backyard["Unit-of-Measurement"]
        self._device_class = device_class
        self._unit = unit
        self._system_id = system_id

    @property
    def device_class(self):
        """Return the device class of the entity."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the right unit of measure."""
        return self._unit

    @property
    def force_update(self):
        """Force update."""
        return True

    @staticmethod
    def find_chlorinator(coordinator, systemid):
        """Find the correct chlorinator entity."""

        for backyard in coordinator.data:
            for bow in backyard.get("BOWS"):
                if bow["Chlorinator"]["systemId"] == systemid:
                    sensor_data = bow.get("Chlorinator")
                    break

        return sensor_data

    @staticmethod
    def find_csad(coordinator, systemid):
        """Find the correct CSAD entity."""

        for backyard in coordinator.data:
            for bow in backyard.get("BOWS"):
                if bow["CSAD"]["systemId"] == systemid:
                    sensor_data = bow.get("CSAD")
                    break

        return sensor_data


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
        sensor_data: dict,
    ):
        """Initialize the sensor."""
        backyard_name = backyard["BackyardName"]

        if kind == "water_temperature":
            system_id = bow["systemId"]
            name = f"{backyard_name} {bow['Name']} {name}"
        else:
            system_id = backyard["systemId"]
            name = f"{backyard_name} {name}"

        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            backyard=backyard,
            bow=bow,
            device_class=device_class,
            icon=icon,
            unit=unit,
            sensor_data=sensor_data,
            system_id=system_id,
        )

    @property
    def state(self):
        """Return the state for the temperature sensor."""
        _LOGGER.debug("Updating state of sensor: %s", self._name)

        sensor_data = None

        if self._kind == "water_temperature":
            for backyard in self.coordinator.data:
                for bow in backyard["BOWS"]:
                    if bow["systemId"] == self._system_id:
                        sensor_data = bow["waterTemp"]
                        break

        elif self._kind == "air_temperature":
            for backyard in self.coordinator.data:
                if backyard.get("systemId") == self._system_id:
                    sensor_data = backyard.get("airTemp")

        temp_return = int(sensor_data)
        temp_state = int(sensor_data)
        unit_of_measurement = TEMP_FAHRENHEIT
        if self._backyard["Unit-of-Measurement"] == "Metric":
            temp_return = round((temp_return - 32) * 5 / 9, 1)
            unit_of_measurement = TEMP_CELSIUS

        if int(sensor_data) == -1:
            temp_return = None
            temp_state = None

        self._attrs["hayward_temperature"] = temp_return
        self._attrs["hayward_unit_of_measure"] = unit_of_measurement
        if temp_state is not None:
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
        sensor_data: dict,
    ):
        """Initialize the sensor."""

        name = f"{backyard['BackyardName']} {bow['Name']} {name}"

        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            backyard=backyard,
            bow=bow,
            device_class=device_class,
            icon=icon,
            unit=unit,
            sensor_data=sensor_data,
            system_id=sensor_data.get("systemId"),
        )

    @property
    def state(self):
        """Return the state for the pump speed sensor."""

        sensor_data = {}
        pump_type = ""
        pump_speed = 0

        if self._kind == "filter_pump_speed":
            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    if bow["Filter"]["systemId"] == self._system_id:
                        sensor_data = bow["Filter"]
                        break

            pump_type = PUMP_TYPES.get(sensor_data.get("Filter-Type"))
            pump_speed = sensor_data.get("filterSpeed")

        elif self._kind == "pump_speed":
            for backyard in self.coordinator.data:
                for bow in backyard.get("BOWS"):
                    for pump in bow.get("Pumps"):
                        if pump["systemId"] == self.entity_data["systemId"]:
                            sensor_data = pump
                            break

            if sensor_data.get("Filter-Type") == "PMP_VARIABLE_SPEED_PUMP":
                pump_type = "VARIABLE"
            elif sensor_data.get("Filter-Type") == "PMP_SINGLE_SPEED":
                pump_type = "SINGLE"
            elif sensor_data.get("Filter-Type") == "PMP_DUAL_SPEED":
                pump_type = "DUAL"

            pump_speed = sensor_data.get("pumpSpeed")

        if pump_type == "VARIABLE":
            self._unit = "%"
            self._state = pump_speed
        elif pump_type == "DUAL":
            if pump_speed == 0:
                self._state = "off"
            elif pump_speed == sensor_data.get("Min-Pump-Speed"):
                self._state = "low"
            elif pump_speed == sensor_data.get("Max-Pump-Speed"):
                self._state = "high"
        elif pump_type == "SINGLE":
            if pump_speed == 0:
                self.state = "off"
            elif pump_speed == sensor_data.get("Max-Pump-Speed"):
                self._state = "on"

        self._attrs["PumpType"] = pump_type

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
        sensor_data: dict,
    ):
        """Initialize the sensor."""
        name = f"{backyard['BackyardName']} {bow['Name']} {name}"

        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            backyard=backyard,
            bow=bow,
            device_class=device_class,
            icon=icon,
            unit=unit,
            sensor_data=sensor_data,
            system_id=sensor_data["systemId"],
        )

    @property
    def state(self):
        """Return the state for the salt level sensor."""
        _LOGGER.debug("Updating state of sensor: %s", self._name)

        sensor_data = super().find_chlorinator(self.coordinator, self._system_id)

        salt_return = int(sensor_data.get("avgSaltLevel"))
        unit_of_measurement = "ppm"

        if self._backyard["Unit-of-Measurement"] == "Metric":
            salt_return = round(salt_return / 1000, 2)
            unit_of_measurement = "g/L"

        self._state = salt_return
        self._unit = unit_of_measurement

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
        sensor_data: dict,
    ):
        """Initialize the sensor."""
        name = f"{backyard['BackyardName']} {bow['Name']} {name}"

        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            backyard=backyard,
            bow=bow,
            device_class=device_class,
            icon=icon,
            unit=unit,
            sensor_data=sensor_data,
            system_id=sensor_data["systemId"],
        )

    @property
    def state(self):
        """Return the state for the chlorinator sensor."""
        _LOGGER.debug("Updating state of sensor: %s", self._name)

        sensor_data = super().find_chlorinator(self.coordinator, self._system_id)

        if sensor_data.get("operatingMode") == "1":
            self._state = sensor_data.get("Timed-Percent")
            self._unit = "%"
        elif sensor_data.get("operatingMode") == "2":
            if sensor_data.get("Timed-Percent") == "100":
                self._state = "on"
            else:
                self._state = "off"

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
        sensor_data: dict,
    ):
        """Initialize the sensor."""
        name = f"{backyard['BackyardName']} {bow['Name']} {name}"

        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            backyard=backyard,
            bow=bow,
            device_class=device_class,
            icon=icon,
            unit=unit,
            sensor_data=sensor_data,
            system_id=sensor_data["systemId"],
        )

    @property
    def state(self):
        """Return the state for the pH sensor."""
        _LOGGER.debug("Updating state of sensor: %s", self._name)

        sensor_data = super().find_csad(self.coordinator, self._system_id)

        phstate = None
        if sensor_data.get("ph") != 0:
            phstate = sensor_data.get("ph")

        self._state = phstate
        self._unit = "pH"

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
        sensor_data: dict,
    ):
        """Initialize the sensor."""
        name = f"{backyard['BackyardName']} {bow['Name']} {name}"

        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            backyard=backyard,
            bow=bow,
            device_class=device_class,
            icon=icon,
            unit=unit,
            sensor_data=sensor_data,
            system_id=sensor_data["systemId"],
        )

    @property
    def state(self):
        """Return the state for the ORP sensor."""
        _LOGGER.debug("Updating state of sensor: %s", self._name)

        sensor_data = super().find_csad(self.coordinator, self._system_id)

        orpstate = None
        if sensor_data.get("orp") != -1:
            orpstate = sensor_data.get("orp")

        self._state = orpstate
        self._unit = "mV"

        return self._state
