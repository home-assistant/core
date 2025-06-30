from frisquet_connect.const import (
    SENSOR_INSIDE_THERMOMETER_TRANSLATIONS_KEY,
)

from frisquet_connect.domains.site.zone import Zone
from frisquet_connect.entities.sensor.core_thermometer import (
    CoreThermometer,
)
from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)


class InsideThermometerEntity(CoreThermometer):
    _zone_label_id: str

    def __init__(
        self, coordinator: FrisquetConnectCoordinator, zone_label_id: str
    ) -> None:
        super().__init__(
            coordinator, SENSOR_INSIDE_THERMOMETER_TRANSLATIONS_KEY, zone_label_id
        )

        self._zone_label_id = zone_label_id
        self._attr_translation_placeholders = {"zone_name": self.zone.name}

    @property
    def zone(self) -> Zone:
        return self.coordinator.data.get_zone_by_label_id(self._zone_label_id)

    def update(self) -> None:
        self._attr_native_value = self.zone.detail.current_temperature
