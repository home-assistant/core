"""The Wolf SmartSet sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from wolf_comm.models import (
    EnergyParameter,
    FlowParameter,
    FrequencyParameter,
    HoursParameter,
    ListItemParameter,
    Parameter,
    PercentageParameter,
    PowerParameter,
    Pressure,
    RPMParameter,
    SimpleParameter,
    Temperature,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DEVICE_ID, DOMAIN, MANUFACTURER, PARAMETERS, STATES


def get_listitem_resolve_state(wolf_object, state):
    """Resolve list item state."""
    resolved_state = [item for item in wolf_object.items if item.value == int(state)]
    if resolved_state:
        resolved_name = resolved_state[0].name
        state = STATES.get(resolved_name, resolved_name)
    return state


@dataclass(kw_only=True, frozen=True)
class WolflinkSensorEntityDescription(SensorEntityDescription):
    """Describes Wolflink sensor entity."""

    value_fn: Callable[[Parameter, str], str | None] = lambda param, value: value
    supported_fn: Callable[[Parameter], bool]


SENSOR_DESCRIPTIONS = [
    WolflinkSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        supported_fn=lambda param: isinstance(param, Temperature),
    ),
    WolflinkSensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        supported_fn=lambda param: isinstance(param, Pressure),
    ),
    WolflinkSensorEntityDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        supported_fn=lambda param: isinstance(param, EnergyParameter),
    ),
    WolflinkSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        supported_fn=lambda param: isinstance(param, PowerParameter),
    ),
    WolflinkSensorEntityDescription(
        key="percentage",
        native_unit_of_measurement=PERCENTAGE,
        supported_fn=lambda param: isinstance(param, PercentageParameter),
    ),
    WolflinkSensorEntityDescription(
        key="list_item",
        translation_key="state",
        supported_fn=lambda param: isinstance(param, ListItemParameter),
        value_fn=get_listitem_resolve_state,
    ),
    WolflinkSensorEntityDescription(
        key="hours",
        icon="mdi:clock",
        native_unit_of_measurement=UnitOfTime.HOURS,
        supported_fn=lambda param: isinstance(param, HoursParameter),
    ),
    WolflinkSensorEntityDescription(
        key="flow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        supported_fn=lambda param: isinstance(param, FlowParameter),
    ),
    WolflinkSensorEntityDescription(
        key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        supported_fn=lambda param: isinstance(param, FrequencyParameter),
    ),
    WolflinkSensorEntityDescription(
        key="rpm",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        supported_fn=lambda param: isinstance(param, RPMParameter),
    ),
    WolflinkSensorEntityDescription(
        key="default",
        supported_fn=lambda param: isinstance(param, SimpleParameter),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all entries for Wolf Platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    parameters = hass.data[DOMAIN][config_entry.entry_id][PARAMETERS]
    device_id = hass.data[DOMAIN][config_entry.entry_id][DEVICE_ID]

    entities: list[WolfLinkSensor] = [
        WolfLinkSensor(coordinator, parameter, device_id, description)
        for parameter in parameters
        for description in SENSOR_DESCRIPTIONS
        if description.supported_fn(parameter)
    ]

    async_add_entities(entities, True)


class WolfLinkSensor(CoordinatorEntity, SensorEntity):
    """Base class for all Wolf entities."""

    entity_description: WolflinkSensorEntityDescription

    def __init__(
        self,
        coordinator,
        wolf_object: Parameter,
        device_id: str,
        description: WolflinkSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self.wolf_object = wolf_object
        self._attr_name = wolf_object.name
        self._attr_unique_id = f"{device_id}:{wolf_object.parameter_id}"
        self._state = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            configuration_url="https://www.wolf-smartset.com/",
            manufacturer=MANUFACTURER,
        )

    @property
    def native_value(self) -> str | None:
        """Return the state. Wolf Client is returning only changed values so we need to store old value here."""
        if self.wolf_object.parameter_id in self.coordinator.data:
            new_state = self.coordinator.data[self.wolf_object.parameter_id]
            self.wolf_object.value_id = new_state[0]
            self._state = new_state[1]
            if (
                isinstance(self.wolf_object, ListItemParameter)
                and self._state is not None
            ):
                self._state = self.entity_description.value_fn(
                    self.wolf_object, self._state
                )
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return the state attributes."""
        return {
            "parameter_id": self.wolf_object.parameter_id,
            "value_id": self.wolf_object.value_id,
            "parent": self.wolf_object.parent,
        }
