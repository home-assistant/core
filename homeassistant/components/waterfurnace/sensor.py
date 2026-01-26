"""Support for Waterfurnace."""

from __future__ import annotations

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import DOMAIN
from .coordinator import WaterFurnaceCoordinator

SENSORS = [
    SensorEntityDescription(name="Furnace Mode", key="mode", icon="mdi:gauge"),
    SensorEntityDescription(
        name="Total Power",
        key="totalunitpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        name="Active Setpoint",
        key="tstatactivesetpoint",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        name="Leaving Air",
        key="leavingairtemp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        name="Room Temp",
        key="tstatroomtemp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        name="Loop Temp",
        key="enteringwatertemp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        name="Humidity Set Point",
        key="tstathumidsetpoint",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        name="Humidity",
        key="tstatrelativehumidity",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        name="Compressor Power",
        key="compressorpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        name="Fan Power",
        key="fanpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        name="Aux Power",
        key="auxpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        name="Loop Pump Power",
        key="looppumppower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        name="Compressor Speed", key="actualcompressorspeed", icon="mdi:speedometer"
    ),
    SensorEntityDescription(
        name="Fan Speed", key="airflowcurrentspeed", icon="mdi:fan"
    ),
]


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Waterfurnace sensor."""
    if discovery_info is None:
        return

    coordinator = hass.data[DOMAIN]

    add_entities(
        WaterFurnaceSensor(coordinator, description) for description in SENSORS
    )


class WaterFurnaceSensor(CoordinatorEntity[WaterFurnaceCoordinator], SensorEntity):
    """Implementing the Waterfurnace sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self, coordinator: WaterFurnaceCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        # This ensures that the sensors are isolated per waterfurnace unit
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"wf_{slugify(coordinator.unit)}_{slugify(description.key)}"
        )

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        if self.coordinator.data is None:
            return None
        return getattr(self.coordinator.data, self.entity_description.key, None)
