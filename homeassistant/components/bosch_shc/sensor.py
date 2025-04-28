"""Platform for sensor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from boschshcpy.device import SHCDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import BoschConfigEntry
from .entity import SHCEntity


@dataclass(frozen=True, kw_only=True)
class SHCSensorEntityDescription(SensorEntityDescription):
    """Describes a SHC sensor."""

    value_fn: Callable[[SHCDevice], StateType]
    attributes_fn: Callable[[SHCDevice], dict[str, Any]] | None = None


TEMPERATURE_SENSOR = "temperature"
HUMIDITY_SENSOR = "humidity"
VALVE_TAPPET_SENSOR = "valvetappet"
PURITY_SENSOR = "purity"
AIR_QUALITY_SENSOR = "airquality"
TEMPERATURE_RATING_SENSOR = "temperature_rating"
HUMIDITY_RATING_SENSOR = "humidity_rating"
PURITY_RATING_SENSOR = "purity_rating"
POWER_SENSOR = "power"
ENERGY_SENSOR = "energy"
COMMUNICATION_QUALITY_SENSOR = "communication_quality"

SENSOR_DESCRIPTIONS: dict[str, SHCSensorEntityDescription] = {
    TEMPERATURE_SENSOR: SHCSensorEntityDescription(
        key=TEMPERATURE_SENSOR,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.temperature,
    ),
    HUMIDITY_SENSOR: SHCSensorEntityDescription(
        key=HUMIDITY_SENSOR,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.humidity,
    ),
    PURITY_SENSOR: SHCSensorEntityDescription(
        key=PURITY_SENSOR,
        translation_key=PURITY_SENSOR,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        value_fn=lambda device: device.purity,
    ),
    AIR_QUALITY_SENSOR: SHCSensorEntityDescription(
        key=AIR_QUALITY_SENSOR,
        translation_key="air_quality",
        value_fn=lambda device: device.combined_rating.name,
        attributes_fn=lambda device: {
            "rating_description": device.description,
        },
    ),
    TEMPERATURE_RATING_SENSOR: SHCSensorEntityDescription(
        key=TEMPERATURE_RATING_SENSOR,
        translation_key=TEMPERATURE_RATING_SENSOR,
        value_fn=lambda device: device.temperature_rating.name,
    ),
    COMMUNICATION_QUALITY_SENSOR: SHCSensorEntityDescription(
        key=COMMUNICATION_QUALITY_SENSOR,
        translation_key=COMMUNICATION_QUALITY_SENSOR,
        value_fn=lambda device: device.communicationquality.name,
    ),
    HUMIDITY_RATING_SENSOR: SHCSensorEntityDescription(
        key=HUMIDITY_RATING_SENSOR,
        translation_key=HUMIDITY_RATING_SENSOR,
        value_fn=lambda device: device.humidity_rating.name,
    ),
    PURITY_RATING_SENSOR: SHCSensorEntityDescription(
        key=PURITY_RATING_SENSOR,
        translation_key=PURITY_RATING_SENSOR,
        value_fn=lambda device: device.purity_rating.name,
    ),
    POWER_SENSOR: SHCSensorEntityDescription(
        key=POWER_SENSOR,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda device: device.powerconsumption,
    ),
    ENERGY_SENSOR: SHCSensorEntityDescription(
        key=ENERGY_SENSOR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda device: device.energyconsumption / 1000.0,
    ),
    VALVE_TAPPET_SENSOR: SHCSensorEntityDescription(
        key=VALVE_TAPPET_SENSOR,
        translation_key=VALVE_TAPPET_SENSOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.position,
        attributes_fn=lambda device: {
            "valve_tappet_state": device.valvestate.name,
        },
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC sensor platform."""
    session = config_entry.runtime_data

    entities: list[SensorEntity] = [
        SHCSensor(
            device,
            SENSOR_DESCRIPTIONS[sensor_type],
            session.information.unique_id,
            config_entry.entry_id,
        )
        for device in session.device_helper.thermostats
        for sensor_type in (TEMPERATURE_SENSOR, VALVE_TAPPET_SENSOR)
    ]

    entities.extend(
        SHCSensor(
            device,
            SENSOR_DESCRIPTIONS[sensor_type],
            session.information.unique_id,
            config_entry.entry_id,
        )
        for device in session.device_helper.wallthermostats
        for sensor_type in (TEMPERATURE_SENSOR, HUMIDITY_SENSOR)
    )

    entities.extend(
        SHCSensor(
            device,
            SENSOR_DESCRIPTIONS[sensor_type],
            session.information.unique_id,
            config_entry.entry_id,
        )
        for device in session.device_helper.twinguards
        for sensor_type in (
            TEMPERATURE_SENSOR,
            HUMIDITY_SENSOR,
            PURITY_SENSOR,
            AIR_QUALITY_SENSOR,
            TEMPERATURE_RATING_SENSOR,
            HUMIDITY_RATING_SENSOR,
            PURITY_RATING_SENSOR,
        )
    )

    entities.extend(
        SHCSensor(
            device,
            SENSOR_DESCRIPTIONS[sensor_type],
            session.information.unique_id,
            config_entry.entry_id,
        )
        for device in (
            session.device_helper.smart_plugs + session.device_helper.light_switches_bsm
        )
        for sensor_type in (POWER_SENSOR, ENERGY_SENSOR)
    )

    entities.extend(
        SHCSensor(
            device,
            SENSOR_DESCRIPTIONS[sensor_type],
            session.information.unique_id,
            config_entry.entry_id,
        )
        for device in session.device_helper.smart_plugs_compact
        for sensor_type in (POWER_SENSOR, ENERGY_SENSOR, COMMUNICATION_QUALITY_SENSOR)
    )

    async_add_entities(entities)


class SHCSensor(SHCEntity, SensorEntity):
    """Representation of a SHC sensor."""

    entity_description: SHCSensorEntityDescription

    def __init__(
        self,
        device: SHCDevice,
        entity_description: SHCSensorEntityDescription,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(device, parent_id, entry_id)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.serial}_{entity_description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._device)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self.entity_description.attributes_fn is not None:
            return self.entity_description.attributes_fn(self._device)
        return None
