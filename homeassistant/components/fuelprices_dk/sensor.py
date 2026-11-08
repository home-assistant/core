"""Sensor platform for the Fuelprices.dk integration."""

from typing import TYPE_CHECKING, override

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify as util_slugify

from .const import CONF_COMPANY, CONF_STATION, DOMAIN, SUBENTRY_TYPE_STATION
from .coordinator import FuelPricesDKCoordinator

if TYPE_CHECKING:
    from . import FuelpricesDkConfigEntry

SENSORS = [
    SensorEntityDescription(
        key="price",
        name="Fuel Price",
        native_unit_of_measurement="DKK/L",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gas-station",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FuelpricesDkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform for Fuelprices.dk."""

    coordinator = entry.runtime_data
    added: set[tuple[str, str]] = set()

    @callback
    def async_add_sensors() -> None:
        """Add sensors for products returned for configured stations."""
        for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_STATION):
            station_id = subentry.data[CONF_STATION]["id"]
            if (station := coordinator.data.get(station_id)) is None:
                continue
            entities: list[FuelpricesDkSensor] = []
            for product_key in station.prices:
                key = (subentry.subentry_id, product_key)
                if key in added:
                    continue
                added.add(key)
                entities.extend(
                    FuelpricesDkSensor(
                        coordinator, subentry, station.name, product_key, sensor
                    )
                    for sensor in SENSORS
                )
            async_add_entities(entities, config_subentry_id=subentry.subentry_id)

    async_add_sensors()
    entry.async_on_unload(coordinator.async_add_listener(async_add_sensors))


class FuelpricesDkSensor(CoordinatorEntity[FuelPricesDKCoordinator], RestoreSensor):
    """Sensor for Fuelprices.dk."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FuelPricesDKCoordinator,
        subentry: ConfigSubentry,
        station_name: str,
        product_key: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._product_key = product_key
        self._station_id: int = subentry.data[CONF_STATION]["id"]
        self._station_name = station_name

        self._attr_name = product_key

        self._attr_unique_id = util_slugify(
            f"{self._station_id}_{self.entity_description.key}_{product_key}"
        )
        self._attr_config_subentry_id = subentry.subentry_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._station_id))},
            entry_type=DeviceEntryType.SERVICE,
            name=self._station_name,
            manufacturer=subentry.data[CONF_COMPANY],
            model=station_name,
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the entity is available."""
        return (
            super().available
            and (station := self.coordinator.data.get(self._station_id)) is not None
            and self._product_key in station.prices
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value of the sensor."""
        if (station := self.coordinator.data.get(self._station_id)) is None:
            return None
        if (price := station.prices.get(self._product_key)) is None:
            return None
        try:
            return float(price)
        except ValueError:
            return None
