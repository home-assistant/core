"""Support for DROP sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_COORDINATOR,
    CONF_DEVICE_TYPE,
    DEV_FILTER,
    DEV_HUB,
    DEV_LEAK_DETECTOR,
    DEV_PROTECTION_VALVE,
    DEV_PUMP_CONTROLLER,
    DEV_RO_FILTER,
    DEV_SOFTENER,
    DOMAIN,
)
from .coordinator import DROPDeviceDataUpdateCoordinator
from .entity import DROPEntity

_LOGGER = logging.getLogger(__name__)

FLOW_ICON = "mdi:shower-head"
GAUGE_ICON = "mdi:gauge"
TDS_ICON = "mdi:water-opacity"


@dataclass(kw_only=True)
class DROPSensorEntityDescription(SensorEntityDescription):
    """Describes DROP sensor entity."""

    value_fn: Callable[[DROPDeviceDataUpdateCoordinator], float | int | None]


SENSORS: dict[str, DROPSensorEntityDescription] = {
    "current_flow_rate": DROPSensorEntityDescription(
        key="current_flow_rate",
        icon="mdi:shower-head",
        native_unit_of_measurement="gpm",
        suggested_display_precision=1,
        value_fn=lambda device: device.current_flow_rate,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "peak_flow_rate": DROPSensorEntityDescription(
        key="peak_flow_rate",
        icon="mdi:shower-head",
        native_unit_of_measurement="gpm",
        suggested_display_precision=1,
        value_fn=lambda device: device.peak_flow_rate,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "water_used_today": DROPSensorEntityDescription(
        key="water_used_today",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=1,
        value_fn=lambda device: device.water_used_today,
    ),
    "average_water_used": DROPSensorEntityDescription(
        key="average_water_used",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=0,
        value_fn=lambda device: device.average_water_used,
    ),
    "capacity_remaining": DROPSensorEntityDescription(
        key="capacity_remaining",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=0,
        value_fn=lambda device: device.capacity_remaining,
    ),
    "current_system_pressure": DROPSensorEntityDescription(
        key="current_system_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement="psi",
        suggested_display_precision=1,
        value_fn=lambda device: device.current_system_pressure,
    ),
    "high_system_pressure": DROPSensorEntityDescription(
        key="high_system_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement="psi",
        suggested_display_precision=0,
        value_fn=lambda device: device.high_system_pressure,
    ),
    "low_system_pressure": DROPSensorEntityDescription(
        key="low_system_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement="psi",
        suggested_display_precision=0,
        value_fn=lambda device: device.low_system_pressure,
    ),
    "battery": DROPSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement="%",
        suggested_display_precision=0,
        value_fn=lambda device: device.battery,
    ),
    "temperature": DROPSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°F",
        suggested_display_precision=1,
        value_fn=lambda device: device.temperature,
    ),
    "inlet_tds": DROPSensorEntityDescription(
        key="inlet_tds",
        icon=TDS_ICON,
        native_unit_of_measurement="ppm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.inlet_tds,
    ),
    "outlet_tds": DROPSensorEntityDescription(
        key="outlet_tds",
        icon=TDS_ICON,
        native_unit_of_measurement="ppm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.outlet_tds,
    ),
    "cart1": DROPSensorEntityDescription(
        key="cart1",
        icon=GAUGE_ICON,
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.cart1,
    ),
    "cart2": DROPSensorEntityDescription(
        key="cart2",
        icon=GAUGE_ICON,
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.cart2,
    ),
    "cart3": DROPSensorEntityDescription(
        key="cart3",
        icon=GAUGE_ICON,
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.cart3,
    ),
}


class DROPSensor(DROPEntity, SensorEntity):
    """Representation of a DROP sensor."""

    entity_description: DROPSensorEntityDescription

    def __init__(self, device, entity_description) -> None:
        """Initialize the sensor."""
        super().__init__(entity_description.key, device)
        self.entity_description = entity_description
        self.device = device
        self._attr_translation_key = entity_description.key

    @property
    def native_value(self) -> float | int | None:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.device)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DROP sensors from config entry."""
    _LOGGER.debug(
        "Set up sensor for device type %s with entry_id is %s",
        config_entry.data[CONF_DEVICE_TYPE],
        config_entry.entry_id,
    )

    coordinator: DROPDeviceDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ][CONF_COORDINATOR]
    device_type: str = config_entry.data[CONF_DEVICE_TYPE]
    entities: list[SensorEntity] = []

    if device_type == DEV_HUB:
        entities.extend(
            DROPSensor(coordinator, SENSORS[sensor_type])
            for sensor_type in (
                "average_water_used",
                "battery",
                "current_flow_rate",
                "current_system_pressure",
                "high_system_pressure",
                "low_system_pressure",
                "peak_flow_rate",
                "water_used_today",
            )
        )
    elif device_type == DEV_SOFTENER:
        entities.extend(
            DROPSensor(coordinator, SENSORS[sensor_type])
            for sensor_type in (
                "battery",
                "capacity_remaining",
                "current_flow_rate",
                "current_system_pressure",
            )
        )
    elif device_type == DEV_FILTER:
        entities.extend(
            DROPSensor(coordinator, SENSORS[sensor_type])
            for sensor_type in (
                "battery",
                "current_flow_rate",
                "current_system_pressure",
            )
        )
    elif device_type == DEV_LEAK_DETECTOR:
        entities.extend(
            DROPSensor(coordinator, SENSORS[sensor_type])
            for sensor_type in (
                "battery",
                "temperature",
            )
        )
    elif device_type == DEV_PROTECTION_VALVE:
        entities.extend(
            DROPSensor(coordinator, SENSORS[sensor_type])
            for sensor_type in (
                "battery",
                "current_flow_rate",
                "current_system_pressure",
                "temperature",
            )
        )
    elif device_type == DEV_PUMP_CONTROLLER:
        entities.extend(
            DROPSensor(coordinator, SENSORS[sensor_type])
            for sensor_type in (
                "current_flow_rate",
                "current_system_pressure",
                "temperature",
            )
        )
    elif device_type == DEV_RO_FILTER:
        entities.extend(
            DROPSensor(coordinator, SENSORS[sensor_type])
            for sensor_type in (
                "cart1",
                "cart2",
                "cart3",
                "inlet_tds",
                "outlet_tds",
            )
        )

    async_add_entities(entities)
