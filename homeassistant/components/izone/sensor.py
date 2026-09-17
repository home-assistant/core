"""Support for iZone sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from operator import attrgetter
from typing import override

from pizone import Controller, Power, PowerChannel, PowerDevice, PowerGroup, Zone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import IZoneConfigEntry, IZoneCoordinator
from .entity import IZoneCoordinatorEntity

PARALLEL_UPDATES = 0

type IZoneSensorSource = (
    Controller | Zone | Power | PowerDevice | PowerChannel | PowerGroup
)


@dataclass(frozen=True, kw_only=True)
class IZoneSensorEntityDescription[SourceT: IZoneSensorSource](SensorEntityDescription):
    """Describes an iZone sensor; value_fn reads from a pizone source object."""

    value_fn: Callable[[SourceT], StateType]


CONTROLLER_SENSOR_DESCRIPTIONS: tuple[IZoneSensorEntityDescription[Controller], ...] = (
    IZoneSensorEntityDescription[Controller](
        key="supply_temperature",
        translation_key="supply_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=attrgetter("temp_supply"),
    ),
    IZoneSensorEntityDescription[Controller](
        key="return_temperature",
        translation_key="return_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=attrgetter("temp_return"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IZoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up iZone sensor entities from the entry coordinator."""
    coordinator = entry.runtime_data
    controller = coordinator.controller
    async_add_entities(
        IZoneSensor(
            coordinator,
            description,
            controller,
            unique_id=f"{controller.device_uid}_{description.key}",
            device_info=DeviceInfo(
                identifiers={(DOMAIN, controller.device_uid)},
                manufacturer="IZone",
                model=controller.sys_type,
                name=f"iZone Controller {controller.device_uid}",
            ),
        )
        for description in CONTROLLER_SENSOR_DESCRIPTIONS
    )


class IZoneSensor[SourceT: IZoneSensorSource](IZoneCoordinatorEntity, SensorEntity):
    """Sensor backed by a pizone Controller, Zone, or Power* object."""

    _attr_has_entity_name = True
    entity_description: IZoneSensorEntityDescription[SourceT]

    def __init__(
        self,
        coordinator: IZoneCoordinator,
        description: IZoneSensorEntityDescription[SourceT],
        source: SourceT,
        *,
        unique_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor for *source*."""
        super().__init__(coordinator)
        self.entity_description = description
        self._source = source
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value from the pizone source object."""
        return self.entity_description.value_fn(self._source)
