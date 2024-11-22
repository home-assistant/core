"""BinarySensor integration microBees."""

from microBeesPy import Sensor

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MicroBeesUpdateCoordinator
from .entity import MicroBeesEntity

BINARYSENSOR_TYPES = {
    12: BinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.MOTION,
        key="motion_sensor",
    ),
    13: BinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.DOOR,
        key="door_sensor",
    ),
    19: BinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.MOISTURE,
        key="moisture_sensor",
    ),
    20: BinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.SMOKE,
        key="smoke_sensor",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the microBees binary sensor platform."""
    coordinator: MicroBeesUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ].coordinator
    async_add_entities(
        MBBinarySensor(coordinator, entity_description, bee_id, binary_sensor.id)
        for bee_id, bee in coordinator.data.bees.items()
        for binary_sensor in bee.sensors
        if (entity_description := BINARYSENSOR_TYPES.get(binary_sensor.device_type))
        is not None
    )


class MBBinarySensor(MicroBeesEntity, BinarySensorEntity):
    """Representation of a microBees BinarySensor."""

    def __init__(
        self,
        coordinator: MicroBeesUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
        bee_id: int,
        sensor_id: int,
    ) -> None:
        """Initialize the microBees BinarySensor."""
        super().__init__(coordinator, bee_id)
        self._attr_unique_id = f"{bee_id}_{sensor_id}"
        self.sensor_id = sensor_id
        self.entity_description = entity_description

    @property
    def name(self) -> str:
        """Name of the BinarySensor."""
        return self.sensor.name

    @property
    def is_on(self) -> bool:
        """Return the state of the BinarySensor."""
        return self.sensor.value

    @property
    def sensor(self) -> Sensor:
        """Return the BinarySensor."""
        return self.coordinator.data.sensors[self.sensor_id]
