"""Platform for sensor integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from boschshcpy import (
    SHCLightSwitchBSM,
    SHCSmartPlug,
    SHCSmartPlugCompact,
    SHCThermostat,
    SHCTwinguard,
    SHCWallThermostat,
)
from boschshcpy.device import SHCDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfPower,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import BoschConfigEntry
from .entity import SHCEntity


@dataclass(frozen=True, kw_only=True)
class SHCSensorEntityDescription[_DeviceT: SHCDevice](SensorEntityDescription):
    """Describes a SHC sensor."""

    value_fn: Callable[[_DeviceT], StateType]
    attributes_fn: Callable[[_DeviceT], dict[str, Any]] | None = None


_PowerMeterDevice = SHCSmartPlug | SHCLightSwitchBSM | SHCSmartPlugCompact

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

THERMOSTAT_SENSOR_TYPES: tuple[SHCSensorEntityDescription[SHCThermostat], ...] = (
    SHCSensorEntityDescription[SHCThermostat](
        key=TEMPERATURE_SENSOR,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.temperature,
    ),
    SHCSensorEntityDescription[SHCThermostat](
        key=VALVE_TAPPET_SENSOR,
        translation_key=VALVE_TAPPET_SENSOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        value_fn=lambda device: device.position,
        attributes_fn=lambda device: {
            "valve_tappet_state": device.valvestate.name,
        },
    ),
)

WALLTHERMOSTAT_SENSOR_TYPES: tuple[
    SHCSensorEntityDescription[SHCWallThermostat], ...
] = (
    SHCSensorEntityDescription[SHCWallThermostat](
        key=TEMPERATURE_SENSOR,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.temperature,
    ),
    SHCSensorEntityDescription[SHCWallThermostat](
        key=HUMIDITY_SENSOR,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        value_fn=lambda device: device.humidity,
    ),
)

TWINGUARD_SENSOR_TYPES: tuple[SHCSensorEntityDescription[SHCTwinguard], ...] = (
    SHCSensorEntityDescription[SHCTwinguard](
        key=TEMPERATURE_SENSOR,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.temperature,
    ),
    SHCSensorEntityDescription[SHCTwinguard](
        key=HUMIDITY_SENSOR,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        value_fn=lambda device: device.humidity,
    ),
    SHCSensorEntityDescription[SHCTwinguard](
        key=PURITY_SENSOR,
        translation_key=PURITY_SENSOR,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        value_fn=lambda device: device.purity,
    ),
    SHCSensorEntityDescription[SHCTwinguard](
        key=AIR_QUALITY_SENSOR,
        translation_key="air_quality",
        value_fn=lambda device: device.combined_rating.name,
        attributes_fn=lambda device: {
            "rating_description": device.description,
        },
    ),
    SHCSensorEntityDescription[SHCTwinguard](
        key=TEMPERATURE_RATING_SENSOR,
        translation_key=TEMPERATURE_RATING_SENSOR,
        value_fn=lambda device: device.temperature_rating.name,
    ),
    SHCSensorEntityDescription[SHCTwinguard](
        key=HUMIDITY_RATING_SENSOR,
        translation_key=HUMIDITY_RATING_SENSOR,
        value_fn=lambda device: device.humidity_rating.name,
    ),
    SHCSensorEntityDescription[SHCTwinguard](
        key=PURITY_RATING_SENSOR,
        translation_key=PURITY_RATING_SENSOR,
        value_fn=lambda device: device.purity_rating.name,
    ),
)

POWER_METER_SENSOR_TYPES: tuple[SHCSensorEntityDescription[_PowerMeterDevice], ...] = (
    SHCSensorEntityDescription[_PowerMeterDevice](
        key=POWER_SENSOR,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda device: device.powerconsumption,
    ),
    SHCSensorEntityDescription[_PowerMeterDevice](
        key=ENERGY_SENSOR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda device: device.energyconsumption / 1000.0,
    ),
)

PLUG_COMPACT_SENSOR_TYPES: tuple[
    SHCSensorEntityDescription[SHCSmartPlugCompact], ...
] = (
    SHCSensorEntityDescription[SHCSmartPlugCompact](
        key=COMMUNICATION_QUALITY_SENSOR,
        translation_key=COMMUNICATION_QUALITY_SENSOR,
        value_fn=lambda device: device.communicationquality.name,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC sensor platform."""
    session = config_entry.runtime_data.session
    parent_id = config_entry.runtime_data.parent_id

    entities: list[SensorEntity] = [
        SHCSensor(device, description, parent_id, config_entry.entry_id)
        for device in session.device_helper.thermostats
        for description in THERMOSTAT_SENSOR_TYPES
    ]

    entities.extend(
        SHCSensor(device, description, parent_id, config_entry.entry_id)
        for device in session.device_helper.wallthermostats
        for description in WALLTHERMOSTAT_SENSOR_TYPES
    )

    entities.extend(
        SHCSensor(device, description, parent_id, config_entry.entry_id)
        for device in session.device_helper.twinguards
        for description in TWINGUARD_SENSOR_TYPES
    )

    power_meter_devices: list[_PowerMeterDevice] = [
        *session.device_helper.smart_plugs,
        *session.device_helper.light_switches_bsm,
        *session.device_helper.smart_plugs_compact,
    ]
    entities.extend(
        SHCSensor(device, description, parent_id, config_entry.entry_id)
        for device in power_meter_devices
        for description in POWER_METER_SENSOR_TYPES
    )

    entities.extend(
        SHCSensor(device, description, parent_id, config_entry.entry_id)
        for device in session.device_helper.smart_plugs_compact
        for description in PLUG_COMPACT_SENSOR_TYPES
    )

    async_add_entities(entities)


class SHCSensor[_DeviceT: SHCDevice](SHCEntity[_DeviceT], SensorEntity):
    """Representation of a SHC sensor."""

    entity_description: SHCSensorEntityDescription[_DeviceT]

    def __init__(
        self,
        device: _DeviceT,
        entity_description: SHCSensorEntityDescription[_DeviceT],
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(device, parent_id, entry_id)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.serial}_{entity_description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._device)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self.entity_description.attributes_fn is not None:
            return self.entity_description.attributes_fn(self._device)
        return None
