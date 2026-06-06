"""BleBox sensor entities."""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import blebox_uniapi.sensor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import BleBoxConfigEntry
from .const import OPEN_STATUS
from .coordinator import BleBoxCoordinator
from .entity import BleBoxEntity

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class BleBoxSensorEntityDescription(SensorEntityDescription):
    """Describes a BleBox sensor entity."""

    value_fn: Callable[[StateType], StateType] = lambda v: v


SENSOR_TYPES: tuple[BleBoxSensorEntityDescription, ...] = (
    BleBoxSensorEntityDescription(
        key="pm1",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    BleBoxSensorEntityDescription(
        key="pm2_5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    BleBoxSensorEntityDescription(
        key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    BleBoxSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    BleBoxSensorEntityDescription(
        key="powerConsumption",
        translation_key="power_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    BleBoxSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    BleBoxSensorEntityDescription(
        key="wind",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
    ),
    BleBoxSensorEntityDescription(
        key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
    ),
    BleBoxSensorEntityDescription(
        key="forwardActiveEnergy",
        translation_key="forward_active_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    BleBoxSensorEntityDescription(
        key="reverseActiveEnergy",
        translation_key="reverse_active_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    BleBoxSensorEntityDescription(
        key="reactivePower",
        translation_key="reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
    ),
    BleBoxSensorEntityDescription(
        key="activePower",
        translation_key="active_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    BleBoxSensorEntityDescription(
        key="apparentPower",
        translation_key="apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
    ),
    BleBoxSensorEntityDescription(
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    BleBoxSensorEntityDescription(
        key="current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
    ),
    BleBoxSensorEntityDescription(
        key="frequency",
        translation_key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
    ),
    BleBoxSensorEntityDescription(
        key="openStatus",
        translation_key="open_status",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:window-open",
        options=list(OPEN_STATUS.values()),
        value_fn=lambda v: OPEN_STATUS.get(int(v)) if v is not None else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BleBoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a BleBox entry."""

    coordinator = config_entry.runtime_data
    features = coordinator.box.features.get("sensors", [])
    counts = Counter(f.device_class for f in features)
    entities = [
        BleBoxSensorEntity(
            coordinator,
            feature,
            description,
            feature.index
            if counts[feature.device_class] > 1 and feature.index
            else None,
        )
        for feature in features
        for description in SENSOR_TYPES
        if description.key == feature.device_class
    ]
    async_add_entities(entities)


class BleBoxSensorEntity(BleBoxEntity[blebox_uniapi.sensor.BaseSensor], SensorEntity):
    """Representation of a BleBox sensor feature."""

    entity_description: BleBoxSensorEntityDescription

    def __init__(
        self,
        coordinator: BleBoxCoordinator,
        feature: blebox_uniapi.sensor.BaseSensor,
        description: BleBoxSensorEntityDescription,
        index: int | None = None,
    ) -> None:
        """Initialize a BleBox sensor feature."""
        super().__init__(coordinator, feature)
        self.entity_description = description
        if feature.name:
            self._attr_name = feature.name
        elif index is not None and description.translation_key:
            self._attr_translation_key = f"{description.translation_key}_n"
            self._attr_translation_placeholders = {"index": str(index)}

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.entity_description.value_fn(self._feature.native_value)

    @property
    def last_reset(self) -> datetime | None:
        """Return the time when the sensor was last reset, if implemented."""
        if self.state_class != SensorStateClass.TOTAL:
            return None
        native_implementation = getattr(self._feature, "last_reset", None)
        return native_implementation or super().last_reset
