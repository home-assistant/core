"""DVLA sensor platform."""

from contextlib import suppress
from datetime import date
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_REG_NUMBER, DOMAIN
from .coordinator import DVLACoordinator

# Fallback/Overrides for icons and units
ENTITY_METADATA: dict[str, dict[str, Any]] = {
    "registrationNumber": {"icon": "mdi:ocr", "title": "Registration Number"},
    "taxStatus": {"icon": "mdi:cash-clock", "title": "Tax Status"},
    "taxDueDate": {
        "icon": "mdi:calendar-clock",
        "device_class": SensorDeviceClass.DATE,
        "title": "Tax Due Date",
    },
    "artEndDate": {
        "icon": "mdi:calendar-end",
        "device_class": SensorDeviceClass.DATE,
        "title": "Additional Rate of Tax End Date",
    },
    "motStatus": {"icon": "mdi:car-wrench"},
    "make": {"icon": "mdi:car"},
    "yearOfManufacture": {"icon": "mdi:calendar-month"},
    "engineCapacity": {
        "icon": "mdi:engine",
        "native_unit_of_measurement": "cc",
        "title": "Engine Capacity",
    },
    "co2Emissions": {
        "icon": "mdi:molecule-co2",
        "native_unit_of_measurement": "g/km",
        "title": "CO2 Emissions",
    },
    "fuelType": {"icon": "mdi:gas-station", "title": "Fuel Type"},
    "colour": {"icon": "mdi:spray"},
    "typeApproval": {"icon": "mdi:car"},
    "revenueWeight": {
        "icon": "mdi:weight-kilogram",
        "device_class": SensorDeviceClass.WEIGHT,
        "native_unit_of_measurement": UnitOfMass.KILOGRAMS,
        "title": "Revenue Weight",
    },
    "dateOfLastV5CIssued": {
        "icon": "mdi:calendar",
        "device_class": SensorDeviceClass.DATE,
    },
    "motExpiryDate": {
        "icon": "mdi:calendar-check",
        "device_class": SensorDeviceClass.DATE,
    },
    "wheelplan": {"icon": "mdi:tire"},
    "monthOfFirstRegistration": {"icon": "mdi:calendar-month", "device_class": None},
    "monthOfFirstDvlaRegistration": {
        "icon": "mdi:calendar-month-outline",
        "device_class": None,
    },
    "realDrivingEmissions": {
        "icon": "mdi:gas-station-outline",
        "title": "Real Driving Emissions",
    },
    "euroStatus": {"icon": "mdi:currency-eur", "title": "Euro Status"},
}
SENSOR_KEYS: tuple[str, ...] = (
    "registrationNumber",
    "taxStatus",
    "taxDueDate",
    "artEndDate",
    "motStatus",
    "make",
    "yearOfManufacture",
    "engineCapacity",
    "co2Emissions",
    "fuelType",
    "colour",
    "typeApproval",
    "revenueWeight",
    "dateOfLastV5CIssued",
    "motExpiryDate",
    "wheelplan",
    "monthOfFirstRegistration",
    "monthOfFirstDvlaRegistration",
    "realDrivingEmissions",
    "euroStatus",
)
ENTITY_DESCRIPTIONS: dict[str, str] = {
    "registrationNumber": "Registration number",
    "taxStatus": "Tax status",
    "taxDueDate": "Tax due date",
    "artEndDate": "Additional rate of tax end date",
    "motStatus": "M.O.T status",
    "make": "Make",
    "yearOfManufacture": "Year of manufacture",
    "engineCapacity": "Engine capacity",
    "co2Emissions": "CO2 emissions",
    "fuelType": "Fuel type",
    "colour": "Colour",
    "typeApproval": "Type approval",
    "revenueWeight": "Revenue weight",
    "dateOfLastV5CIssued": "Date of last V5C issued",
    "motExpiryDate": "M.O.T expiry date",
    "wheelplan": "Wheelplan",
    "monthOfFirstRegistration": "Month of first registration",
    "monthOfFirstDvlaRegistration": "Month of first DVLA registration",
    "realDrivingEmissions": "Real driving emissions",
    "euroStatus": "Euro status",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors from a config entry created in the integrations UI."""
    config = entry.runtime_data

    coordinator: DVLACoordinator = config["coordinator"]
    name = entry.data[CONF_REG_NUMBER]

    sensors: list[DVLASensor] = []

    for key in SENSOR_KEYS:
        metadata = ENTITY_METADATA.get(key, {})

        description = SensorEntityDescription(
            key=key,
            name=metadata.get("title", ENTITY_DESCRIPTIONS[key]),
            icon=metadata.get("icon", "mdi:car"),
            device_class=metadata.get("device_class"),
            native_unit_of_measurement=metadata.get("native_unit_of_measurement"),
        )

        sensors.append(DVLASensor(coordinator, name, description))
    async_add_entities(sensors)


class DVLASensor(CoordinatorEntity[DVLACoordinator], SensorEntity):
    """Define a DVLA sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DVLACoordinator,
        name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{name}")},
            manufacturer=DOMAIN.upper(),
            model=coordinator.data.get("make"),
            name=name.upper(),
        )
        self._attr_unique_id = f"{name}-{description.key}".lower()
        self.entity_id = f"sensor.{DOMAIN}_{name}_{description.key}".lower()
        self.attrs: dict[str, Any] = {}
        self.entity_description = description
        self._state: StateType | date = None
        self.update_from_coordinator()

    def update_from_coordinator(self) -> None:
        """Update sensor state and attributes from coordinator data."""
        key = self.entity_description.key
        self._state = self.coordinator.data.get(key)

        if key == "monthOfFirstRegistration" and self._state is None:
            self._state = self.coordinator.data.get("monthOfFirstDvlaRegistration")

        if key == "revenueWeight" and self._state is not None:
            with suppress(TypeError, ValueError):
                self._state = int(self._state)

            if not isinstance(self._state, int):
                self._state = None

        if key == "motExpiryDate" and not self._state:
            reg_month_str = self.coordinator.data.get("monthOfFirstRegistration")
            if reg_month_str:
                with suppress(ValueError):
                    year_str, month_str = reg_month_str.split("-")
                    calculated_date = date(int(year_str) + 3, int(month_str), 1)
                    self._state = calculated_date.isoformat()

        if (
            self._state
            and self.entity_description.device_class == SensorDeviceClass.DATE
        ):
            try:
                self._state = date.fromisoformat(str(self._state))
            except ValueError:
                self._state = None

        self.attrs = self.coordinator.data.copy() if self._state is not None else {}

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_from_coordinator()
        self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        # Ensure entity is available even if specific key is missing but we have coordinator data
        return self.coordinator.last_update_success

    @property
    @override
    def native_value(self) -> StateType | date:
        """Native value."""
        return self._state

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Define entity attributes."""
        return self.attrs
