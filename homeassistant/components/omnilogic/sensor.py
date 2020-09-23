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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""

    SENSOR_TYPES = {
        (2, "Backyard"): [
            {
                "entity_classes": {"airTemp": OmniLogicTemperatureSensor},
                "name": "Air Temperature",
                "kind": "air_temperature",
                "device_class": DEVICE_CLASS_TEMPERATURE,
                "icon": None,
                "unit": TEMP_FAHRENHEIT,
                "guard_condition": {},
            },
        ],
        (4, "BOWS"): [
            {
                "entity_classes": {"waterTemp": OmniLogicTemperatureSensor},
                "name": "Water Temperature",
                "kind": "water_temperature",
                "device_class": DEVICE_CLASS_TEMPERATURE,
                "icon": None,
                "unit": TEMP_FAHRENHEIT,
                "guard_condition": {},
            },
        ],
        (6, "Filter"): [
            {
                "entity_classes": {"filterSpeed": OmniLogicPumpSpeedSensor},
                "name": "Speed",
                "kind": "filter_pump_speed",
                "device_class": None,
                "icon": "mdi:speedometer",
                "unit": PERCENTAGE,
                "guard_condition": {},
            },
        ],
        (6, "Pumps"): [
            {
                "entity_classes": {"pumpSpeed": OmniLogicPumpSpeedSensor},
                "name": "Pump Speed",
                "kind": "pump_speed",
                "device_class": None,
                "icon": "mdi:speedometer",
                "unit": PERCENTAGE,
                "guard_condition": {},
            },
        ],
        (6, "Chlorinator"): [
            {
                "entity_classes": {"Timed-Percent": OmniLogicChlorinatorSensor},
                "name": "Setting",
                "kind": "chlorinator",
                "device_class": None,
                "icon": "mdi:gauge",
                "unit": PERCENTAGE,
                "guard_condition": {
                    "Shared-Type": "BOW_SHARED_EQUIPMENT",
                    "status": "0",
                },
            },
            {
                "entity_classes": {"avgSaltLevel": OmniLogicSaltLevelSensor},
                "name": "Salt Level",
                "kind": "salt_level",
                "device_class": None,
                "icon": "mdi:gauge",
                "unit": None,
                "guard_condition": {
                    "Shared-Type": "BOW_SHARED_EQUIPMENT",
                    "status": "0",
                },
            },
        ],
        (6, "CSAD"): [
            {
                "entity_classes": {"ph": OmniLogicPHSensor},
                "name": "pH",
                "kind": "csad_ph",
                "device_class": None,
                "icon": "mdi:gauge",
                "unit": None,
                "guard_condition": {"ph": ""},
            },
            {
                "entity_classes": {"orp": OmniLogicORPSensor},
                "name": "ORP",
                "kind": "csad_orp",
                "device_class": None,
                "icon": "mdi:gauge",
                "unit": None,
                "guard_condition": {"orp": ""},
            },
        ],
    }

    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    entities = []

    for item_id, item in coordinator.data.items():
        id_len = len(item_id)
        item_kind = item_id[-2]
        entity_settings = SENSOR_TYPES.get((id_len, item_kind))

        if not entity_settings:
            continue

        for entity_setting in entity_settings:
            for state_key, entity_class in entity_setting["entity_classes"].items():
                if state_key not in item:
                    continue

                guard_condition = entity_setting["guard_condition"]
                if guard_condition and all(
                    item.get(guard_key) == guard_value
                    for guard_key, guard_value in guard_condition.items()
                ):
                    continue

                entity = entity_class(
                    coordinator,
                    state_key,
                    entity_setting["name"],
                    entity_setting["kind"],
                    item_id,
                    entity_setting["device_class"],
                    entity_setting["icon"],
                    entity_setting["unit"],
                )

                entities.append(entity)

    async_add_entities(entities, update_before_add=True)


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
        item_id: tuple,
        state_key: str,
    ):
        """Initialize Entities."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            item_id=item_id,
            icon=icon,
        )

        backyard_id = item_id[:2]
        unit_type = coordinator.data[backyard_id].get("Unit-of-Measurement")

        self._state = None
        self._unit_type = unit_type
        self._device_class = device_class
        self._unit = unit
        self._state_key = state_key

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
        state_key: str,
        name: str,
        kind: str,
        item_id: tuple,
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
            item_id=item_id,
            state_key=state_key,
        )

    @property
    def state(self):
        """Return the state for the temperature sensor."""
        sensor_data = self.coordinator.data[self._item_id].get(self._state_key)

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
        state_key: str,
        name: str,
        kind: str,
        item_id: tuple,
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
            item_id=item_id,
            state_key=state_key,
        )

    @property
    def state(self):
        """Return the state for the pump speed sensor."""

        pump_type = PUMP_TYPES.get(
            self.coordinator.data[self._item_id].get("Filter-Type")
        )
        pump_speed = self.coordinator.data[self._item_id].get(self._state_key)

        if pump_type == "VARIABLE":
            self._unit = PERCENTAGE
            self._state = pump_speed
        elif pump_type == "DUAL":
            if pump_speed == 0:
                self._state = "off"
            elif pump_speed == self.coordinator.data[self._item_id].get(
                "Min-Pump-Speed"
            ):
                self._state = "low"
            elif pump_speed == self.coordinator.data[self._item_id].get(
                "Max-Pump-Speed"
            ):
                self._state = "high"
        elif pump_type == "SINGLE":
            if pump_speed == 0:
                self.state = "off"
            elif pump_speed == self.coordinator.data[self._item_id].get(
                "Max-Pump-Speed"
            ):
                self._state = "on"

        self._attrs["pump_type"] = pump_type

        return self._state


class OmniLogicSaltLevelSensor(OmnilogicSensor):
    """Define an OmniLogic Salt Level Sensor."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        state_key: str,
        name: str,
        kind: str,
        item_id: tuple,
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
            item_id=item_id,
            state_key=state_key,
        )

    @property
    def state(self):
        """Return the state for the salt level sensor."""

        salt_return = self.coordinator.data[self._item_id].get(self._state_key)
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
        state_key: str,
        name: str,
        kind: str,
        item_id: tuple,
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
            item_id=item_id,
            state_key=state_key,
        )

    @property
    def state(self):
        """Return the state for the chlorinator sensor."""
        state = self.coordinator.data[self._item_id].get(self._state_key)
        operating_mode = self.coordinator.data[self._item_id].get("operatingMode")

        if operating_mode == "1":
            self._state = state
            self._unit = PERCENTAGE
        elif operating_mode == "2":
            self._unit = None
            if state == "100":
                self._state = "on"
            else:
                self._state = "off"

        return self._state


class OmniLogicPHSensor(OmnilogicSensor):
    """Define an OmniLogic pH Sensor."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        state_key: str,
        name: str,
        kind: str,
        item_id: tuple,
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
            item_id=item_id,
            state_key=state_key,
        )

    @property
    def state(self):
        """Return the state for the pH sensor."""

        ph_state = self.coordinator.data[self._item_id].get(self._state_key)

        if ph_state == 0:
            ph_state = None

        self._state = ph_state
        self._unit = "pH"

        return self._state


class OmniLogicORPSensor(OmnilogicSensor):
    """Define an OmniLogic ORP Sensor."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        state_key: str,
        name: str,
        kind: str,
        item_id: tuple,
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
            item_id=item_id,
            state_key=state_key,
        )

    @property
    def state(self):
        """Return the state for the ORP sensor."""

        orp_state = self.coordinator.data[self._item_id].get(self._state_key)

        if orp_state == -1:
            orp_state = None

        self._state = orp_state
        self._unit = "mV"

        return self._state
