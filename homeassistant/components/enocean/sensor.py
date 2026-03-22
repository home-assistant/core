"""Support for EnOcean sensors."""

from __future__ import annotations

from datetime import UTC, datetime

from enocean_async import EURID, EntityType, Gateway, Observable, Observation
from enocean_async.semantics.entity import EntityCategory as LibEntityCategory
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
from .entity import EnOceanEntity, EnOceanEntityID

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

_SCALAR_STATE_CLASS: SensorStateClass = SensorStateClass.MEASUREMENT

_LIB_CATEGORY_MAP: dict[str, EntityCategory | None] = {
    LibEntityCategory.CONFIG: EntityCategory.CONFIG,
    LibEntityCategory.DIAGNOSTIC: EntityCategory.DIAGNOSTIC,
    LibEntityCategory.DEFAULT: None,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway: Gateway = config_entry.runtime_data
    gateway_eurid: EURID = await gateway.eurid

    entities: list[EnOceanSensor] = []

    for eurid, spec in gateway.device_specs.items():
        for entity in spec.entities:
            if entity.entity_type not in (EntityType.SENSOR, EntityType.METADATA):
                continue
            for observable in entity.observables:
                if observable.kind == ValueKind.BINARY:
                    continue
                entity_id = EnOceanEntityID(
                    device_address=eurid,
                    unique_id=f"{entity.id}.{observable.value}",
                )
                entities.append(
                    EnOceanSensor(
                        entity_id,
                        gateway,
                        gateway_eurid,
                        observable,
                        entity.id,
                        entity_category=EntityCategory.DIAGNOSTIC
                        if entity.entity_type == EntityType.METADATA
                        else None,
                    )
                )

    for entity in gateway.gateway_entities:
        for observable in entity.observables:
            entity_id = EnOceanEntityID(
                device_address=gateway_eurid,
                unique_id=entity.id,
            )
            entities.append(
                EnOceanSensor(
                    entity_id,
                    gateway,
                    gateway_eurid,
                    observable,
                    entity.id,
                    entity_category=_LIB_CATEGORY_MAP.get(entity.category),
                )
            )

    async_add_entities(entities)


class EnOceanSensor(EnOceanEntity, RestoreSensor):
    """Representation of an EnOcean sensor."""

    def __init__(
        self,
        entity_id: EnOceanEntityID,
        gateway: Gateway,
        gateway_eurid: EURID,
        observable: Observable,
        eep_entity_id: str,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize the EnOcean sensor."""
        super().__init__(
            enocean_entity_id=entity_id,
            gateway=gateway,
            gateway_eurid=gateway_eurid,
        )
        self._observable = observable
        self._entity_part = eep_entity_id
        # Use the observable's own value string as the translation key (e.g. "temperature",
        # "last_seen") rather than the full unique_id which contains a dot.
        self._attr_translation_key = observable.value
        self._attr_entity_category = entity_category
        self._attr_device_class = _OBSERVABLE_TO_DEVICE_CLASS.get(observable)
        self._attr_native_unit_of_measurement = observable.unit
        if observable.kind == ValueKind.ENUM:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = observable.possible_values
            self._attr_native_unit_of_measurement = None
        else:
            self._attr_state_class = _SCALAR_STATE_CLASS

        gateway.add_observation_callback(self._on_observation)

    def _on_observation(self, observation: Observation) -> None:
        """Handle an incoming observation."""
        if (
            observation.device != self.enocean_entity_id.device_address
            or observation.entity != self._entity_part
            or self._observable not in observation.values
        ):
            return

        value = observation.values[self._observable]
        if self._observable is Observable.LAST_SEEN:
            value = datetime.fromtimestamp(value, tz=UTC)
        self._attr_native_value = value
        self.schedule_update_ha_state()
