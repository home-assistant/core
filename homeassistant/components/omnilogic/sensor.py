"""Definition and setup of the Omnilogic Sensors for Home Assistant."""

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfMass,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import OmniLogicEntity, check_guard
from .const import COORDINATOR, DEFAULT_PH_OFFSET, DOMAIN, PUMP_TYPES
from .coordinator import OmniLogicUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""

    coordinator: OmniLogicUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]
    entities = []

    for item_id, item in coordinator.data.items():
        id_len = len(item_id)
        item_kind = item_id[-2]
        entity_settings = SENSOR_TYPES.get((id_len, item_kind))

        if not entity_settings:
            continue

        for entity_setting in entity_settings:
            entity_classes: dict[str, type] = entity_setting["entity_classes"]
            for state_key, entity_class in entity_classes.items():
                if check_guard(state_key, item, entity_setting):
                    continue

                entity = entity_class(
                    coordinator=coordinator,
                    state_key=state_key,
                    name=entity_setting["name"],
                    kind=entity_setting["kind"],
                    item_id=item_id,
                    device_class=entity_setting["device_class"],
                    icon=entity_setting["icon"],
                    unit=entity_setting["unit"],
                )

                entities.append(entity)

    async_add_entities(entities)


class OmnilogicSensor(OmniLogicEntity, SensorEntity):
    """Defines an Omnilogic sensor entity."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        kind: str,
        name: str,
        device_class: SensorDeviceClass | None,
        icon: str,
        unit: str,
        item_id: tuple,
        state_key: str,
    ) -> None:
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

        self._unit_type = unit_type
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._state_key = state_key


class OmniLogicTemperatureSensor(OmnilogicSensor):
    """Define an OmniLogic Temperature (Air/Water) Sensor."""

    @property
    def native_value(self):
        """Return the state for the temperature sensor."""
        sensor_data = self.coordinator.data[self._item_id][self._state_key]

        hayward_state = sensor_data
        hayward_unit_of_measure = UnitOfTemperature.FAHRENHEIT
        state = sensor_data

        if self._unit_type == "Metric":
            hayward_state = round((int(hayward_state) - 32) * 5 / 9, 1)
            hayward_unit_of_measure = UnitOfTemperature.CELSIUS

        if int(sensor_data) == -1:
            hayward_state = None
            state = None

        self._attrs["hayward_temperature"] = hayward_state
        self._attrs["hayward_unit_of_measure"] = hayward_unit_of_measure

        self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT

        return state


class OmniLogicPumpSpeedSensor(OmnilogicSensor):
    """Define an OmniLogic Pump Speed Sensor."""

    @property
    def native_value(self):
        """Return the state for the pump speed sensor."""

        pump_type = PUMP_TYPES[
            self.coordinator.data[self._item_id].get(
                "Filter-Type", self.coordinator.data[self._item_id].get("Type", {})
            )
        ]
        pump_speed = self.coordinator.data[self._item_id][self._state_key]

        if pump_type == "VARIABLE":
            self._attr_native_unit_of_measurement = PERCENTAGE
            state = pump_speed
        elif pump_type == "DUAL":
            self._attr_native_unit_of_measurement = None
            if pump_speed == 0:
                state = "off"
            elif pump_speed == self.coordinator.data[self._item_id].get(
                "Min-Pump-Speed"
            ):
                state = "low"
            elif pump_speed == self.coordinator.data[self._item_id].get(
                "Max-Pump-Speed"
            ):
                state = "high"

        self._attrs["pump_type"] = pump_type

        return state


class OmniLogicSaltLevelSensor(OmnilogicSensor):
    """Define an OmniLogic Salt Level Sensor."""

    @property
    def native_value(self):
        """Return the state for the salt level sensor."""

        salt_return = self.coordinator.data[self._item_id][self._state_key]

        if self._unit_type == "Metric":
            salt_return = round(int(salt_return) / 1000, 2)
            self._attr_native_unit_of_measurement = (
                f"{UnitOfMass.GRAMS}/{UnitOfVolume.LITERS}"
            )

        return salt_return


class OmniLogicChlorinatorSensor(OmnilogicSensor):
    """Define an OmniLogic Chlorinator Sensor."""

    @property
    def native_value(self):
        """Return the state for the chlorinator sensor."""
        return self.coordinator.data[self._item_id][self._state_key]


class OmniLogicPHSensor(OmnilogicSensor):
    """Define an OmniLogic pH Sensor."""

    @property
    def native_value(self):
        """Return the state for the pH sensor."""

        ph_state = self.coordinator.data[self._item_id][self._state_key]

        if ph_state == 0:
            ph_state = None
        else:
            ph_state = float(ph_state) + float(
                self.coordinator.config_entry.options.get(
                    "ph_offset", DEFAULT_PH_OFFSET
                )
            )

        return ph_state


class OmniLogicORPSensor(OmnilogicSensor):
    """Define an OmniLogic ORP Sensor."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        state_key: str,
        name: str,
        kind: str,
        item_id: tuple,
        device_class: SensorDeviceClass | None,
        icon: str,
        unit: str,
    ) -> None:
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
    def native_value(self):
        """Return the state for the ORP sensor."""

        orp_state = int(self.coordinator.data[self._item_id][self._state_key])

        if orp_state == -1:
            orp_state = None

        return orp_state


SENSOR_TYPES: dict[tuple[int, str], list[dict[str, Any]]] = {
    (2, "Backyard"): [
        {
            "entity_classes": {"airTemp": OmniLogicTemperatureSensor},
            "name": "Air Temperature",
            "kind": "air_temperature",
            "device_class": SensorDeviceClass.TEMPERATURE,
            "icon": None,
            "unit": UnitOfTemperature.FAHRENHEIT,
            "guard_condition": [{}],
        },
    ],
    (4, "BOWS"): [
        {
            "entity_classes": {"waterTemp": OmniLogicTemperatureSensor},
            "name": "Water Temperature",
            "kind": "water_temperature",
            "device_class": SensorDeviceClass.TEMPERATURE,
            "icon": None,
            "unit": UnitOfTemperature.FAHRENHEIT,
            "guard_condition": [{}],
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
            "guard_condition": [
                {"Filter-Type": "FMT_SINGLE_SPEED"},
            ],
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
            "guard_condition": [
                {"Type": "PMP_SINGLE_SPEED"},
            ],
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
            "guard_condition": [
                {
                    "Shared-Type": "BOW_SHARED_EQUIPMENT",
                    "status": "0",
                },
                {
                    "operatingMode": "2",
                },
            ],
        },
        {
            "entity_classes": {"avgSaltLevel": OmniLogicSaltLevelSensor},
            "name": "Salt Level",
            "kind": "salt_level",
            "device_class": None,
            "icon": "mdi:gauge",
            "unit": CONCENTRATION_PARTS_PER_MILLION,
            "guard_condition": [
                {
                    "Shared-Type": "BOW_SHARED_EQUIPMENT",
                    "status": "0",
                },
            ],
        },
    ],
    (6, "CSAD"): [
        {
            "entity_classes": {"ph": OmniLogicPHSensor},
            "name": "pH",
            "kind": "csad_ph",
            "device_class": None,
            "icon": "mdi:gauge",
            "unit": "pH",
            "guard_condition": [
                {"ph": ""},
            ],
        },
        {
            "entity_classes": {"orp": OmniLogicORPSensor},
            "name": "ORP",
            "kind": "csad_orp",
            "device_class": None,
            "icon": "mdi:gauge",
            "unit": UnitOfElectricPotential.MILLIVOLT,
            "guard_condition": [
                {"orp": ""},
            ],
        },
    ],
}
