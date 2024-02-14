"""Sensor for openSenseMap."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_STATION_ID, DOMAIN, MANUFACTURER, SensorTypeId
from .coordinator import OpenSenseMapDataUpdateCoordinator, SensorDescr

DEVICE_CLASS_MAPPING = {
    SensorTypeId.PM25: SensorDeviceClass.PM25,
    SensorTypeId.PM10: SensorDeviceClass.PM10,
    SensorTypeId.TEMPERATURE: SensorDeviceClass.TEMPERATURE,
    SensorTypeId.HUMIDITY: SensorDeviceClass.HUMIDITY,
    SensorTypeId.PRESSURE: SensorDeviceClass.ATMOSPHERIC_PRESSURE,
    SensorTypeId.ILLUMINANCE: SensorDeviceClass.ILLUMINANCE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize the entries."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            OpenSenseMapSensor(coordinator, entry, sensor_descr)
            for sensor_descr in coordinator.sensors.values()
        ],
    )


class OpenSenseMapSensor(
    CoordinatorEntity[OpenSenseMapDataUpdateCoordinator], SensorEntity
):
    """OpenSenseMap Sensor."""

    _attr_attribution = (
        "Information provided by the openSenseMap (https://opensensemap.org/)"
    )
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: OpenSenseMapDataUpdateCoordinator,
        config_entry: ConfigEntry,
        sensor_descr: SensorDescr,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._station_id: str = config_entry.data[CONF_STATION_ID]
        self._sensor_id = sensor_descr.id
        self._descr = sensor_descr

    @property
    def unique_id(self) -> str:
        """Return a unique id for the sensor."""
        return self._sensor_id

    @property
    def name(self) -> str:
        """Return a sensor name."""
        return self._descr.title

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the sensors device class."""
        return DEVICE_CLASS_MAPPING[self._descr.sensor_type]

    @property
    def device_info(self) -> DeviceInfo:
        """Return the OpenSenseMap station as a device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name=self.coordinator.name,
            model=self.coordinator.name,
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def attribution(self) -> str:
        """Return link to source as attribution."""
        return f"https://opensensemap.org/explore/{self._station_id}"

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        return self.coordinator.data[self._sensor_id].value

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of the native value."""
        return self._descr.unit
