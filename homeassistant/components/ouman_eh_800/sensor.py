"""Sensor platform for the Ouman EH-800 integration."""

from ouman_eh_800_api import NumberOumanEndpoint, OumanEndpoint, OumanUnit

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PRIMARY_SENSOR_ENDPOINTS
from .coordinator import OumanEh800ConfigEntry, OumanEh800Coordinator
from .entity import OumanEh800Entity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OumanEh800ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ouman EH-800 sensors based on a config entry."""
    coordinator = entry.runtime_data

    entities = (
        OumanEh800SensorEntity(coordinator, endpoint)
        for endpoint in coordinator.sensor_endpoints
    )

    async_add_entities(entities)


class OumanEh800SensorEntity(OumanEh800Entity, SensorEntity):
    """Ouman EH-800 sensor entity."""

    def __init__(
        self, coordinator: OumanEh800Coordinator, endpoint: OumanEndpoint
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, endpoint)

        if endpoint not in PRIMARY_SENSOR_ENDPOINTS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        is_numerical = isinstance(endpoint, NumberOumanEndpoint)

        self._attr_native_unit_of_measurement = endpoint.unit
        self._attr_state_class = SensorStateClass.MEASUREMENT if is_numerical else None
        self._attr_suggested_display_precision = 1 if is_numerical else None

        self._attr_device_class = None
        if endpoint.unit == OumanUnit.CELSIUS:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE

    @property
    def native_value(self) -> float | str:
        """Return the current sensor value."""
        value = self.coordinator.data[self._endpoint]
        assert isinstance(value, float | str)
        return value
