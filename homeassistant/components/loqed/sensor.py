"""Creates LOQED sensors."""
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LoqedDataCoordinator, StatusMessage
from .entity import LoqedEntity

SENSORS: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key="ble_strength",
        name="Bluetooth signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="battery_percentage",
        name="Battery level",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Loqed lock platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(LoqedSensor(coordinator, sensor, entry) for sensor in SENSORS)


class LoqedSensor(LoqedEntity, SensorEntity):
    """Representation of Sensor state."""

    def __init__(
        self,
        coordinator: LoqedDataCoordinator,
        description: SensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.entry = entry

        self._attr_unique_id = f"{entry.unique_id}_{description.key}"

    @property
    def data(self) -> StatusMessage:
        """Return data object from DataUpdateCoordinator."""
        return self.coordinator.lock

    @property
    def native_value(self) -> int:
        """Return state of sensor."""
        return getattr(self.data, self.entity_description.key)
