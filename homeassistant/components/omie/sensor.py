"""Sensor for the OMIE - Spain and Portugal electricity prices integration."""

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OMIEConfigEntry, OMIECoordinator
from .util import current_hour_CET, pick_series_cet

PARALLEL_UPDATES = 0

_ATTRIBUTION = "Data provided by OMIE.es"


@dataclass(frozen=True)
class OMIEPriceEntityDescription(SensorEntityDescription):
    """Describes OMIE price entities."""

    def __init__(self, key: str) -> None:
        """Construct an OMIEPriceEntityDescription that reports prices in €/kWh."""
        super().__init__(
            key=key,
            has_entity_name=True,
            translation_key=key,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
            icon="mdi:currency-eur",
            suggested_display_precision=4,
        )


class OMIEPriceSensor(CoordinatorEntity[OMIECoordinator], SensorEntity):
    """OMIE price sensor."""

    _attr_should_poll = False
    _attr_attribution = _ATTRIBUTION

    def __init__(
        self,
        coordinator: OMIECoordinator,
        device_info: DeviceInfo,
        pyomie_series_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = OMIEPriceEntityDescription(key=pyomie_series_name)
        self._attr_device_info = device_info
        self._attr_unique_id = pyomie_series_name
        self._pyomie_series_name = pyomie_series_name

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update this sensor's state from the coordinator results."""
        value = self._get_current_hour_value()
        self._attr_available = value is not None
        self._attr_native_value = value if self._attr_available else None
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._attr_available

    def _get_current_hour_value(self) -> float | None:
        """Get current hour's price value from coordinator data."""
        current_hour_cet = current_hour_CET()
        current_date_cet = current_hour_cet.date()

        pyomie_results = self.coordinator.data.get(current_date_cet)
        pyomie_hours = pick_series_cet(pyomie_results, self._pyomie_series_name)

        # Convert to €/kWh
        value_mwh = pyomie_hours.get(current_hour_cet)
        return value_mwh / 1000 if value_mwh is not None else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OMIEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OMIE from its config entry."""
    coordinator = entry.runtime_data

    device_info = DeviceInfo(
        configuration_url="https://www.omie.es/en/market-results",
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, entry.entry_id)},
        name="OMIE",
    )

    sensors = [
        OMIEPriceSensor(coordinator, device_info, pyomie_series_name="spot_price_pt"),
        OMIEPriceSensor(coordinator, device_info, pyomie_series_name="spot_price_es"),
    ]

    async_add_entities(sensors)
