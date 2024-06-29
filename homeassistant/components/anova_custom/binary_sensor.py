"""The Anova integration Binary sensor."""

from anova_wifi import AnovaPrecisionCookerBinarySensor

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AnovaCoordinator
from .entity import AnovaEntity

SENSOR_DESCRIPTIONS: list[BinarySensorEntityDescription] = [
    BinarySensorEntityDescription(
        key=AnovaPrecisionCookerBinarySensor.COOKING, name="Cooking"
    ),
    BinarySensorEntityDescription(
        key=AnovaPrecisionCookerBinarySensor.PREHEATING, name="Preheating"
    ),
    BinarySensorEntityDescription(
        key=AnovaPrecisionCookerBinarySensor.MAINTAINING, name="Maintaining"
    ),
    BinarySensorEntityDescription(
        key=AnovaPrecisionCookerBinarySensor.DEVICE_SAFE, name="Device is safe"
    ),
    BinarySensorEntityDescription(
        key=AnovaPrecisionCookerBinarySensor.WATER_LEAK, name="Water leak"
    ),
    BinarySensorEntityDescription(
        key=AnovaPrecisionCookerBinarySensor.WATER_LEVEL_CRITICAL,
        name="Water level critical",
    ),
    BinarySensorEntityDescription(
        key=AnovaPrecisionCookerBinarySensor.WATER_TEMP_TOO_HIGH,
        name="Water temperature too high",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anova device."""
    coordinators = hass.data[DOMAIN][entry.entry_id]
    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()
        sensors = [
            AnovaPrecissionCookerBinarySensor(coordinator, description)
            for description in SENSOR_DESCRIPTIONS
            if coordinator.data["binary_sensors"][description.key] is not None
        ]
        async_add_entities(sensors)


class AnovaPrecissionCookerBinarySensor(AnovaEntity, BinarySensorEntity):
    """Representation of an Anova Precision Cooker binary sensor."""

    def __init__(
        self, coordinator: AnovaCoordinator, description: BinarySensorEntityDescription
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._sensor_update_key = description.key
        self._attr_unique_id = (
            f"{coordinator.device_unique_id}_{description.key}".lower()
        )

    @property
    def is_on(self) -> bool:
        """Return if motion is detected."""
        return self.coordinator.data["binary_sensors"][self._sensor_update_key]
