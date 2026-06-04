"""Support for Rabbit Air sensors."""

from rabbitair import Quality

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import RabbitAirConfigEntry, RabbitAirDataUpdateCoordinator
from .entity import RabbitAirBaseEntity


def _quality_value(quality: Quality | None) -> StateType:
    """Return the air quality state."""
    return None if quality is None else quality.name.lower()


AIR_QUALITY_OPTIONS = [quality.name.lower() for quality in Quality]

AIR_QUALITY_DESCRIPTION = SensorEntityDescription(
    key="air_quality",
    translation_key="air_quality",
    device_class=SensorDeviceClass.ENUM,
    options=AIR_QUALITY_OPTIONS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RabbitAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Rabbit Air sensors."""
    if entry.runtime_data.data.quality is not None:
        async_add_entities([RabbitAirAirQualitySensor(entry.runtime_data, entry)])


class RabbitAirAirQualitySensor(RabbitAirBaseEntity, SensorEntity):
    """Rabbit Air air quality sensor."""

    entity_description = AIR_QUALITY_DESCRIPTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RabbitAirDataUpdateCoordinator,
        entry: RabbitAirConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, entry)
        del self._attr_name
        self._attr_unique_id = f"{entry.unique_id}_{self.entity_description.key}"
        self._attr_native_value = _quality_value(coordinator.data.quality)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = _quality_value(self.coordinator.data.quality)
        super()._handle_coordinator_update()
