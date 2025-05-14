import logging
from datetime import datetime
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy


from frisquet_connect.const import ConsumptionType
from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)
from frisquet_connect.entities.core_entity import CoreEntity


_LOGGER = logging.getLogger(__name__)


class CoreConsumption(CoreEntity, SensorEntity):

    _consumption_type: ConsumptionType

    def __init__(
        self, coordinator: FrisquetConnectCoordinator, translation_key: str
    ) -> None:
        super().__init__(coordinator)

        self._attr_unique_id = f"{self.coordinator.data.site_id}_{translation_key}"
        self._attr_translation_key = translation_key

        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_unit_of_measurement = "kWh"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    def update(self) -> None:
        if not self._consumption_type:
            _LOGGER.error("Consumption type not set")
            return

        current_year = datetime.now().year
        native_value = 0
        consumptions = self.coordinator.data.get_consumptions_by_type(
            self._consumption_type
        )
        if consumptions:
            for consumption_month in consumptions.consumption_months:
                if consumption_month.year == current_year:
                    native_value += consumption_month.value
        self._attr_native_value = native_value
