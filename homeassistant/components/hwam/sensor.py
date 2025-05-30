"""The HWAM Smart Control sensors."""

from pystove import (
    DATA_OXYGEN_LEVEL,
    DATA_PHASE,
    DATA_ROOM_TEMPERATURE,
    DATA_STOVE_TEMPERATURE,
    DATA_VALVE1_POSITION,
    DATA_VALVE2_POSITION,
    DATA_VALVE3_POSITION,
    PHASE,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StoveDataUpdateCoordinator

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=DATA_PHASE,
        translation_key=DATA_PHASE,
        device_class=SensorDeviceClass.ENUM,
        options=PHASE,
        icon="mdi:state-machine",
    ),
    SensorEntityDescription(
        key=DATA_STOVE_TEMPERATURE,
        translation_key=DATA_STOVE_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:fire",
    ),
    SensorEntityDescription(
        key=DATA_ROOM_TEMPERATURE,
        translation_key=DATA_ROOM_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key=DATA_OXYGEN_LEVEL,
        translation_key=DATA_OXYGEN_LEVEL,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent-outline",
    ),
    SensorEntityDescription(
        key=DATA_VALVE1_POSITION,
        translation_key=DATA_VALVE1_POSITION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:valve",
    ),
    SensorEntityDescription(
        key=DATA_VALVE2_POSITION,
        translation_key=DATA_VALVE2_POSITION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:valve",
    ),
    SensorEntityDescription(
        key=DATA_VALVE3_POSITION,
        translation_key=DATA_VALVE3_POSITION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:valve",
    ),
)


class StoveSensorEntity(CoordinatorEntity[StoveDataUpdateCoordinator], SensorEntity):
    """A generic sensor class."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: StoveDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._attr_device_info = coordinator.device_info()
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        if self.device_class == SensorDeviceClass.ENUM:
            return str(self._coordinator.data[self.entity_description.key])

        return self._coordinator.data[self.entity_description.key]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure the thermostat."""
    coordinator: StoveDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        StoveSensorEntity(coordinator, description) for description in SENSORS
    )
