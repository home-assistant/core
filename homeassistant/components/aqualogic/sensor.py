"""Support for AquaLogic sensors."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AquaLogicConfigEntry, AquaLogicProcessor
from .const import UPDATE_TOPIC


@dataclass(frozen=True)
class AquaLogicSensorEntityDescription(SensorEntityDescription):
    """Describes AquaLogic sensor entity."""

    unit_metric: str | None = None
    unit_imperial: str | None = None


# keys correspond to property names in aqualogic.core.AquaLogic
SENSOR_TYPES: tuple[AquaLogicSensorEntityDescription, ...] = (
    AquaLogicSensorEntityDescription(
        key="air_temp",
        name="Air Temperature",
        unit_metric=UnitOfTemperature.CELSIUS,
        unit_imperial=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AquaLogicSensorEntityDescription(
        key="pool_temp",
        name="Pool Temperature",
        unit_metric=UnitOfTemperature.CELSIUS,
        unit_imperial=UnitOfTemperature.FAHRENHEIT,
        icon="mdi:oil-temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AquaLogicSensorEntityDescription(
        key="spa_temp",
        name="Spa Temperature",
        unit_metric=UnitOfTemperature.CELSIUS,
        unit_imperial=UnitOfTemperature.FAHRENHEIT,
        icon="mdi:oil-temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AquaLogicSensorEntityDescription(
        key="pool_chlorinator",
        name="Pool Chlorinator",
        unit_metric=PERCENTAGE,
        unit_imperial=PERCENTAGE,
        icon="mdi:gauge",
    ),
    AquaLogicSensorEntityDescription(
        key="spa_chlorinator",
        name="Spa Chlorinator",
        unit_metric=PERCENTAGE,
        unit_imperial=PERCENTAGE,
        icon="mdi:gauge",
    ),
    AquaLogicSensorEntityDescription(
        key="salt_level",
        name="Salt Level",
        unit_metric="g/L",
        unit_imperial="PPM",
        icon="mdi:gauge",
    ),
    AquaLogicSensorEntityDescription(
        key="pump_speed",
        name="Pump Speed",
        unit_metric=PERCENTAGE,
        unit_imperial=PERCENTAGE,
        icon="mdi:speedometer",
    ),
    AquaLogicSensorEntityDescription(
        key="pump_power",
        name="Pump Power",
        unit_metric=UnitOfPower.WATT,
        unit_imperial=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    AquaLogicSensorEntityDescription(
        key="status",
        name="Status",
        icon="mdi:alert",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquaLogicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor entities."""
    processor = entry.runtime_data

    async_add_entities(
        AquaLogicSensor(processor, description) for description in SENSOR_TYPES
    )


class AquaLogicSensor(SensorEntity):
    """Sensor implementation for the AquaLogic component."""

    entity_description: AquaLogicSensorEntityDescription
    _attr_should_poll = False

    def __init__(
        self,
        processor: AquaLogicProcessor,
        description: AquaLogicSensorEntityDescription,
    ) -> None:
        """Initialize sensor."""
        self.entity_description = description
        self._processor = processor
        self._attr_name = f"AquaLogic {description.name}"

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, UPDATE_TOPIC, self.async_update_callback
            )
        )

    @callback
    def async_update_callback(self) -> None:
        """Update callback."""
        if (panel := self._processor.panel) is not None:
            if panel.is_metric:
                self._attr_native_unit_of_measurement = (
                    self.entity_description.unit_metric
                )
            else:
                self._attr_native_unit_of_measurement = (
                    self.entity_description.unit_imperial
                )

            self._attr_native_value = getattr(panel, self.entity_description.key)
            self.async_write_ha_state()
        else:
            self._attr_native_value = None
            self.async_write_ha_state()
