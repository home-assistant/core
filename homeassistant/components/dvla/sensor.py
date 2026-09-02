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
from homeassistant.core import HomeAssistant
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


def raw_value(value: Any) -> StateType:
    """Return a raw DVLA value."""
    return cast(StateType, value)


def enum_value_fn(options: Mapping[str, str]) -> Callable[[Any], StateType]:
    """Return a value function for a DVLA enum field."""

    def _value_fn(value: Any) -> StateType:
        if value is None:
            return None

        return options.get(str(value))

    return _value_fn


def int_value(value: Any) -> StateType:
    """Return an integer DVLA value."""

    if value is None:
        return None

    try:
        return int(value)
    except TypeError, ValueError:
        return None


def date_value(value: Any) -> StateType | date:
    """Return a date DVLA value."""

    if not isinstance(value, str):
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@dataclass(frozen=True, kw_only=True)
class DVLASensorEntityDescription(SensorEntityDescription):
    """Describe a DVLA sensor."""

    value_fn: Callable[[Any], StateType | date] = raw_value


SENSOR_DESCRIPTIONS: tuple[DVLASensorEntityDescription, ...] = (
    DVLASensorEntityDescription(
        key="taxStatus",
        translation_key="tax_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(TAX_STATUS_OPTIONS.values()),
        value_fn=enum_value_fn(TAX_STATUS_OPTIONS),
    ),
    DVLASensorEntityDescription(
        key="taxDueDate",
        translation_key="tax_due_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=date_value,
    ),
    DVLASensorEntityDescription(
        key="artEndDate",
        translation_key="additional_rate_of_tax_end_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=date_value,
    ),
    DVLASensorEntityDescription(
        key="motStatus",
        translation_key="mot_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(MOT_STATUS_OPTIONS.values()),
        value_fn=enum_value_fn(MOT_STATUS_OPTIONS),
    ),
    DVLASensorEntityDescription(
        key="engineCapacity",
        translation_key="engine_capacity",
        native_unit_of_measurement="cc",
        value_fn=int_value,
    ),
    DVLASensorEntityDescription(
        key="yearOfManufacture",
        translation_key="year_of_manufacture",
        value_fn=int_value,
    ),
    DVLASensorEntityDescription(
        key="co2Emissions",
        translation_key="co2_emissions",
        native_unit_of_measurement="g/km",
        value_fn=int_value,
    ),
    DVLASensorEntityDescription(
        key="fuelType",
        translation_key="fuel_type",
    ),
    DVLASensorEntityDescription(
        key="colour",
        translation_key="color",
    ),
    DVLASensorEntityDescription(
        key="typeApproval",
        translation_key="type_approval",
    ),
    DVLASensorEntityDescription(
        key="revenueWeight",
        translation_key="revenue_weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        value_fn=int_value,
    ),
    DVLASensorEntityDescription(
        key="dateOfLastV5CIssued",
        translation_key="date_of_last_v5c_issued",
        device_class=SensorDeviceClass.DATE,
        value_fn=date_value,
    ),
    DVLASensorEntityDescription(
        key="motExpiryDate",
        translation_key="mot_expiry_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=date_value,
    ),
    DVLASensorEntityDescription(
        key="wheelplan",
        translation_key="wheelplan",
    ),
    DVLASensorEntityDescription(
        key="monthOfFirstRegistration",
        translation_key="month_of_first_registration",
    ),
    DVLASensorEntityDescription(
        key="realDrivingEmissions",
        translation_key="real_driving_emissions",
    ),
    DVLASensorEntityDescription(
        key="euroStatus",
        translation_key="euro_status",
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

    @property
    @override
    def native_value(self) -> StateType | date:
        """Native value."""
        return self.entity_description.value_fn(
            self.coordinator.data.get(self.entity_description.key)
        )
