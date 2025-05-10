import logging
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)

from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)
from frisquet_connect.entities.core_entity import CoreEntity

_LOGGER = logging.getLogger(__name__)


class CoreThermometer(CoreEntity, SensorEntity):

    def __init__(
        self,
        coordinator: FrisquetConnectCoordinator,
        translation_key: str,
        suffix: str = None,
    ) -> None:
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{self.coordinator.data.site_id}_{translation_key}{suffix}"
        )
        self._attr_has_entity_name = True
        self._attr_translation_key = translation_key

        self._attr_native_unit_of_measurement = "°C"
        self._attr_unit_of_measurement = "°C"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
