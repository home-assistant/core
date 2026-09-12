"""Support for iZone sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from operator import attrgetter
from typing import override

from pizone import Controller, Power, PowerChannel, PowerDevice, PowerGroup, Zone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
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


def _control_zone_entity_id(hass: HomeAssistant, controller: Controller) -> str | None:
    """Return the climate entity ID that currently owns the unit setpoint."""
    owner = controller.control_setpoint_owner
    if owner is controller:
        unique_id = controller.device_uid
    elif isinstance(owner, Zone):
        unique_id = f"{controller.device_uid}_z{owner.index + 1}"
    else:
        return None
    return er.async_get(hass).async_get_entity_id(Platform.CLIMATE, DOMAIN, unique_id)


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
    IZoneSensorEntityDescription[Controller](
        key="control_zone_setpoint",
        translation_key="control_zone_setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=attrgetter("control_setpoint"),
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
    device_info = DeviceInfo(
        identifiers={(DOMAIN, controller.device_uid)},
        manufacturer="IZone",
        model=controller.sys_type,
        name=f"iZone Controller {controller.device_uid}",
    )
    descriptions: tuple[IZoneSensorEntityDescription[Controller], ...] = (
        *CONTROLLER_SENSOR_DESCRIPTIONS,
        IZoneSensorEntityDescription[Controller](
            key="control_zone",
            translation_key="control_zone",
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=partial(_control_zone_entity_id, hass),
        ),
    )
    async_add_entities(
        IZoneSensor(
            coordinator,
            description,
            controller,
            unique_id=f"{controller.device_uid}_{description.key}",
            device_info=device_info,
        )
        for description in descriptions
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
