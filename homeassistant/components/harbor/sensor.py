"""Sensor entities for Harbor."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfDataRate, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import HarborConfigEntry, HarborCoordinator
from .entity import HarborEntity

PARALLEL_UPDATES = 0

CAMERA_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="num_viewers",
        translation_key="num_viewers",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="bitrate",
        translation_key="bitrate",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="wifi_strength",
        translation_key="wifi_strength",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="stream_quality",
        translation_key="stream_quality",
        device_class=SensorDeviceClass.ENUM,
        options=["excellent", "fair", "good", "poor"],
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HarborConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Harbor sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        HarborSensor(coordinator, description) for description in CAMERA_SENSORS
    )


class HarborSensor(HarborEntity, SensorEntity):
    """A Harbor sensor entity."""

    def __init__(
        self,
        coordinator: HarborCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Harbor sensor."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    @override
    @property
    def native_value(self) -> StateType:
        """Return the current sensor value."""
        value = self.coordinator.data.values.get(self.entity_description.key)
        if (
            self.entity_description.device_class == SensorDeviceClass.ENUM
            and value == "unknown"
        ):
            # The library falls back to the literal string "unknown" for any
            # enum value it doesn't recognize; surface that as no value
            # rather than a bogus member of the options list.
            return None
        return value
