"""DVLA sensor platform."""

from contextlib import suppress
from datetime import date
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DVLAConfigEntry
from .const import DOMAIN
from .coordinator import DVLACoordinator

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="registrationNumber",
        icon="mdi:ocr",
        name="Registration number",
    ),
    SensorEntityDescription(
        key="taxStatus",
        icon="mdi:cash-clock",
        name="Tax status",
    ),
    SensorEntityDescription(
        key="taxDueDate",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar-clock",
        name="Tax due date",
    ),
    SensorEntityDescription(
        key="artEndDate",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar-end",
        name="Additional rate of tax end date",
    ),
    SensorEntityDescription(
        key="motStatus",
        icon="mdi:car-wrench",
        name="MOT status",  # codespell:ignore
    ),
    SensorEntityDescription(
        key="make",
        icon="mdi:car",
        name="Make",
    ),
    SensorEntityDescription(
        key="yearOfManufacture",
        icon="mdi:calendar-month",
        name="Year of manufacture",
    ),
    SensorEntityDescription(
        key="engineCapacity",
        icon="mdi:engine",
        name="Engine capacity",
        native_unit_of_measurement="cc",
    ),
    SensorEntityDescription(
        key="co2Emissions",
        icon="mdi:molecule-co2",
        name="CO2 emissions",
        native_unit_of_measurement="g/km",
    ),
    SensorEntityDescription(
        key="fuelType",
        icon="mdi:gas-station",
        name="Fuel type",
    ),
    SensorEntityDescription(
        key="colour",
        icon="mdi:spray",
        name="Color",
    ),
    SensorEntityDescription(
        key="typeApproval",
        icon="mdi:car",
        name="Type approval",
    ),
    SensorEntityDescription(
        key="revenueWeight",
        device_class=SensorDeviceClass.WEIGHT,
        icon="mdi:weight-kilogram",
        name="Revenue weight",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
    ),
    SensorEntityDescription(
        key="dateOfLastV5CIssued",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar",
        name="Date of last V5C issued",
    ),
    SensorEntityDescription(
        key="motExpiryDate",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar-check",
        name="MOT expiry date",  # codespell:ignore
    ),
    SensorEntityDescription(
        key="wheelplan",
        icon="mdi:tire",
        name="Wheelplan",
    ),
    SensorEntityDescription(
        key="monthOfFirstRegistration",
        icon="mdi:calendar-month",
        name="Month of first registration",
    ),
    SensorEntityDescription(
        key="monthOfFirstDvlaRegistration",
        icon="mdi:calendar-month-outline",
        name="Month of first DVLA registration",
    ),
    SensorEntityDescription(
        key="realDrivingEmissions",
        icon="mdi:gas-station-outline",
        name="Real driving emissions",
    ),
    SensorEntityDescription(
        key="euroStatus",
        icon="mdi:currency-eur",
        name="Euro status",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DVLAConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors from a config entry created in the integrations UI."""
    coordinator = entry.runtime_data
    reg_number = coordinator.reg_number

    async_add_entities(
        DVLASensor(coordinator, reg_number, description)
        for description in SENSOR_DESCRIPTIONS
    )


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
            identifiers={(DOMAIN, name)},
            manufacturer=coordinator.data.get("make"),
            name=name.upper(),
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_unique_id = f"{name}-{description.key}".lower()
        self.entity_description = description
        self._state: StateType | date = None
        self.update_from_coordinator()

    def update_from_coordinator(self) -> None:
        """Update sensor state and attributes from coordinator data."""
        key = self.entity_description.key
        self._state = self.coordinator.data.get(key)

        if key == "revenueWeight" and self._state is not None:
            with suppress(TypeError, ValueError):
                self._state = int(self._state)

            if not isinstance(self._state, int):
                self._state = None

        if (
            self._state
            and self.entity_description.device_class == SensorDeviceClass.DATE
        ):
            try:
                self._state = date.fromisoformat(str(self._state))
            except ValueError:
                self._state = None

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_from_coordinator()
        self.async_write_ha_state()

    @property
    @override
    def native_value(self) -> StateType | date:
        """Native value."""
        return self._state
