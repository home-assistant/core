"""Sensor platform for Acaia."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from pyacaia_async.acaiascale import AcaiaDeviceState, AcaiaScale
from pyacaia_async.const import UnitMass as AcaiaUnitOfMass

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorExtraStoredData,
    SensorStateClass,
)
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import AcaiaConfigEntry, AcaiaCoordinator
from .entity import AcaiaEntity, AcaiaEntityDescription


@dataclass(kw_only=True, frozen=True)
class AcaiaSensorEntityDescription(AcaiaEntityDescription, SensorEntityDescription):
    """Description for Acaia Sensor entities."""

    unit_fn: Callable[[AcaiaDeviceState], str] | None = None
    value_fn: Callable[[AcaiaScale], StateType]


SENSORS: tuple[AcaiaSensorEntityDescription, ...] = (
    AcaiaSensorEntityDescription(
        key="weight",
        translation_key="weight",
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
)
RESTORE_SENSORS: tuple[AcaiaSensorEntityDescription, ...] = (
    AcaiaSensorEntityDescription(
        key="battery_level",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement="%",
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
    """Set up button entities and services."""

    coordinator = entry.runtime_data
    entities = [
        AcaiaSensor(coordinator, entity_description) for entity_description in SENSORS
    ]
    entities.extend(
        AcaiaRestoreSensor(coordinator, entity_description)
        for entity_description in RESTORE_SENSORS
    )
    async_add_entities(entities)


class AcaiaSensor(AcaiaEntity, SensorEntity):
    """Representation of a Acaia Sensor."""

    entity_description: AcaiaSensorEntityDescription

    def __init__(
        self,
        coordinator: AcaiaCoordinator,
        entity_description: AcaiaSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description)
        self._attr_native_unit_of_measurement = (
            entity_description.native_unit_of_measurement
        )
        self._scale = coordinator.scale

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._scale)


class AcaiaRestoreSensor(AcaiaSensor, RestoreSensor):
    """Representation of a Acaia Sensor with restore capabilities."""

    entity_description: AcaiaSensorEntityDescription

    def __init__(
        self,
        coordinator: AcaiaCoordinator,
        entity_description: AcaiaSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description)
        self._restored_data: SensorExtraStoredData | None = None

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self._restored_data = await self.async_get_last_sensor_data()

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if value := self.entity_description.value_fn(self._scale) is not None:
            return value

        if self._restored_data is None:
            return None

        return cast(StateType, self._restored_data.native_value)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of this entity."""
        if self._restored_data is not None:
            return self._restored_data.native_unit_of_measurement
        if (
            self.entity_description.unit_fn is not None
            and (device_state := self._scale.device_state) is not None
        ):
            return self.entity_description.unit_fn(device_state)
        return self.entity_description.native_unit_of_measurement

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available or self._restored_data is not None
