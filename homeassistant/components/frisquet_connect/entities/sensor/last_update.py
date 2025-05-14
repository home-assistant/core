import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass


from frisquet_connect.const import (
    SENSOR_BOILER_LAST_UPDATE_TRANSLATIONS_KEY,
)
from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)
from frisquet_connect.entities.core_entity import CoreEntity

_LOGGER = logging.getLogger(__name__)


class LastUpdateEntity(CoreEntity, SensorEntity):

    def __init__(self, coordinator: FrisquetConnectCoordinator) -> None:
        super().__init__(coordinator)

        self._attr_unique_id = f"{self.coordinator.data.site_id}_{SENSOR_BOILER_LAST_UPDATE_TRANSLATIONS_KEY}"
        self._attr_translation_key = SENSOR_BOILER_LAST_UPDATE_TRANSLATIONS_KEY
        self._attr_device_class = SensorDeviceClass.DATE

    def update(self) -> None:
        self._attr_native_value = self.coordinator.data.last_updated
