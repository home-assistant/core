"""Support for Flick Electric Pricing data."""

from datetime import timedelta
from decimal import Decimal
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CURRENCY_CENT, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_COMPONENTS, ATTR_END_AT, ATTR_START_AT
from .coordinator import FlickConfigEntry, FlickElectricDataCoordinator

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlickConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Flick Sensor Setup."""
    coordinator = entry.runtime_data

    async_add_entities([FlickPricingSensor(coordinator)])


class FlickPricingSensor(CoordinatorEntity[FlickElectricDataCoordinator], SensorEntity):
    """Entity object for Flick Electric sensor."""

    _attr_attribution = "Data provided by Flick Electric"
    _attr_native_unit_of_measurement = f"{CURRENCY_CENT}/{UnitOfEnergy.KILO_WATT_HOUR}"
    _attr_has_entity_name = True
    _attr_translation_key = "power_price"

    def __init__(self, coordinator: FlickElectricDataCoordinator) -> None:
        """Entity object for Flick Electric sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.supply_node_ref}_pricing"

    @property
    def native_value(self) -> Decimal:
        """Return the state of the sensor."""
        # The API should return a unit price with quantity of 1.0 when no start/end time is provided
        if self.coordinator.data.quantity != 1:
            _LOGGER.warning(
                "Unexpected quantity for unit price: %s", self.coordinator.data
            )
        return self.coordinator.data.cost * 100

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        components: dict[str, float] = {}

        for component in self.coordinator.data.components:
            if component.charge_setter not in ATTR_COMPONENTS:
                _LOGGER.warning("Found unknown component: %s", component.charge_setter)
                continue

            components[component.charge_setter] = float(component.value * 100)

        return {
            ATTR_START_AT: self.coordinator.data.start_at,
            ATTR_END_AT: self.coordinator.data.end_at,
            **components,
        }
