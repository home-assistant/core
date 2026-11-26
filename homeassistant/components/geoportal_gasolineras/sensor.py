"""Fuel price sensors for Spain fuel prices (Geoportal Gasolineras)."""

from typing import override

from aioprecioscarburantes import FuelType, Station

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CURRENCY_EURO, UnitOfMass, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONF_STATION_ID,
    CONFIGURATION_URL,
    DOMAIN,
    SUBENTRY_TYPE_STATION,
)
from .coordinator import (
    GeoportalGasolinerasConfigEntry,
    GeoportalGasolinerasCoordinator,
)
from .names import brand_name, clean_address

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

# Fuels sold by weight; the rest are sold by volume
FUELS_PER_KG = {
    FuelType.AMMONIA,
    FuelType.COMPRESSED_BIOGAS,
    FuelType.LIQUEFIED_BIOGAS,
    FuelType.COMPRESSED_NATURAL_GAS,
    FuelType.LIQUEFIED_NATURAL_GAS,
    FuelType.HYDROGEN,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GeoportalGasolinerasConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a price sensor for each fuel each station sells."""
    coordinator = entry.runtime_data
    added: set[tuple[str, FuelType]] = set()

    @callback
    def async_add_sensors() -> None:
        """Add sensors for stations and fuels not seen before."""
        for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_STATION):
            station_id: str = subentry.data[CONF_STATION_ID]
            if (station := coordinator.data.get(station_id)) is None:
                continue
            new = [fuel for fuel in station.prices if (station_id, fuel) not in added]
            added.update((station_id, fuel) for fuel in new)
            if new:
                async_add_entities(
                    (FuelPriceSensor(coordinator, subentry, fuel) for fuel in new),
                    config_subentry_id=subentry.subentry_id,
                )

    async_add_sensors()
    entry.async_on_unload(coordinator.async_add_listener(async_add_sensors))


class FuelPriceSensor(CoordinatorEntity[GeoportalGasolinerasCoordinator], SensorEntity):
    """Price of one fuel at a station."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: GeoportalGasolinerasCoordinator,
        subentry: ConfigSubentry,
        fuel: FuelType,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._fuel = fuel
        self._station_id: str = subentry.data[CONF_STATION_ID]
        station = coordinator.data[self._station_id]
        self._attr_translation_key = fuel.name.lower()
        self._attr_unique_id = f"{self._station_id}_{fuel.name.lower()}"
        unit = UnitOfMass.KILOGRAMS if fuel in FUELS_PER_KG else UnitOfVolume.LITERS
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/{unit}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._station_id)},
            name=subentry.title,
            manufacturer=brand_name(station.brand),
            model=clean_address(station.address),
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=CONFIGURATION_URL,
        )

    @property
    def _station(self) -> Station | None:
        return self.coordinator.data.get(self._station_id)

    @property
    @override
    def available(self) -> bool:
        """Return if the station was fetched and still sells this fuel."""
        station = self._station
        return (
            super().available and station is not None and self._fuel in station.prices
        )

    @property
    @override
    def native_value(self) -> float:
        """Return the price; only called while available."""
        return self.coordinator.data[self._station_id].prices[self._fuel]
