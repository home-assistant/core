"""Support for AquaLogic sensors."""

from __future__ import annotations

from dataclasses import dataclass

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    PERCENTAGE,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, UPDATE_TOPIC, AquaLogicProcessor


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

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        )
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    processor: AquaLogicProcessor = hass.data[DOMAIN]
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]

    entities = [
        AquaLogicSensor(processor, description)
        for description in SENSOR_TYPES
        if description.key in monitored_conditions
    ]

    async_add_entities(entities)


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
            self._attr_native_unit_of_measurement = None
