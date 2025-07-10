"""Support for the CO2signal platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aioelectricitymaps.models import CarbonIntensityResponse

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import CO2SignalConfigEntry, CO2SignalCoordinator


@dataclass(frozen=True, kw_only=True)
class CO2SensorEntityDescription(SensorEntityDescription):
    """Provide a description of a CO2 sensor."""

    # For backwards compat, allow description to override unique ID key to use
    unique_id: str | None = None
    unit_of_measurement_fn: Callable[[CarbonIntensityResponse], str | None] | None = (
        None
    )
    value_fn: Callable[[CarbonIntensityResponse], float | None]


SENSORS = (
    CO2SensorEntityDescription(
        key="carbonIntensity",
        translation_key="carbon_intensity",
        unique_id="co2intensity",
        value_fn=lambda response: response.data.carbon_intensity,
        unit_of_measurement_fn=lambda response: response.units.carbon_intensity,
    ),
    CO2SensorEntityDescription(
        key="fossilFuelPercentage",
        translation_key="fossil_fuel_percentage",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda response: response.data.fossil_fuel_percentage,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CO2SignalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the CO2signal sensor."""
    coordinator = entry.runtime_data
    async_add_entities(
        [CO2Sensor(coordinator, description) for description in SENSORS], False
    )


class CO2Sensor(CoordinatorEntity[CO2SignalCoordinator], SensorEntity):
    """Implementation of the CO2Signal sensor."""

    entity_description: CO2SensorEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: CO2SignalCoordinator, description: CO2SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_extra_state_attributes = {
            "country_code": coordinator.data.country_code,
        }
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.electricitymaps.com/",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.entry_id)},
            manufacturer="Electricity Maps",
            name="Electricity Maps",
        )
        self._attr_unique_id = (
            f"{coordinator.entry_id}_{description.unique_id or description.key}"
        )

    @property
    def native_value(self) -> float | None:
        """Return sensor state."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if self.entity_description.unit_of_measurement_fn:
            return self.entity_description.unit_of_measurement_fn(self.coordinator.data)

        return self.entity_description.native_unit_of_measurement
