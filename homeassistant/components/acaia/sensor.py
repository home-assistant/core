"""Sensor platform for Acaia."""

from collections.abc import Callable
from dataclasses import dataclass

from aioacaia.acaiascale import AcaiaDeviceState, AcaiaScale
from aioacaia.const import UnitMass as AcaiaUnitOfMass

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorExtraStoredData,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfMass, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AcaiaConfigEntry
from .entity import AcaiaEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class AcaiaSensorEntityDescription(SensorEntityDescription):
    """Description for Acaia sensor entities."""

    value_fn: Callable[[AcaiaScale], int | float | None]


@dataclass(kw_only=True, frozen=True)
class AcaiaDynamicUnitSensorEntityDescription(AcaiaSensorEntityDescription):
    """Description for Acaia sensor entities with dynamic units."""

    unit_fn: Callable[[AcaiaDeviceState], str] | None = None


SENSORS: tuple[AcaiaSensorEntityDescription, ...] = (
    AcaiaDynamicUnitSensorEntityDescription(
        key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.GRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=lambda data: (
            UnitOfMass.OUNCES
            if data.units == AcaiaUnitOfMass.OUNCES
            else UnitOfMass.GRAMS
        ),
        value_fn=lambda scale: scale.weight,
    ),
    AcaiaDynamicUnitSensorEntityDescription(
        key="flow_rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.MILLILITERS_PER_SECOND,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda scale: scale.flow_rate,
    ),
)
RESTORE_SENSORS: tuple[AcaiaSensorEntityDescription, ...] = (
    AcaiaSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda scale: (
            scale.device_state.battery_level if scale.device_state else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AcaiaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""

    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        AcaiaSensor(coordinator, entity_description) for entity_description in SENSORS
    ]
    entities.extend(
        AcaiaRestoreSensor(coordinator, entity_description)
        for entity_description in RESTORE_SENSORS
    )
    async_add_entities(entities)


class AcaiaSensor(AcaiaEntity, SensorEntity):
    """Representation of an Acaia sensor."""

    entity_description: AcaiaDynamicUnitSensorEntityDescription

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of this entity."""
        if (
            self._scale.device_state is not None
            and self.entity_description.unit_fn is not None
        ):
            return self.entity_description.unit_fn(self._scale.device_state)
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the entity."""
        return self.entity_description.value_fn(self._scale)


class AcaiaRestoreSensor(AcaiaEntity, RestoreSensor):
    """Representation of an Acaia sensor with restore capabilities."""

    entity_description: AcaiaSensorEntityDescription
    _restored_data: SensorExtraStoredData | None = None

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        self._restored_data = await self.async_get_last_sensor_data()
        if self._restored_data is not None:
            self._attr_native_value = self._restored_data.native_value
            self._attr_native_unit_of_measurement = (
                self._restored_data.native_unit_of_measurement
            )

        if self._scale.device_state is not None:
            self._attr_native_value = self.entity_description.value_fn(self._scale)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._scale.device_state is not None:
            self._attr_native_value = self.entity_description.value_fn(self._scale)
        self._async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available or self._restored_data is not None
