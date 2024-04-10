"""Support for Senziio API."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.mqtt import async_subscribe
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
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.json import json_loads_object

from .entity import DOMAIN, SenziioEntity


@dataclass(frozen=True, kw_only=True)
class SenziioSensorEntityDescription(SensorEntityDescription):
    """Class describing Senziio sensor entities."""

    value_key: str


SENSOR_DESCRIPTIONS: tuple[SenziioSensorEntityDescription, ...] = (
    SenziioSensorEntityDescription(
        name="Person Counter",
        key="person-counter",
        value_key="counter",
        translation_key="person-counter",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenziioSensorEntityDescription(
        name="Atmospheric Pressure",
        key="atm-pressure",
        value_key="pressure",
        translation_key="atmospheric-pressure",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
    ),
    SenziioSensorEntityDescription(
        name="CO2",
        key="co2",
        value_key="co2",
        translation_key="co2",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    SenziioSensorEntityDescription(
        name="Humidity",
        key="humidity",
        value_key="humidity",
        translation_key="humidity",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SenziioSensorEntityDescription(
        name="Illuminance",
        key="illuminance",
        value_key="light_level",
        translation_key="illuminance",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
    ),
    SenziioSensorEntityDescription(
        name="Temperature",
        key="temperature",
        value_key="temperature",
        translation_key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Senziio entities."""
    device = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SenziioSensorEntity(hass, entity_description, entry, device)
            for entity_description in SENSOR_DESCRIPTIONS
        ]
    )


class SenziioSensorEntity(SenziioEntity, SensorEntity):
    """Senziio binary sensor entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        entity_description: SenziioSensorEntityDescription,
        entry: ConfigEntry,
        device,
    ) -> None:
        """Initialize entity."""
        super().__init__(entry)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.id}_{entity_description.key}"
        self._hass = hass
        self._dt_topic = device.entity_topic(entity_description.key)

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT data event."""

        @callback
        def message_received(message):
            """Handle new MQTT messages."""
            data = json_loads_object(message.payload)
            self._attr_native_value = data.get(self.entity_description.value_key)
            self.async_write_ha_state()

        await async_subscribe(self._hass, self._dt_topic, message_received, 1)
