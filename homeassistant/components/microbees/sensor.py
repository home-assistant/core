"""sensor integration microBees."""

from microBeesPy import Sensor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import MicroBeesUpdateCoordinator
from .entity import MicroBeesEntity

SENSOR_TYPES = {
    0: SensorEntityDescription(
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        key="absorption",
        suggested_display_precision=2,
    ),
    2: SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        key="temperature",
        suggested_display_precision=1,
    ),
    14: SensorEntityDescription(
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        key="carbon_dioxide",
        suggested_display_precision=1,
    ),
    16: SensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        key="humidity",
        suggested_display_precision=1,
    ),
    21: SensorEntityDescription(
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
        key="illuminance",
        suggested_display_precision=1,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id].coordinator

    async_add_entities(
        MBSensor(coordinator, desc, bee_id, sensor.id)
        for bee_id, bee in coordinator.data.bees.items()
        for sensor in bee.sensors
        if (desc := SENSOR_TYPES.get(sensor.device_type)) is not None
    )


class MBSensor(MicroBeesEntity, SensorEntity):
    """Representation of a microBees sensor."""

    def __init__(
        self,
        coordinator: MicroBeesUpdateCoordinator,
        entity_description: SensorEntityDescription,
        bee_id: int,
        sensor_id: int,
    ) -> None:
        """Initialize the microBees sensor."""
        super().__init__(coordinator, bee_id)
        self._attr_unique_id = f"{bee_id}_{sensor_id}"
        self.sensor_id = sensor_id
        self.entity_description = entity_description

    @property
    def name(self) -> str:
        """Name of the sensor."""
        return self.sensor.name

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.sensor.value

    @property
    def sensor(self) -> Sensor:
        """Return the sensor."""
        return self.coordinator.data.sensors[self.sensor_id]
