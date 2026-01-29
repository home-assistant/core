"""Support for EnOcean sensors."""

from __future__ import annotations

from datetime import datetime

from homeassistant_enocean.entity_id import EnOceanEntityID
from homeassistant_enocean.entity_properties import HomeAssistantEntityProperties
from homeassistant_enocean.gateway import EnOceanHomeAssistantGateway

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_entry import EnOceanConfigEntry
from .entity import EnOceanEntity

CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_RANGE_FROM = "range_from"
CONF_RANGE_TO = "range_to"

DEFAULT_NAME = ""

SENSOR_TYPE_HUMIDITY = "humidity"
SENSOR_TYPE_POWER = "powersensor"
SENSOR_TYPE_TEMPERATURE = "temperature"
SENSOR_TYPE_WINDOWHANDLE = "windowhandle"


SENSOR_DESC_TEMPERATURE = SensorEntityDescription(
    key=SENSOR_TYPE_TEMPERATURE,
    name="Temperature",
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
)

SENSOR_DESC_HUMIDITY = SensorEntityDescription(
    key=SENSOR_TYPE_HUMIDITY,
    name="Humidity",
    native_unit_of_measurement=PERCENTAGE,
    device_class=SensorDeviceClass.HUMIDITY,
    state_class=SensorStateClass.MEASUREMENT,
)

SENSOR_DESC_POWER = SensorEntityDescription(
    key=SENSOR_TYPE_POWER,
    name="Power",
    native_unit_of_measurement=UnitOfPower.WATT,
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
)

SENSOR_DESC_WINDOWHANDLE = SensorEntityDescription(
    key=SENSOR_TYPE_WINDOWHANDLE, name="WindowHandle", icon="mdi:window-open-variant"
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway = config_entry.runtime_data.gateway

    for entity_id in gateway.sensor_entities:
        properties: HomeAssistantEntityProperties | None = gateway.sensor_entities[
            entity_id
        ]

        if properties is None:
            # should not happen
            continue

        async_add_entities(
            [
                EnOceanSensor(
                    entity_id,
                    gateway=gateway,
                    device_class=properties.device_class,
                    state_class=properties.state_class,
                    native_unit_of_measurement=properties.native_unit_of_measurement
                    if properties.device_class != SensorDeviceClass.ENUM
                    else None,
                    entity_category=properties.entity_category,
                    options=properties.options
                    if properties.device_class == SensorDeviceClass.ENUM
                    else None,
                )
            ]
        )


class EnOceanSensor(EnOceanEntity, RestoreSensor):
    """Representation of EnOcean switches."""

    def __init__(
        self,
        entity_id: EnOceanEntityID,
        gateway: EnOceanHomeAssistantGateway,
        device_class: SensorDeviceClass | None = None,
        entity_category: str | None = None,
        state_class: SensorStateClass | None = None,
        native_unit_of_measurement: str | None = None,
        options: list[str] | None = None,
    ) -> None:
        """Initialize the EnOcean switch."""
        super().__init__(
            enocean_entity_id=entity_id,
            gateway=gateway,
            device_class=device_class,
            entity_category=entity_category,
        )
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_options = options
        self.gateway.register_sensor_callback(self.enocean_entity_id, self.update)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

    def update(self, value: float | datetime) -> None:
        """Update the sensor state."""
        self._attr_native_value = value
        self.schedule_update_ha_state()
