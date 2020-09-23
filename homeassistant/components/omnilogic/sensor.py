"""Definition and setup of the Omnilogic Sensors for Home Assistant."""

import logging

from homeassistant.components.sensor import DEVICE_CLASS_TEMPERATURE
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    MASS_GRAMS,
    PERCENTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    VOLUME_LITERS,
)

from .common import OmniLogicEntity, OmniLogicUpdateCoordinator
from .const import COORDINATOR, DOMAIN, PUMP_TYPES

TEMP_UNITS = [TEMP_CELSIUS, TEMP_FAHRENHEIT]
PERCENT_UNITS = [PERCENTAGE, PERCENTAGE]
SALT_UNITS = [f"{MASS_GRAMS}/{VOLUME_LITERS}", CONCENTRATION_PARTS_PER_MILLION]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""

    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    sensors = []

    for this_entity in coordinator.data:
        entity_data = coordinator.data[this_entity]

        if entity_data["type"] == "backyard":
            sensors.append(
                OmniLogicTemperatureSensor(
                    coordinator,
                    "air_temperature",
                    "Air Temperature",
                    this_entity,
                    entity_data,
                    DEVICE_CLASS_TEMPERATURE,
                    None,
                    TEMP_FAHRENHEIT,
                )
            )

        if entity_data["type"] == "bow":
            sensors.append(
                OmniLogicTemperatureSensor(
                    coordinator,
                    "water_temperature",
                    "Water Temperature",
                    this_entity,
                    entity_data,
                    DEVICE_CLASS_TEMPERATURE,
                    None,
                    TEMP_FAHRENHEIT,
                )
            )

        if entity_data["type"] == "filter":
            sensors.append(
                OmniLogicPumpSpeedSensor(
                    coordinator,
                    "filter_pump_speed",
                    "Speed",
                    this_entity,
                    entity_data,
                    None,
                    "mdi:speedometer",
                    PERCENTAGE,
                )
            )

        if entity_data["type"] == "pump":
            sensors.append(
                OmniLogicPumpSpeedSensor(
                    coordinator,
                    "pump_speed",
                    "Pump Speed",
                    this_entity,
                    entity_data,
                    None,
                    "mdi:speedometer",
                    PERCENTAGE,
                )
            )

        if entity_data["type"] == "chlorinator":
            if (entity_data.get("Shared-Type") != "BOW_SHARED_EQUIPMENT") or (
                entity_data.get("Shared-Type") == "BOW_SHARED_EQUIPMENT"
                and entity_data["status"] != "0"
            ):
                sensors.append(
                    OmniLogicChlorinatorSensor(
                        coordinator,
                        "chlorinator",
                        "Setting",
                        this_entity,
                        entity_data,
                        None,
                        "mdi:gauge",
                        PERCENTAGE,
                    )
                )

                sensors.append(
                    OmniLogicSaltLevelSensor(
                        coordinator,
                        "salt_level",
                        "Salt Level",
                        this_entity,
                        entity_data,
                        None,
                        "mdi:gauge",
                        PERCENTAGE,
                    )
                )

        if entity_data["type"] == "csad":
            if entity_data.get("orp") != "":
                sensors.append(
                    OmniLogicORPSensor(
                        coordinator,
                        "csad_orp",
                        "ORP",
                        this_entity,
                        entity_data,
                        None,
                        "mdi:gauge",
                        PERCENTAGE,
                    )
                )

            if entity_data.get("ph") != "":
                sensors.append(
                    OmniLogicPHSensor(
                        coordinator,
                        "csad_ph",
                        "pH",
                        this_entity,
                        entity_data,
                        None,
                        "mdi:gauge",
                        PERCENTAGE,
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
        device_class: str,
        icon: str,
        unit: str,
        entity_data: dict,
        entity: tuple,
    ):
        """Initialize Entities."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            entity_data=entity_data,
            entity=entity,
            icon=icon,
        )

        if entity_data.get("parent_backyard") is None:
            unit_type = entity_data.get("Unit-of-Measurement")
        else:
            unit_type = coordinator.data[entity_data.get("parent_backyard")][
                "Unit-of-Measurement"
            ]

        self._state = None
        self._unit_type = unit_type
        self._device_class = device_class
        self._unit = unit

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


class OmniLogicTemperatureSensor(OmnilogicSensor):
    """Define an OmniLogic Temperature (Air/Water) Sensor."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        kind: str,
        name: str,
        entity: tuple,
        entity_data: dict,
        device_class: str,
        icon: str,
        unit: str,
    ):
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            device_class=device_class,
            icon=icon,
            unit=unit,
            entity_data=entity_data,
            entity=entity,
        )

    @property
    def state(self):
        """Return the state for the temperature sensor."""
        sensor_data = None

        if self._kind == "water_temperature":
            sensor_data = self.coordinator.data[self._entity].get("waterTemp")

        elif self._kind == "air_temperature":
            sensor_data = self.coordinator.data[self._entity].get("airTemp")

        temp_return = int(sensor_data)
        temp_state = int(sensor_data)
        unit_of_measurement = TEMP_FAHRENHEIT
        if self._unit_type == "Metric":
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
        entity: tuple,
        entity_data: dict,
        device_class: str,
        icon: str,
        unit: str,
    ):
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            device_class=device_class,
            icon=icon,
            unit=unit,
            entity_data=entity_data,
            entity=entity,
        )

    @property
    def state(self):
        """Return the state for the pump speed sensor."""

        sensor_data = self.coordinator.data[self._entity]
        pump_type = PUMP_TYPES.get(sensor_data.get("Filter-Type"))

        pump_speed = 0

        if self._kind == "filter_pump_speed":
            pump_speed = sensor_data.get("filterSpeed")
        elif self._kind == "pump_speed":
            pump_speed = sensor_data.get("pumpSpeed")

        if pump_type == "VARIABLE":
            self._unit = PERCENTAGE
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

        self._attrs["pump_type"] = pump_type

        return self._state


class OmniLogicSaltLevelSensor(OmnilogicSensor):
    """Define an OmniLogic Salt Level Sensor."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        kind: str,
        name: str,
        entity: tuple,
        entity_data: dict,
        device_class: str,
        icon: str,
        unit: str,
    ):
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            device_class=device_class,
            icon=icon,
            unit=unit,
            entity_data=entity_data,
            entity=entity,
        )

    @property
    def state(self):
        """Return the state for the salt level sensor."""
        sensor_data = self.coordinator.data[self._entity]

        salt_return = sensor_data.get("avgSaltLevel")
        unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION

        if self._unit_type == "Metric":
            salt_return = round(salt_return / 1000, 2)
            unit_of_measurement = f"{MASS_GRAMS}/{VOLUME_LITERS}"

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
        entity: tuple,
        entity_data: dict,
        device_class: str,
        icon: str,
        unit: str,
    ):
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            device_class=device_class,
            icon=icon,
            unit=unit,
            entity_data=entity_data,
            entity=entity,
        )

    @property
    def state(self):
        """Return the state for the chlorinator sensor."""
        sensor_data = self.coordinator.data[self._entity]

        if sensor_data.get("operatingMode") == "1":
            self._state = sensor_data.get("Timed-Percent")
            self._unit = PERCENTAGE
        elif sensor_data.get("operatingMode") == "2":
            self._unit = None
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
        entity: tuple,
        entity_data: dict,
        device_class: str,
        icon: str,
        unit: str,
    ):
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            device_class=device_class,
            icon=icon,
            unit=unit,
            entity_data=entity_data,
            entity=entity,
        )

    @property
    def state(self):
        """Return the state for the pH sensor."""
        sensor_data = self.coordinator.data[self._entity]

        ph_state = None
        if sensor_data.get("ph") != 0:
            ph_state = sensor_data["ph"]

        self._state = ph_state
        self._unit = "pH"

        return self._state


class OmniLogicORPSensor(OmnilogicSensor):
    """Define an OmniLogic ORP Sensor."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        kind: str,
        name: str,
        entity: tuple,
        entity_data: dict,
        device_class: str,
        icon: str,
        unit: str,
    ):
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            device_class=device_class,
            icon=icon,
            unit=unit,
            entity_data=entity_data,
            entity=entity,
        )

    @property
    def state(self):
        """Return the state for the ORP sensor."""
        sensor_data = self.coordinator.data[self._entity]

        orp_state = None
        if sensor_data.get("orp") != -1:
            orp_state = sensor_data["orp"]

        self._state = orp_state
        self._unit = "mV"

        return self._state
