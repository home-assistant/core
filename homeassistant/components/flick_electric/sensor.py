"""Support for Flick Electric Pricing data."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CURRENCY_CENT, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_END_AT, ATTR_START_AT, DOMAIN
from .coordinator import FlickConfigEntry, FlickElectricDataCoordinator

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlickConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Flick Sensor Setup."""
    coordinator = entry.runtime_data

    async_add_entities([FlickPricingSensor(coordinator)], True)


class FlickPricingSensor(CoordinatorEntity[FlickElectricDataCoordinator], SensorEntity):
    """Entity object for Flick Electric sensor."""

    _attr_attribution = "Data provided by Flick Electric"
    _attr_native_unit_of_measurement = f"{CURRENCY_CENT}/{UnitOfEnergy.KILO_WATT_HOUR}"
    _attr_has_entity_name = True
    _attr_translation_key = "power_price"
    _attributes: dict[str, Any] = {}

    def __init__(self, coordinator: FlickElectricDataCoordinator) -> None:
        """Entity object for Flick Electric sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{DOMAIN}_{coordinator.supply_node_ref}_pricing"

    @property
    def native_value(self) -> Decimal:
        """Return the state of the sensor."""
        return self.coordinator.data.price

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        return {
            ATTR_START_AT: self.coordinator.data.start_at,
            ATTR_END_AT: self.coordinator.data.end_at,
            # TODO: Components
        }
