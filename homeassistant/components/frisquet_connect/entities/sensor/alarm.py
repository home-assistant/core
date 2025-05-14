from homeassistant.components.sensor import SensorEntity, SensorDeviceClass


from frisquet_connect.const import (
    SENSOR_ALARM_TRANSLATIONS_KEY,
    AlarmType,
)
from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)
from frisquet_connect.entities.core_entity import CoreEntity


class AlarmEntity(CoreEntity, SensorEntity):

    def __init__(self, coordinator: FrisquetConnectCoordinator) -> None:
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{self.coordinator.data.site_id}_{SENSOR_ALARM_TRANSLATIONS_KEY}"
        )
        self._attr_translation_key = SENSOR_ALARM_TRANSLATIONS_KEY
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = [alarm_type for alarm_type in AlarmType]

    def update(self) -> None:
        """Handle updated data from the coordinator."""

        value: str = AlarmType.NO_ALARM
        for alarm in self.coordinator.data.alarms:
            # TODO: Handle multiple alarms
            value = alarm.alarme_type
            break

        self._attr_native_value = value
