"""The Wolf SmartSet sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from wolf_comm.models import (
    EnergyParameter,
    HoursParameter,
    ListItemParameter,
    Parameter,
    PercentageParameter,
    PowerParameter,
    Pressure,
    SimpleParameter,
    Temperature,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DEVICE_ID, DOMAIN, MANUFACTURER, PARAMETERS, STATES


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
        WolfLinkSensor(
            coordinator, parameter, device_id, get_entity_description(parameter)
        )
        for parameter in parameters
    ]

    async_add_entities(entities, True)


@dataclass(kw_only=True, frozen=True)
class WolflinkSensorEntityDescription(SensorEntityDescription):
    """Describes Wolflink sensor entity."""

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
    ),
    WolflinkSensorEntityDescription(
        key="hours",
        icon="mdi:clock",
        native_unit_of_measurement=UnitOfTime.HOURS,
        supported_fn=lambda param: isinstance(param, HoursParameter),
    ),
    WolflinkSensorEntityDescription(
        key="default",
        supported_fn=lambda param: isinstance(param, SimpleParameter),
    ),
]


def get_entity_description(parameter: Parameter) -> WolflinkSensorEntityDescription:
    """Return the entity description for a given parameter."""
    for description in SENSOR_DESCRIPTIONS:
        if description.supported_fn(parameter):
            return WolflinkSensorEntityDescription(
                key=parameter.parameter_id,
                name=parameter.name,
                device_class=description.device_class,
                native_unit_of_measurement=description.native_unit_of_measurement,
                icon=description.icon,
                entity_registry_enabled_default=description.entity_registry_enabled_default,
                entity_category=description.entity_category,
                has_entity_name=description.has_entity_name,
                translation_key=description.translation_key,
                supported_fn=description.supported_fn,
            )
    return WolflinkSensorEntityDescription(
        key=parameter.parameter_id,
        name=parameter.name,
        supported_fn=lambda param: True,
    )


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
        self._attr_name = str(description.name)
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
                resolved_state = [
                    item
                    for item in self.wolf_object.items
                    if item.value == int(self._state)
                ]
                if resolved_state:
                    resolved_name = resolved_state[0].name
                    self._state = STATES.get(resolved_name, resolved_name)
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return the state attributes."""
        return {
            "parameter_id": self.wolf_object.parameter_id,
            "value_id": self.wolf_object.value_id,
            "parent": self.wolf_object.parent,
        }
