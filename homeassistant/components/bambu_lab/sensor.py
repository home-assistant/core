"""Sensor platform for the Bambu Lab integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiobambulab import BambuLabClient, PrinterState, PrintState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import BambuLabConfigEntry
from .entity import BambuLabEntity

# The printer pushes its state, there is nothing to limit.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BambuLabSensorEntityDescription(SensorEntityDescription):
    """Describe a Bambu Lab sensor."""

    value_fn: Callable[[PrinterState], StateType]


SENSORS: tuple[BambuLabSensorEntityDescription, ...] = (
    BambuLabSensorEntityDescription(
        key="print_status",
        translation_key="print_status",
        device_class=SensorDeviceClass.ENUM,
        options=[state.value for state in PrintState],
        value_fn=lambda state: state.print_state,
    ),
    BambuLabSensorEntityDescription(
        key="print_progress",
        translation_key="print_progress",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda state: state.progress,
    ),
    BambuLabSensorEntityDescription(
        key="remaining_time",
        translation_key="remaining_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda state: state.remaining_minutes,
    ),
    BambuLabSensorEntityDescription(
        key="current_layer",
        translation_key="current_layer",
        value_fn=lambda state: state.current_layer,
    ),
    BambuLabSensorEntityDescription(
        key="total_layers",
        translation_key="total_layers",
        value_fn=lambda state: state.total_layers,
    ),
    BambuLabSensorEntityDescription(
        key="nozzle_temperature",
        translation_key="nozzle_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda state: state.nozzle_temperature,
    ),
    BambuLabSensorEntityDescription(
        key="bed_temperature",
        translation_key="bed_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda state: state.bed_temperature,
    ),
)

# Not every printer measures the temperature of its chamber.
CHAMBER_TEMPERATURE_SENSOR = BambuLabSensorEntityDescription(
    key="chamber_temperature",
    translation_key="chamber_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=0,
    value_fn=lambda state: state.chamber_temperature,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BambuLabConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors of a Bambu Lab printer."""
    client = entry.runtime_data

    descriptions = list(SENSORS)
    if client.state.chamber_temperature is not None:
        descriptions.append(CHAMBER_TEMPERATURE_SENSOR)

    async_add_entities(
        BambuLabSensor(client, description) for description in descriptions
    )


class BambuLabSensor(BambuLabEntity, SensorEntity):
    """A sensor of a Bambu Lab printer."""

    entity_description: BambuLabSensorEntityDescription

    def __init__(
        self, client: BambuLabClient, description: BambuLabSensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(client)
        self.entity_description = description
        self._attr_unique_id = f"{client.serial}_{description.key}"

    @override
    @property
    def native_value(self) -> StateType:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self._client.state)
