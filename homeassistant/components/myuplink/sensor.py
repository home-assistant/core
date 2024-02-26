"""Sensor for myUplink."""

from myuplink.models import DevicePoint

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfFrequency,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import MyUplinkDataCoordinator
from .const import DOMAIN
from .entity import MyUplinkEntity

DEVICE_POINT_DESCRIPTIONS = {
    "°C": SensorEntityDescription(
        key="celsius",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "A": SensorEntityDescription(
        key="ampere",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    "Hz": SensorEntityDescription(
        key="hertz",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up myUplink sensor."""
    entities: list[SensorEntity] = []
    coordinator: MyUplinkDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Setup device point sensors
    for device_id, point_data in coordinator.data.points.items():
        for point_id, device_point in point_data.items():
            entities.append(
                MyUplinkDevicePointSensor(
                    coordinator=coordinator,
                    device_id=device_id,
                    device_point=device_point,
                    entity_description=DEVICE_POINT_DESCRIPTIONS.get(
                        device_point.parameter_unit
                    ),
                    unique_id_suffix=point_id,
                )
            )

    async_add_entities(entities)


class MyUplinkDevicePointSensor(MyUplinkEntity, SensorEntity):
    """Representation of a myUplink device point sensor."""

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        device_id: str,
        device_point: DevicePoint,
        entity_description: SensorEntityDescription | None,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            device_id=device_id,
            unique_id_suffix=unique_id_suffix,
        )

        # Internal properties
        self.point_id = device_point.parameter_id
        self._attr_name = device_point.parameter_name.replace("\u002d", "")

        if entity_description is not None:
            self.entity_description = entity_description
        else:
            self._attr_native_unit_of_measurement = device_point.parameter_unit

    @property
    def native_value(self) -> StateType:
        """Sensor state value."""
        device_point = self.coordinator.data.points[self.device_id][self.point_id]
        return device_point.value  # type: ignore[no-any-return]
