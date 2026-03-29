"""Support for EnOcean sensors."""

from __future__ import annotations

from datetime import UTC, datetime

from enocean_async import EURID, EntityType, Gateway, Observable, Observation
from enocean_async.semantics.value_kind import ValueKind

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EnOceanConfigEntry
from .entity import LIB_ENTITY_CATEGORY_MAP, EnOceanEntity

PARALLEL_UPDATES = 0

_OBSERVABLE_TO_DEVICE_CLASS: dict[Observable, SensorDeviceClass] = {
    Observable.TEMPERATURE: SensorDeviceClass.TEMPERATURE,
    Observable.HUMIDITY: SensorDeviceClass.HUMIDITY,
    Observable.ILLUMINATION: SensorDeviceClass.ILLUMINANCE,
    Observable.VOLTAGE: SensorDeviceClass.VOLTAGE,
    Observable.POWER: SensorDeviceClass.POWER,
    Observable.ENERGY: SensorDeviceClass.ENERGY,
    Observable.GAS_VOLUME: SensorDeviceClass.GAS,
    Observable.WATER_VOLUME: SensorDeviceClass.WATER,
    Observable.RSSI: SensorDeviceClass.SIGNAL_STRENGTH,
    Observable.LAST_SEEN: SensorDeviceClass.TIMESTAMP,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway: Gateway = config_entry.runtime_data
    gateway_eurid: EURID | None = gateway.eurid
    if gateway_eurid is None:
        return

    entities: list[EnOceanSensor] = []

    for eurid, spec in gateway.device_specs.items():
        for entity in spec.entities:
            if entity.entity_type not in (EntityType.SENSOR, EntityType.METADATA):
                continue
            for observable in entity.observables:
                if observable.kind == ValueKind.BINARY:
                    continue
                entities.append(
                    EnOceanSensor(
                        eurid,
                        entity.id,
                        gateway,
                        observable,
                        entity_category=EntityCategory.DIAGNOSTIC
                        if entity.entity_type == EntityType.METADATA
                        else None,
                    )
                )

    for entity in gateway.gateway_entities:
        (observable,) = entity.observables
        entities.append(
            EnOceanSensor(
                gateway_eurid,
                entity.id,
                gateway,
                observable,
                entity_category=LIB_ENTITY_CATEGORY_MAP.get(entity.category),
            )
        )

    async_add_entities(entities)


class EnOceanSensor(EnOceanEntity, RestoreSensor):
    """Representation of an EnOcean sensor."""

    def __init__(
        self,
        address: EURID,
        entity_key: str,
        gateway: Gateway,
        observable: Observable,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize the EnOcean sensor."""
        super().__init__(address, entity_key, gateway)
        self._observable = observable
        # entity_key is the EEP entity id; unique_id needs the observable suffix
        # to be distinct when a device entity exposes multiple observables.
        self._attr_unique_id = f"{address}.{entity_key}.{observable.value}"
        # Use the observable name as translation key (e.g. "temperature").
        self._attr_translation_key = observable.value
        self._attr_entity_category = entity_category
        self._attr_device_class = _OBSERVABLE_TO_DEVICE_CLASS.get(observable)
        self._attr_native_unit_of_measurement = observable.unit
        if observable.kind == ValueKind.ENUM:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = observable.possible_values
            self._attr_native_unit_of_measurement = None
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    def _update_from_observation(self, observation: Observation) -> None:
        """Update sensor state from a matched observation."""
        if self._observable not in observation.values:
            return

        value = observation.values[self._observable]
        if self._observable is Observable.LAST_SEEN:
            value = datetime.fromtimestamp(value, tz=UTC)
        self._attr_native_value = value
        self.async_write_ha_state()
