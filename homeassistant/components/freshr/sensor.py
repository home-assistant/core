"""Sensor platform for the Fresh-r integration."""

from __future__ import annotations

from pyfreshr.models import DeviceCurrent

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    StateType,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreshrConfigEntry, FreshrCoordinator

PARALLEL_UPDATES = 0

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="t1",
        name="Inside temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="t2",
        name="Outside temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="co2",
        name="Inside CO2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement="ppm",
    ),
    SensorEntityDescription(
        key="hum",
        name="Inside humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="flow",
        name="Flow",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    ),
    SensorEntityDescription(
        key="dp",
        name="Dew point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FreshrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fresh-r sensors from a config entry."""
    coordinator = config_entry.runtime_data
    entities: list[FreshrSensor] = []

    for device_id in coordinator.data:
        device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_id,
            manufacturer="Fresh-r",
        )
        entities.extend(
            FreshrSensor(coordinator, device_id, description, device_info)
            for description in SENSOR_TYPES
        )

    async_add_entities(entities)


class FreshrSensor(CoordinatorEntity[FreshrCoordinator], SensorEntity):
    """Representation of a Fresh-r sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: FreshrCoordinator,
        device_id: str,
        description: SensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_id
        self._attr_device_info = device_info
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_translation_key = description.key

    @property
    def native_value(self) -> StateType:
        """Return the value from coordinator data."""
        device_current: DeviceCurrent | None = self.coordinator.data.get(
            self._device_id
        )
        if device_current is None:
            return None

        value = getattr(device_current, self.entity_description.key, None)
        if value is None:
            return None

        if self.entity_description.key in ("t1", "t2", "dp"):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        if self.entity_description.key == "flow":
            # Already converted to m³/h by the library (convert_flow=True)
            return value
        if self.entity_description.key in ("co2", "hum"):
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
        return value
