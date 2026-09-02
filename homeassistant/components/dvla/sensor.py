"""DVLA sensor platform."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, cast, override

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

TAX_STATUS_OPTIONS = {
    "Not Taxed for on Road Use": "not_taxed_for_on_road_use",
    "SORN": "sorn",
    "Taxed": "taxed",
    "Untaxed": "untaxed",
}

MOT_STATUS_OPTIONS = {
    "No details held by DVLA": "no_details_held_by_dvla",
    "No results returned": "no_results_returned",
    "Not valid": "not_valid",
    "Valid": "valid",
}

ENUM_OPTIONS = {
    "taxStatus": TAX_STATUS_OPTIONS,
    "motStatus": MOT_STATUS_OPTIONS,
}


@dataclass(frozen=True, kw_only=True)
class DVLASensorEntityDescription(SensorEntityDescription):
    """Describe a DVLA sensor."""

    value_fn: Callable[[Mapping[str, Any]], StateType | date]


def value_fn(key: str) -> Callable[[Mapping[str, Any]], StateType]:
    """Return a value function for a raw DVLA field."""

    def _value_fn(data: Mapping[str, Any]) -> StateType:
        return cast(StateType, data.get(key))

    return _value_fn


def enum_value_fn(
    key: str,
    options: Mapping[str, str],
) -> Callable[[Mapping[str, Any]], StateType]:
    """Return a value function for a DVLA enum field."""

    def _value_fn(data: Mapping[str, Any]) -> StateType:
        value = data.get(key)

        if value is None:
            return None

        return options.get(str(value))

    return _value_fn


def int_value_fn(key: str) -> Callable[[Mapping[str, Any]], StateType]:
    """Return a value function for an integer DVLA field."""

    def _value_fn(data: Mapping[str, Any]) -> StateType:
        value = data.get(key)

        if value is None:
            return None

        try:
            return int(value)
        except TypeError, ValueError:
            return None

    return _value_fn


def date_value_fn(key: str) -> Callable[[Mapping[str, Any]], StateType | date]:
    """Return a value function for a date DVLA field."""

    def _value_fn(data: Mapping[str, Any]) -> StateType | date:
        value = data.get(key)

        if not isinstance(value, str):
            return None

        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    return _value_fn


SENSOR_DESCRIPTIONS: tuple[DVLASensorEntityDescription, ...] = (
    DVLASensorEntityDescription(
        key="taxStatus",
        translation_key="tax_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(TAX_STATUS_OPTIONS.values()),
        value_fn=enum_value_fn("taxStatus", TAX_STATUS_OPTIONS),
    ),
    DVLASensorEntityDescription(
        key="taxDueDate",
        translation_key="tax_due_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=date_value_fn("taxDueDate"),
    ),
    DVLASensorEntityDescription(
        key="artEndDate",
        translation_key="additional_rate_of_tax_end_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=date_value_fn("artEndDate"),
    ),
    DVLASensorEntityDescription(
        key="motStatus",
        translation_key="mot_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(MOT_STATUS_OPTIONS.values()),
        value_fn=enum_value_fn("motStatus", MOT_STATUS_OPTIONS),
    ),
    DVLASensorEntityDescription(
        key="engineCapacity",
        translation_key="engine_capacity",
        native_unit_of_measurement="cc",
        value_fn=int_value_fn("engineCapacity"),
    ),
    DVLASensorEntityDescription(
        key="yearOfManufacture",
        translation_key="year_of_manufacture",
        value_fn=int_value_fn("yearOfManufacture"),
    ),
    DVLASensorEntityDescription(
        key="co2Emissions",
        translation_key="co2_emissions",
        native_unit_of_measurement="g/km",
        value_fn=int_value_fn("co2Emissions"),
    ),
    DVLASensorEntityDescription(
        key="fuelType",
        translation_key="fuel_type",
        value_fn=value_fn("fuelType"),
    ),
    DVLASensorEntityDescription(
        key="colour",
        translation_key="color",
        value_fn=value_fn("colour"),
    ),
    DVLASensorEntityDescription(
        key="typeApproval",
        translation_key="type_approval",
        value_fn=value_fn("typeApproval"),
    ),
    DVLASensorEntityDescription(
        key="revenueWeight",
        translation_key="revenue_weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        value_fn=int_value_fn("revenueWeight"),
    ),
    DVLASensorEntityDescription(
        key="dateOfLastV5CIssued",
        translation_key="date_of_last_v5c_issued",
        device_class=SensorDeviceClass.DATE,
        value_fn=date_value_fn("dateOfLastV5CIssued"),
    ),
    DVLASensorEntityDescription(
        key="motExpiryDate",
        translation_key="mot_expiry_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=date_value_fn("motExpiryDate"),
    ),
    DVLASensorEntityDescription(
        key="wheelplan",
        translation_key="wheelplan",
        value_fn=value_fn("wheelplan"),
    ),
    DVLASensorEntityDescription(
        key="monthOfFirstRegistration",
        translation_key="month_of_first_registration",
        value_fn=value_fn("monthOfFirstRegistration"),
    ),
    DVLASensorEntityDescription(
        key="realDrivingEmissions",
        translation_key="real_driving_emissions",
        value_fn=int_value_fn("realDrivingEmissions"),
    ),
    DVLASensorEntityDescription(
        key="euroStatus",
        translation_key="euro_status",
        value_fn=value_fn("euroStatus"),
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

    entity_description: DVLASensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DVLACoordinator,
        reg_number: str,
        description: DVLASensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, reg_number)},
            manufacturer=coordinator.data.get("make"),
            name=reg_number,
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_unique_id = f"{reg_number}-{description.key}"
        self.entity_description = description
        self._state = description.value_fn(coordinator.data)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.entity_description.value_fn(self.coordinator.data)
        self.async_write_ha_state()

    @property
    @override
    def native_value(self) -> StateType | date:
        """Native value."""
        return self._state
